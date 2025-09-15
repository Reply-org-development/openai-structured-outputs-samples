#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gift_finder_agent.py — agente "find-gift" che:
- usa Redis Vector DB per cercare (KNN + filtri)
- RITORNA già i DETTAGLI COMPLETI dei prodotti nelle risposte del tool di search
- mantiene la history
- NON inventa prodotti: tutto ciò che propone viene dal tool

Requisiti:
  pip install openai redis numpy

Env:
  OPENAI_API_KEY=...
  REDIS_URL=redis://localhost:6379/0
  INDEX_NAME=idx:products
  EMBED_MODEL=text-embedding-3-large
  EMBED_DIM=1024
  # opz: JSON_PREFIX, VEC_PREFIX, LLM_MODEL

Esecuzione:
  python gift_finder_agent.py --session ./session_chat.json
  (comandi: /reset, /quit)
"""

import os
import re
import json
import time
import argparse
from typing import Any, Dict, List, Optional
import numpy as np
import redis

from openai import OpenAI, APIError, APIConnectionError, RateLimitError, BadRequestError
from redis.commands.search.query import Query

# -----------------------------
# Config
# -----------------------------
REDIS_URL  = os.getenv("REDIS_URL", "redis://localhost:6379/0")
INDEX_NAME = os.getenv("INDEX_NAME", "idx:products")
JSON_PREFIX = os.getenv("JSON_PREFIX", "prod:")
VEC_PREFIX  = os.getenv("VEC_PREFIX", "vec:")

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")
EMBED_DIM   = int(os.getenv("EMBED_DIM", "1024"))
LLM_MODEL   = os.getenv("LLM_MODEL", "gpt-4o-mini-2024-07-18")

# -----------------------------
# Utils
# -----------------------------
def sanitize_for_embedding(text: Any, max_chars: int = 12000) -> str:
    s = "" if text is None else str(text)
    s = s.replace("\x00", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        s = s[:max_chars]
    if not s:
        s = "."
    return s

def with_backoff(fn, *, retries: int = 5, base_delay: float = 1.2):
    for i in range(retries):
        try:
            return fn()
        except BadRequestError:
            raise
        except (APIConnectionError, RateLimitError, APIError):
            time.sleep(min(30.0, base_delay * (2 ** i)))
    return fn()

def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()

def _escape_tag(s: str) -> str:
    return s.replace(" ", "\\ ")

def _b(x):
    return x.decode() if isinstance(x, (bytes, bytearray)) else x

def pick_product_fields(j: Dict[str, Any], wanted: Optional[List[str]] = None) -> Dict[str, Any]:
    """Ritorna un sottoinsieme utile del JSON prodotto per non esagerare con la payload size."""
    if not j:
        return {}
    if not wanted:
        wanted = [
            "id","title","description","category","brand","ean","upc","themes",
            "material","material_secondary","made_in","format","binding",
            "dimensions","canonical_text","keywords","topics","attributes_extracted"
        ]
    out = {}
    for k in wanted:
        if k in j:
            out[k] = j[k]
    return out

# -----------------------------
# Redis Tooling
# -----------------------------
class RedisToolbox:
    def __init__(self, redis_url: str, index_name: str):
        self.r = redis.from_url(redis_url, decode_responses=False)
        self.index_name = index_name
        self.client = OpenAI()

    # Embedding query
    def _embed_query(self, query: str) -> bytes:
        query = sanitize_for_embedding(query)
        def _call():
            res = self.client.embeddings.create(
                model=EMBED_MODEL, input=[query], dimensions=EMBED_DIM
            )
            v = np.array(res.data[0].embedding, dtype=np.float32)
            return to_bytes(v)
        return with_backoff(_call)

    # Search KNN + filtri, con DETTAGLI (full JSON ridotto) incorporati
    def search(self,
               query_text: str,
               k: int = 8,
               category: Optional[str] = None,
               brand: Optional[str] = None,
               must_keywords: Optional[List[str]] = None,
               min_price: Optional[float] = None,
               max_price: Optional[float] = None,
               include_details: bool = True,
               detail_fields: Optional[List[str]] = None) -> Dict[str, Any]:

        qvec = self._embed_query(query_text)

        parts = []
        if category:
            parts.append(f'@category:{{{category}}}')
        if brand:
            parts.append(f'@brand:{{{brand}}}')
        if must_keywords:
            safe = [_escape_tag(k) for k in must_keywords]
            parts.append(f'@keywords:{{{"|".join(safe)}}}')
        if (min_price is not None) or (max_price is not None):
            lo = min_price if min_price is not None else "-inf"
            hi = max_price if max_price is not None else "+inf"
            parts.append(f'@price:[{lo} {hi}]')
        fexpr = " ".join(parts) if parts else "*"

        q = (
            Query(f"({fexpr})=>[KNN {k} @embedding $vec AS score]")
            .sort_by("score")
            .paging(0, k)
            .return_fields("code","title","brand","category","keywords","score")
            .dialect(2)
        )
        res = self.r.ft(self.index_name).search(q, query_params={"vec": qvec})

        items = []
        for d in res.docs:
            code = _b(d.code)
            row = {
                "code": code,
                "title": _b(d.title),
                "brand": _b(d.brand) if hasattr(d, "brand") else None,
                "category": _b(d.category) if hasattr(d, "category") else None,
                "score": float(d.score),
            }
            if include_details:
                j = self.r.json().get(f"{JSON_PREFIX}{code}") or {}
                row["product"] = pick_product_fields(j, detail_fields)
            items.append(row)

        return {
            "count": res.total,
            "k": k,
            "filters": {"category": category, "brand": brand, "must_keywords": must_keywords,
                        "min_price": min_price, "max_price": max_price},
            "items": items
        }

    # Get product diretto (utile se l’utente chiede un item specifico separatamente)
    def get_product(self, code: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        if code:
            j = self.r.json().get(f"{JSON_PREFIX}{code}") or {}
            return {"found": bool(j), "by": "code", "code": code, "product": j}
        if title:
            phrase = title.replace('"', '\\"')
            q = Query(f'@title:"{phrase}"').paging(0, 5).return_fields("code","title").dialect(2)
            res = self.r.ft(self.index_name).search(q)
            if res.docs:
                d = res.docs[0]
                code = _b(d.code)
                j = self.r.json().get(f"{JSON_PREFIX}{code}") or {}
                return {"found": True, "by": "title", "code": code, "product": j}
        return {"found": False, "error": "missing code/title or not found"}

# -----------------------------
# Agent (LLM + tool calling)
# -----------------------------
SYSTEM_PROMPT = (
    "Sei GiftFinder, un assistente per scegliere regali.\n"
    "- Parla in ITALIANO, chiaro e concreto.\n"
    "- NON inventare prodotti: proponi SOLO elementi restituiti dal tool di ricerca.\n"
    "- Quando l’utente chiede idee/suggerimenti, chiama SUBITO `search_redis` con include_details=true e mostra 3-5 risultati pertinenti con dettagli utili (dimensioni/materiali/tema/paese).\n"
    "- Se l’utente chiede dettagli su un item, usa i dettagli già inclusi nei risultati; se servisse altro chiama `get_product`.\n"
    "- Fai al massimo 1-2 domande chiarificatrici (budget/destinatario/occasione/interessi), ma non bloccare la proposta iniziale: mostra subito opzioni ragionevoli.\n"
    "- Dopo i risultati, proponi 2-3 filtri rapidi (es. prezzo, colore/tema, dimensioni).\n"
)

def tools_schema() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_redis",
                "description": "Semantic KNN search on Redis vector index with optional filters. Returns top products WITH details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_text": {"type": "string"},
                        "k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8},
                        "category": {"type": "string"},
                        "brand": {"type": "string"},
                        "must_keywords": {"type": "array", "items": {"type": "string"}},
                        "min_price": {"type": "number"},
                        "max_price": {"type": "number"},
                        "include_details": {"type": "boolean", "description": "If true, attach product JSON details.", "default": True},
                        "detail_fields": {"type": "array", "items": {"type": "string"},
                                          "description": "Subset of product fields to return; omit for default useful set."}
                    },
                    "required": ["query_text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_product",
                "description": "Fetch a product full JSON payload from Redis by product code or by exact title.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code":  {"type": "string"},
                        "title": {"type": "string"}
                    },
                    "additionalProperties": False
                }
            }
        }
    ]

class GiftFinderAgent:
    def __init__(self, session_path: Optional[str] = None):
        self.client = OpenAI()
        self.redis = RedisToolbox(REDIS_URL, INDEX_NAME)
        self.messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.session_path = session_path
        self._last_search = None
        self._active_code = None
        self._load_session()

    # ---- persistence ----
    def _load_session(self):
        if self.session_path and os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msgs = data.get("messages")
                if isinstance(msgs, list) and msgs:
                    self.messages = [self.messages[0]] + [m for m in msgs if m.get("role") != "system"]
            except Exception:
                pass

    def _save_session(self):
        if not self.session_path:
            return
        data = {"messages": [m for m in self.messages if m["role"] != "system"]}
        tmp = self.session_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.session_path)

    # ---- tool dispatcher ----
    def _dispatch_tool(self, name: str, arguments: str) -> str:
        try:
            args = json.loads(arguments or "{}")
        except Exception:
            args = {}

        if name == "search_redis":
            result = self.redis.search(
                query_text=args.get("query_text",""),
                k=int(args.get("k", 8)),
                category=args.get("category"),
                brand=args.get("brand"),
                must_keywords=args.get("must_keywords"),
                min_price=args.get("min_price"),
                max_price=args.get("max_price"),
                include_details = bool(args.get("include_details", True)),
                detail_fields  = args.get("detail_fields")
            )
            self._last_search = result
            if result.get("items"):
                self._active_code = result["items"][0]["code"]  # default “focus” sul primo
            return json.dumps(result, ensure_ascii=False)

        if name == "get_product":
            code = args.get("code")
            title = args.get("title")
            if not code and not title:
                return json.dumps({"found": False, "error": "missing code or title"}, ensure_ascii=False)
            result = self.redis.get_product(code=code, title=title)
            if result.get("found") and result.get("code"):
                self._active_code = result["code"]
            return json.dumps(result, ensure_ascii=False)

        return json.dumps({"error": f"Unknown tool {name}"})

    # ---- chat loop ----
    def ask(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})

        while True:
            resp = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=self.messages,
                tools=tools_schema(),
                tool_choice="auto",
                temperature=0.3,
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
                })
                for tc in msg.tool_calls:
                    out = self._dispatch_tool(tc.function.name, tc.function.arguments)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": out
                    })
                continue

            final = msg.content or ""
            self.messages.append({"role": "assistant", "content": final})
            self._save_session()
            return final

    def reset(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._last_search = None
        self._active_code = None
        self._save_session()

# -----------------------------
# REPL
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="GiftFinder Agent (search returns details)")
    ap.add_argument("--session", help="Path file JSON per salvare la conversazione", default=None)
    args = ap.parse_args()

    agent = GiftFinderAgent(session_path=args.session)
    print("🎁 GiftFinder pronto. Scrivi la tua richiesta (digita /reset per azzerare, /quit per uscire).\n")

    while True:
        try:
            user = input("👤 Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!")
            break

        if not user:
            continue
        if user.lower() in ("/quit", "/exit"):
            print("Ciao!")
            break
        if user.lower() == "/reset":
            agent.reset()
            print("↺ Conversazione azzerata.")
            continue

        answer = agent.ask(user)
        print(f"🤖 Assistente: {answer}\n")

if __name__ == "__main__":
    main()

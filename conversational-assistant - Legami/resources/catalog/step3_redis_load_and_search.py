#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: Redis load + vector search (HNSW) with single-product updates
Keyed by product code (configurable)

Comandi:
  load   -> carica/aggiorna prodotti arricchiti (Step 2)
  search -> esegue ricerche KNN + filtri
  delete -> cancella specifici codici dal DB

Esempi:
  # Carica tutto
  python step3_redis_load_and_search.py load \
    --in ./prodotti_enriched.json \
    --redis-url redis://localhost:6379/0 \
    --embed-model text-embedding-3-large --embed-dim 1024

  # Aggiorna SOLO un codice (chiave = id)
  python step3_redis_load_and_search.py load \
    --in ./prodotti_enriched.json \
    --key-field id --keys VCAL250124

  # Chiave = upc, forza re-embed
  python step3_redis_load_and_search.py load \
    --in ./prodotti_enriched.json \
    --key-field upc --keys CAL250124 --force

  # Ricerca
  python step3_redis_load_and_search.py search \
    --query "gift for cat lovers small wall calendar" --k 10

  # Elimina
  python step3_redis_load_and_search.py delete --keys VCAL250124
"""

import os
import re
import json
import argparse
import hashlib
from typing import List, Dict, Any, Iterable, Optional
import numpy as np
import redis

from openai import OpenAI, APIError, APIConnectionError, RateLimitError, BadRequestError
from redis.exceptions import ResponseError
from redis.commands.search.field import TextField, TagField, NumericField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

# ---------- Config di default ----------
REDIS_URL_DEFAULT = os.getenv("REDIS_URL", "redis://localhost:6379/0")
INDEX_NAME_DEFAULT = os.getenv("INDEX_NAME", "idx:products")
JSON_PREFIX = os.getenv("JSON_PREFIX", "prod:")  # JSON per codice prodotto
VEC_PREFIX  = os.getenv("VEC_PREFIX", "vec:")   # HASH indicizzato + embedding

# ---------- I/O ----------
def read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def read_json_array(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    for o in arr:
        yield o

# ---------- Sanitizzazione per embeddings ----------
def sanitize_for_embedding(text: Any, max_chars: int) -> str:
    s = "" if text is None else str(text)
    s = s.replace("\x00", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        s = s[:max_chars]
    if not s:
        s = "."
    return s

def sanitize_batch(texts: List[str], max_chars: int) -> List[str]:
    return [sanitize_for_embedding(t, max_chars) for t in texts]

# ---------- OpenAI helpers con backoff ----------
def with_backoff(fn, *, retries: int = 5, base_delay: float = 1.2):
    import time
    for i in range(retries):
        try:
            return fn()
        except BadRequestError:
            raise
        except (APIConnectionError, RateLimitError, APIError):
            sleep = base_delay * (2 ** i)
            if sleep > 30: sleep = 30
            time.sleep(sleep)
    return fn()

def embed_batch(client: OpenAI, model: str, dim: int, texts: List[str], *,
                max_chars: int, codes: Optional[List[str]] = None) -> np.ndarray:
    cleaned = sanitize_batch(texts, max_chars)

    def _call():
        return client.embeddings.create(model=model, input=cleaned, dimensions=dim)

    try:
        res = with_backoff(_call)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        return vecs
    except BadRequestError as e:
        # Batch fallito -> fallback per-item per isolare input sporchi
        out = []
        for i, t in enumerate(cleaned):
            def _one():
                return client.embeddings.create(model=model, input=[t], dimensions=dim)
            try:
                r = with_backoff(_one)
                out.append(np.array(r.data[0].embedding, dtype=np.float32))
            except BadRequestError as e1:
                code = codes[i] if (codes and i < len(codes)) else f"idx:{i}"
                print(f"[WARN] Skipping item due to invalid input for code={code}: {e1}")
                out.append(np.zeros((dim,), dtype=np.float32))
        return np.vstack(out)

def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()

# ---------- Hash di contenuto ----------
def content_hash(prod: Dict[str, Any], embed_model: str, embed_dim: int) -> str:
    payload = {
        "canonical_text": prod.get("canonical_text") or "",
        "keywords": prod.get("keywords") or [],
        "topics": prod.get("topics") or [],
        "attributes_extracted": prod.get("attributes_extracted") or [],
        "category": prod.get("category") or "",
        "brand": prod.get("brand") or "",
        "price": prod.get("price") if prod.get("price") is not None else "",
        "embed_model": embed_model,
        "embed_dim": embed_dim,
    }
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---------- Redis: indice HNSW ----------
def ensure_index(r: redis.Redis, index_name: str, dim: int):
    ft = r.ft(index_name)
    try:
        ft.info()
        return
    except ResponseError:
        pass

    schema = [
        TextField("code"),       # codice prodotto (chiave)
        TextField("title"),
        TextField("desc"),
        TagField("brand"),
        TagField("category"),
        TagField("keywords"),    # TagField separa per virgole; sfuggire spazi con backslash
        NumericField("price"),
        TextField("content_hash"),
        VectorField("embedding", "HNSW", {
            "TYPE": "FLOAT32",
            "DIM": dim,
            "DISTANCE_METRIC": "COSINE",
            "M": 16,
            "EF_CONSTRUCTION": 200
        }),
    ]
    ft.create_index(
        schema,
        definition=IndexDefinition(prefix=[VEC_PREFIX], index_type=IndexType.HASH)
    )

# ---------- Load (ingest / upsert) ----------
def load_products(
    inp: str,
    redis_url: str,
    index_name: str,
    embed_model: str,
    embed_dim: int,
    batch_size: int,
    key_field: str,
    only_keys: Optional[List[str]],
    skip_unchanged: bool,
    force: bool,
    max_chars: int
):
    in_is_jsonl = inp.lower().endswith(".jsonl")
    reader = read_jsonl if in_is_jsonl else read_json_array
    all_products = list(reader(inp))
    print(f"[LOAD] Read {len(all_products)} products from {inp}")

    def get_code(p: Dict[str, Any]) -> str:
        code = (p.get(key_field) or "").strip()
        if not code:
            code = (p.get("id") or "").strip()
        return code

    if only_keys:
        wanted = set(only_keys)
        products = [p for p in all_products if get_code(p) in wanted]
        print(f"[LOAD] Filtered by keys -> {len(products)} products")
    else:
        products = all_products

    if not products:
        print("[LOAD] No products to process. Exit.")
        return

    r = redis.from_url(redis_url, decode_responses=False)
    ensure_index(r, index_name, embed_dim)
    client = OpenAI()

    # Preleva hash precedente (per skip invariati)
    prev_hashes: Dict[str, str] = {}
    if skip_unchanged and not force:
        pipe = r.pipeline()
        for p in products:
            pipe.hget(f"{VEC_PREFIX}{get_code(p)}", "content_hash")
        res = pipe.execute()
        for p, val in zip(products, res):
            code = get_code(p)
            prev_hashes[code] = val.decode() if isinstance(val, (bytes, bytearray)) else (val or "")

    # Decide chi upsertare e quali embedding servono
    to_upsert: List[Dict[str, Any]] = []
    texts_to_embed: List[str] = []
    idx_map: List[int] = []  # indice nel to_upsert
    for p in products:
        code = get_code(p)
        if not code:
            continue
        chash = content_hash(p, embed_model, embed_dim)
        p["_content_hash_calc"] = chash

        if (skip_unchanged and not force) and prev_hashes.get(code) == chash:
            continue

        canon = p.get("canonical_text") or ""
        if not canon.strip():
            parts = [p.get("title",""), p.get("brand",""), p.get("category",""), p.get("description","")]
            canon = ". ".join([t for t in parts if t])
        canon = sanitize_for_embedding(canon, max_chars)

        has_emb = isinstance(p.get("embedding"), list) and len(p["embedding"]) == embed_dim
        if not has_emb:
            texts_to_embed.append(canon)
            idx_map.append(len(to_upsert))

        to_upsert.append(p)

    print(f"[LOAD] To upsert: {len(to_upsert)} (embedding to compute: {len(texts_to_embed)})")

    # Calcolo embedding mancanti (batch)
    emb_matrix: List[Optional[np.ndarray]] = [None] * len(to_upsert)
    if texts_to_embed:
        for start in range(0, len(texts_to_embed), batch_size):
            chunk = texts_to_embed[start:start+batch_size]
            chunk_codes = [ (get_code(to_upsert[idx_map[start + j]]) or f"row{idx_map[start+j]+1}") for j in range(len(chunk)) ]
            vecs = embed_batch(client, embed_model, embed_dim, chunk, max_chars=max_chars, codes=chunk_codes)
            for j, v in enumerate(vecs):
                pos = idx_map[start + j]
                emb_matrix[pos] = v

    # Scrittura su Redis
    pipe = r.pipeline(transaction=False)
    for i, p in enumerate(to_upsert, 1):
        code = get_code(p)
        chash = p["_content_hash_calc"]

        pj = dict(p)
        pj.pop("_content_hash_calc", None)
        if "embedding" in pj:
            pj.pop("embedding", None)
        r.json().set(f"{JSON_PREFIX}{code}", "$", pj)

        title = (p.get("title") or "").encode()
        desc  = (p.get("description") or "").encode()
        brand = (p.get("brand") or "").encode()
        category = (p.get("category") or "").encode()

        keywords = p.get("keywords") or []
        kw_tag = ",".join([k.replace(" ", "\\ ") for k in keywords]).encode()

        if isinstance(p.get("embedding"), list) and len(p["embedding"]) == embed_dim:
            vec = np.array(p["embedding"], dtype=np.float32)
        else:
            v = emb_matrix[i-1]
            if v is None:
                v = np.zeros((embed_dim,), dtype=np.float32)
            vec = v

        mapping = {
            "code": code.encode(),
            "title": title,
            "desc": desc,
            "brand": brand,
            "category": category,
            "keywords": kw_tag,
            "content_hash": chash.encode(),
            "embedding": to_bytes(vec),
        }
        if p.get("price") is not None:
            mapping["price"] = str(float(p["price"])).encode()

        pipe.hset(f"{VEC_PREFIX}{code}", mapping=mapping)

        if i % 200 == 0:
            pipe.execute()
            print(f"[LOAD] Written {i}/{len(to_upsert)}…")

    pipe.execute()
    print(f"[DONE] Upserted {len(to_upsert)} products into Redis (index={index_name})")

# ---------- Search ----------
def _build_filter(category: Optional[str], brand: Optional[str], must_keywords: Optional[List[str]]) -> str:
    parts = []
    if category:
        parts.append(f'@category:{{{category}}}')
    if brand:
        parts.append(f'@brand:{{{brand}}}')
    if must_keywords:
        safe = [k.replace(" ", "\\ ") for k in must_keywords]
        parts.append(f'@keywords:{{{"|".join(safe)}}}')
    return " ".join(parts) if parts else "*"

def search_products(
    redis_url: str,
    index_name: str,
    embed_model: str,
    embed_dim: int,
    query_text: str,
    k: int,
    category: Optional[str],
    brand: Optional[str],
    must_keywords: Optional[List[str]]
):
    r = redis.from_url(redis_url, decode_responses=False)
    client = OpenAI()

    def _embed():
        res = client.embeddings.create(model=embed_model, input=[query_text], dimensions=embed_dim)
        return np.array(res.data[0].embedding, dtype=np.float32).tobytes()
    qvec = with_backoff(_embed)

    fexpr = _build_filter(category, brand, must_keywords)
    q = (
        Query(f"({fexpr})=>[KNN {k} @embedding $vec AS score]")
        .sort_by("score")
        .paging(0, k)
        .return_fields("code", "title", "brand", "category", "keywords", "score")
        .dialect(2)
    )
    res = r.ft(index_name).search(q, query_params={"vec": qvec})

    out = []
    for d in res.docs:
        code = d.code.decode() if isinstance(d.code, (bytes, bytearray)) else str(d.code)
        j = r.json().get(f"{JSON_PREFIX}{code}") or {}
        out.append({
            "code": code,
            "title": j.get("title"),
            "category": j.get("category"),
            "brand": j.get("brand"),
            "score": float(d.score),
            "keywords": j.get("keywords", []),
            "canonical_text": j.get("canonical_text", "")
        })

    print(json.dumps(out, ensure_ascii=False, indent=2))

# ---------- Delete ----------
def delete_products(redis_url: str, keys: List[str]):
    r = redis.from_url(redis_url, decode_responses=False)
    pipe = r.pipeline()
    for code in keys:
        pipe.delete(f"{JSON_PREFIX}{code}")
        pipe.delete(f"{VEC_PREFIX}{code}")
    pipe.execute()
    print(f"[DELETE] Removed {len(keys)} codes.")

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Step 3: Redis load + vector search (keyed by product code)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_load = sub.add_parser("load", help="Load/update enriched products into Redis")
    ap_load.add_argument("--in", dest="inp", required=True, help="Input file (JSONL or JSON array from Step 2)")
    ap_load.add_argument("--redis-url", default=REDIS_URL_DEFAULT)
    ap_load.add_argument("--index-name", default=INDEX_NAME_DEFAULT)
    ap_load.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-large"))
    ap_load.add_argument("--embed-dim", type=int, default=int(os.getenv("EMBED_DIM", "1024")))
    ap_load.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "64")))
    ap_load.add_argument("--key-field", choices=["id", "upc", "ean"], default=os.getenv("KEY_FIELD", "id"),
                         help="Campo da usare come chiave Redis (default: id)")
    ap_load.add_argument("--keys", nargs="*", help="Aggiorna solo questi codici (secondo --key-field)")
    ap_load.add_argument("--skip-unchanged", action="store_true", default=True, help="Salta i record invariati (default: on)")
    ap_load.add_argument("--force", action="store_true", help="Ignora content_hash e sovrascrivi")
    ap_load.add_argument("--max-chars", type=int, default=int(os.getenv("MAX_CHARS", "12000")),
                         help="Max caratteri per l'input embedding (default: 12000)")

    ap_search = sub.add_parser("search", help="Semantic search via Redis")
    ap_search.add_argument("--query", required=True)
    ap_search.add_argument("--k", type=int, default=10)
    ap_search.add_argument("--redis-url", default=REDIS_URL_DEFAULT)
    ap_search.add_argument("--index-name", default=INDEX_NAME_DEFAULT)
    ap_search.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-large"))
    ap_search.add_argument("--embed-dim", type=int, default=int(os.getenv("EMBED_DIM", "1024")))
    ap_search.add_argument("--category")
    ap_search.add_argument("--brand")
    ap_search.add_argument("--kw", nargs="*", help="List of required keywords (Tag OR)")

    ap_delete = sub.add_parser("delete", help="Delete products by code")
    ap_delete.add_argument("--redis-url", default=REDIS_URL_DEFAULT)
    ap_delete.add_argument("--keys", nargs="+", required=True, help="Codes to delete")

    args = ap.parse_args()

    if args.cmd == "load":
        load_products(
            inp=args.inp,
            redis_url=args.redis_url,
            index_name=args.index_name,
            embed_model=args.embed_model,
            embed_dim=args.embed_dim,
            batch_size=args.batch_size,
            key_field=args.key_field,
            only_keys=args.keys,
            skip_unchanged=args.skip_unchanged and (not args.force),
            force=args.force,
            max_chars=args.max_chars
        )
    elif args.cmd == "search":
        search_products(
            redis_url=args.redis_url,
            index_name=args.index_name,
            embed_model=args.embed_model,
            embed_dim=args.embed_dim,
            query_text=args.query,
            k=args.k,
            category=args.category,
            brand=args.brand,
            must_keywords=args.kw
        )
    elif args.cmd == "delete":
        delete_products(
            redis_url=args.redis_url,
            keys=args.keys
        )

if __name__ == "__main__":
    main()

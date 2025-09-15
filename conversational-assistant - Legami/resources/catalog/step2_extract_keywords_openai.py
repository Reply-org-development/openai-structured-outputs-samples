#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2 (parallel): Semantic enrichment with OpenAI
- Forces EN output (keywords/topics/attributes/occasions/audience/negatives + canonical_summary_en)
- Parallel OpenAI calls (concurrency configurable)
- Chat Completions + JSON Schema (Structured Outputs)
- Single embeddings call per product for keyword re-scoring
- Optional canonical_text embedding (debug/small sets)

Usage:
  pip install openai numpy
  export OPENAI_API_KEY=sk-...

  python step2_extract_keywords_openai.py \
    --in ./prodotti.jsonl \
    --out ./prodotti_enriched.jsonl \
    --out-format jsonl \
    --llm-model gpt-4o-mini \
    --embed-model text-embedding-3-large \
    --embed-dim 1024 \
    --topk 16 \
    --min-sim 0.25 \
    --concurrency 6 \
    --target-lang en
"""

import os
import re
import json
import time
import argparse
from typing import Dict, Any, List, Iterable, Optional
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI, APIError, APIConnectionError, RateLimitError, BadRequestError

# -----------------------------
# Text utilities
# -----------------------------
WS_RE = re.compile(r"\s+")
TRAIL_PUNCT_RE = re.compile(r"^[\s,.;:!?]+|[\s,.;:!?]+$")

def clean_token(s: str) -> str:
    t = TRAIL_PUNCT_RE.sub("", WS_RE.sub(" ", str(s))).strip().lower()
    return t

def clean_list(xs: Iterable[str]) -> List[str]:
    out, seen = [], set()
    for x in xs or []:
        t = clean_token(x)
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            out.append(t)
    return out

def shorten_measure(s: str) -> str:
    if not s:
        return s
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)(?:\s*cm)?\s*$", s.strip())
    if m:
        a, b = m.group(1).replace(",", "."), m.group(2).replace(",", ".")
        return f"{a} x {b} cm"
    return s

# -----------------------------
# I/O helpers
# -----------------------------
def read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def read_json_array(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    for obj in arr:
        yield obj

def write_jsonl_stream(path: str, objs: Iterable[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

def write_json_array(path: str, objs: List[Dict[str, Any]], pretty: bool):
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(objs, f, ensure_ascii=False, indent=2)
        else:
            json.dump(objs, f, ensure_ascii=False)

# -----------------------------
# Backoff
# -----------------------------
def with_backoff(fn, *, retries: int = 5, base_delay: float = 1.2):
    for i in range(retries):
        try:
            return fn()
        except BadRequestError:
            raise
        except (APIConnectionError, RateLimitError, APIError):
            sleep = base_delay * (2 ** i) * (1.0 + 0.25 * np.random.rand())
            time.sleep(min(30.0, sleep))
    return fn()

# -----------------------------
# Build product context (source can be IT/ES/etc.)
# -----------------------------
def build_product_text(prod: Dict[str, Any]) -> str:
    parts = []
    title = prod.get("title") or ""
    category = prod.get("category") or ""
    brand = prod.get("brand") or ""
    themes = prod.get("themes") or ""
    material = prod.get("material") or ""
    material2 = prod.get("material_secondary") or ""
    made_in = prod.get("made_in") or ""
    fmt = shorten_measure(prod.get("format") or "")
    binding = prod.get("binding") or ""
    desc = prod.get("description") or ""

    if title: parts.append(title)
    if brand: parts.append(f"Brand: {brand}")
    if category: parts.append(f"Categoria: {category}")
    if themes: parts.append(f"Temi: {themes}")
    if material: parts.append(f"Materiale: {material}")
    if material2: parts.append(f"Materiale secondario: {material2}")
    if fmt: parts.append(f"Formato: {fmt}")
    if binding: parts.append(f"Rilegatura: {binding}")
    if made_in: parts.append(f"Made in: {made_in}")
    if desc: parts.append(desc)

    dims = prod.get("dimensions") or {}
    w, h, d, wgt = dims.get("width"), dims.get("height"), dims.get("depth"), dims.get("weight_g")
    dim_parts = []
    if w: dim_parts.append(f"larghezza={w}")
    if h: dim_parts.append(f"altezza={h}")
    if d: dim_parts.append(f"profondità={d}")
    if wgt: dim_parts.append(f"peso_g={wgt}")
    if dim_parts:
        parts.append("Dimensioni: " + ", ".join(dim_parts))

    return ". ".join([p for p in parts if p])

# -----------------------------
# LLM extraction (Chat Completions + JSON Schema), forced English
# -----------------------------
def extract_llm_fields(client: OpenAI, model: str, text: str, target_lang: str = "en") -> Dict[str, Any]:
    model = os.getenv("OPENAI_LLM_MODEL", model) or model
    if model == "gpt-4o-mini":
        model = "gpt-4o-mini-2024-07-18"

    schema = {
        "name": "ProductKeywords",
        "schema": {
            "type": "object",
            "properties": {
                "keyphrases": {"type": "array", "items": {"type": "string"}},
                "topics": {"type": "array", "items": {"type": "string"}},
                "attributes": {"type": "array", "items": {"type": "string"}},
                "occasions": {"type": "array", "items": {"type": "string"}},
                "audience": {"type": "array", "items": {"type": "string"}},
                "negatives": {"type": "array", "items": {"type": "string"}},
                "canonical_summary_en": {"type": "string"}
            },
            "required": ["keyphrases","topics","attributes","occasions","audience","negatives","canonical_summary_en"],
            "additionalProperties": False
        }
    }

    sys = (
        "You are a product keyword extractor and normalizer. "
        "Always respond in ENGLISH ({lang}), even if the input is in another language. "
        "Return ONLY valid JSON following the provided schema. "
        "Rules: keep keyphrases short (1-4 words), specific, non-redundant; no SKUs/IDs; no invented attributes; "
        "avoid brand names unless clearly part of the product name; use neutral consumer terminology."
    ).format(lang=target_lang)

    def _call():
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": f"Product text:\n{text}\n\nExtract the required fields in English."}
            ],
            response_format={"type": "json_schema", "json_schema": schema},
            temperature=0.0
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)

        def _clean(xs):
            out, seen = [], set()
            for x in xs or []:
                s = re.sub(r"\s+", " ", str(x)).strip().strip(",.;:!?").lower()
                if len(s) >= 2 and s not in seen:
                    seen.add(s); out.append(s)
            return out

        return {
            "keyphrases": _clean(data.get("keyphrases", [])),
            "topics": _clean(data.get("topics", [])),
            "attributes": _clean(data.get("attributes", [])),
            "occasions": _clean(data.get("occasions", [])),
            "audience": _clean(data.get("audience", [])),
            "negatives": _clean(data.get("negatives", [])),
            "canonical_summary_en": (data.get("canonical_summary_en") or "").strip()
        }

    return with_backoff(_call)

# -----------------------------
# Embeddings + cosine re-scoring
# (single call: [doc_text] + candidates)
# -----------------------------
def embed_openai(client: OpenAI, model: str, dim: int, texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)
    def _call():
        res = client.embeddings.create(model=model, input=texts, dimensions=dim)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        return vecs
    return with_backoff(_call)

def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    return a @ b.T

def rescore_keywords_single_call(client: OpenAI,
                                 embed_model: str,
                                 embed_dim: int,
                                 product_base_text: str,
                                 candidates: List[str],
                                 top_k: int,
                                 min_sim: float) -> List[str]:
    if not candidates:
        return []
    inputs = [product_base_text] + candidates
    vecs = embed_openai(client, embed_model, embed_dim, inputs)  # [1+N, D]
    doc_vec = vecs[0:1, :]                                      # [1,D]
    cand_vecs = vecs[1:, :]                                     # [N,D]
    sims = cosine(cand_vecs, doc_vec).flatten()                  # [N]
    ranked = sorted(zip(candidates, sims), key=lambda x: x[1], reverse=True)
    filtered = [k for k, s in ranked if s >= min_sim]
    return (filtered[:top_k] or [k for k, _ in ranked[:min(top_k, len(ranked))]])

# -----------------------------
# Canonical text (English)
# -----------------------------
def canonical_text_en(canonical_summary_en: str,
                      kws: List[str],
                      topics: List[str],
                      attrs: List[str]) -> str:
    parts = []
    if canonical_summary_en:
        parts.append(canonical_summary_en)
    extra = []
    if topics:
        extra.append("Topics: " + ", ".join(topics[:6]))
    if attrs:
        extra.append("Attributes: " + ", ".join(attrs[:8]))
    if kws:
        extra.append("Keywords: " + ", ".join(kws[:16]))
    if extra:
        parts.append(". ".join(extra))
    return ". ".join([p for p in parts if p])

# -----------------------------
# Per-product pipeline (thread-safe)
# -----------------------------
def enrich_product(client: OpenAI,
                   llm_model: str,
                   embed_model: str,
                   embed_dim: int,
                   prod: Dict[str, Any],
                   topk: int,
                   min_sim: float,
                   include_embedding: bool,
                   target_lang: str) -> Dict[str, Any]:
    # 1) Context
    text = build_product_text(prod)

    # 2) LLM extraction (EN)
    fields = extract_llm_fields(client, llm_model, text, target_lang=target_lang)

    # 3) Re-score keywords with single embeddings call
    base_for_rescore = ". ".join([t for t in [
        prod.get("title") or "",
        prod.get("brand") or "",
        prod.get("category") or "",
        prod.get("themes") or "",
        shorten_measure(prod.get("format") or ""),
        prod.get("binding") or "",
        prod.get("material") or "",
        prod.get("description") or ""
    ] if t])
    keyphrases = rescore_keywords_single_call(
        client, embed_model, embed_dim, base_for_rescore, fields["keyphrases"], topk, min_sim
    )

    # 4) Canonical text EN
    canon = canonical_text_en(fields.get("canonical_summary_en", ""), keyphrases, fields["topics"], fields["attributes"])

    enriched = dict(prod)
    enriched["keywords"] = keyphrases
    enriched["topics"] = fields["topics"]
    enriched["attributes_extracted"] = fields["attributes"]
    enriched["occasions"] = fields["occasions"]
    enriched["audience"] = fields["audience"]
    enriched["negatives"] = fields["negatives"]
    enriched["canonical_text"] = canon
    enriched["embedding_model"] = embed_model
    enriched["embedding_dimensions"] = embed_dim

    if include_embedding:
        # optional extra call (kept separate to not inflate the joint call above)
        vec = embed_openai(client, embed_model, embed_dim, [canon])[0]
        enriched["embedding"] = [float(x) for x in vec.tolist()]

    return enriched

# -----------------------------
# Main (parallel)
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Step 2 (parallel): OpenAI semantic enrichment in EN + canonical_text")
    ap.add_argument("--in", dest="inp", required=True, help="Input file (JSONL or JSON array from Step 1)")
    ap.add_argument("--out", dest="out", required=True, help="Output file (JSONL or JSON array)")
    ap.add_argument("--out-format", choices=["jsonl", "json"], default=None,
                    help="Output format; if omitted, inferred from extension")
    ap.add_argument("--llm-model", default=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
                    help="OpenAI model for extraction (Chat Completions + JSON Schema)")
    ap.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-large"),
                    help="OpenAI embeddings model")
    ap.add_argument("--embed-dim", type=int, default=int(os.getenv("EMBED_DIM", "1024")),
                    help="Embedding dimensions (supported by model)")
    ap.add_argument("--topk", type=int, default=int(os.getenv("TOP_K_KEYWORDS", "16")),
                    help="Max number of keywords after re-scoring")
    ap.add_argument("--min-sim", type=float, default=float(os.getenv("MIN_SIM", "0.25")),
                    help="Cosine similarity threshold to keep a keyword")
    ap.add_argument("--include-embedding", action="store_true",
                    help="If set, also computes and stores canonical_text embedding (heavier output)")
    ap.add_argument("--pretty", action="store_true", help="Pretty print (only for JSON output)")
    ap.add_argument("--concurrency", type=int, default=int(os.getenv("CONCURRENCY", "50")),
                    help="Number of parallel workers (default: 50)")
    ap.add_argument("--target-lang", default=os.getenv("TARGET_LANG", "en"),
                    help="Target language for extraction (default: en)")
    args = ap.parse_args()

    # Infer formats
    in_is_jsonl = args.inp.lower().endswith(".jsonl")
    if args.out_format:
        out_is_jsonl = (args.out_format == "jsonl")
    else:
        out_is_jsonl = args.out.lower().endswith(".jsonl")

    client = OpenAI()

    # Read all inputs (for streaming JSONL you could refactor to chunked reading)
    reader = read_jsonl if in_is_jsonl else read_json_array
    products = list(reader(args.inp))
    n = len(products)
    print(f"[INFO] Loaded {n} products. Running with concurrency={args.concurrency}")

    results: List[Optional[Dict[str, Any]]] = [None] * n

    def _task(idx: int, prod: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return enrich_product(
                client=client,
                llm_model=args.llm_model,
                embed_model=args.embed_model,
                embed_dim=args.embed_dim,
                prod=prod,
                topk=args.topk,
                min_sim=args.min_sim,
                include_embedding=args.include_embedding,
                target_lang=args.target_lang
            )
        except Exception as e:
            return {**prod, "_error": f"{type(e).__name__}: {e}"}

    # Parallel execution
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(_task, i, p): i for i, p in enumerate(products)}
        completed = 0
        if out_is_jsonl:
            # Stream to JSONL as they complete (reduced memory)
            with open(args.out, "w", encoding="utf-8") as fw:
                for fut in as_completed(futures):
                    i = futures[fut]
                    obj = fut.result()
                    fw.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    completed += 1
                    if completed % 50 == 0:
                        print(f"[PROGRESS] {completed}/{n} done")
        else:
            # Collect then write a JSON array
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
                completed += 1
                if completed % 50 == 0:
                    print(f"[PROGRESS] {completed}/{n} done")

    # Write JSON array if requested
    if not out_is_jsonl:
        arr = [r for r in results if r is not None]
        write_json_array(args.out, arr, pretty=args.pretty)

    print(f"[DONE] Enriched {n} products -> {args.out}")

if __name__ == "__main__":
    main()

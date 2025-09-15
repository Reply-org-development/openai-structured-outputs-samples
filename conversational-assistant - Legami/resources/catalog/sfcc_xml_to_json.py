#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SFCC (Demandware) Catalog XML -> JSON normalizzato per prodotto.

Caratteristiche:
- Parsing con namespace: http://www.demandware.com/xml/impex/catalog/2006-10-31
- Supporto campi localizzati (xml:lang) per display-name, short/long-description e custom-attribute
- Normalizzazione HTML (rimozione tag, unescape, whitespace)
- Derivazione campi utili: category (da tipologia/serieMerceologica/eventoCommerciale), themes, material, made_in, format, binding
- Estrazione dimensioni (dimWidth, dimHeight, dimDepth, dimWeight)
- Flag booleane online/searchable, tax_class, ean, upc
- Output JSONL o JSON array

Uso:
    pip install lxml
    python sfcc_xml_to_json.py --xml ./catalog.xml --out ./prodotti.jsonl --format jsonl --lang it en x-default es fr de

Se preferisci un array JSON:
    python sfcc_xml_to_json.py --xml ./catalog.xml --out ./prodotti.json --format json
"""

import argparse
import json
import sys
import html
import re
import hashlib
from typing import Dict, Any, List, Optional
from lxml import etree

# Namespace SFCC + xml:lang
NS = {
    "dwc": "http://www.demandware.com/xml/impex/catalog/2006-10-31",
    "xml": "http://www.w3.org/XML/1998/namespace"
}

# ---------- Utilità di pulizia testo ----------

TAG_RE = re.compile(r"<[^>]+>")

def strip_html(x: Optional[str]) -> str:
    if not x:
        return ""
    s = html.unescape(x)
    s = TAG_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def to_bool(s: Optional[str]) -> Optional[bool]:
    if s is None:
        return None
    v = s.strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return None

def safe_first(d: Dict[str, Dict[str, str]], key: str, lang_priority: List[str]) -> str:
    """Prende un valore da custom_attributes (mappa lang->valore) rispettando la priorità lingue."""
    if key not in d:
        return ""
    obj = d[key]
    for lang in lang_priority:
        if lang in obj and obj[lang]:
            return obj[lang]
    # fallback: qualunque non vuoto
    for v in obj.values():
        if v:
            return v
    return ""

def pick_localized(elems: List[etree._Element], lang_priority: List[str]) -> str:
    by_lang: Dict[str, str] = {}
    for el in elems:
        lang = el.get(f"{{{NS['xml']}}}lang")
        txt = strip_html(el.text or "")
        if lang:
            by_lang.setdefault(lang.lower(), txt)
        elif txt:
            # se non ha lang, consideralo x-default
            by_lang.setdefault("x-default", txt)
    for lang in lang_priority:
        if lang in by_lang and by_lang[lang]:
            return by_lang[lang]
    # fallback qualsiasi non vuoto
    for v in by_lang.values():
        if v:
            return v
    return ""

# ---------- Parser principale ----------

def parse_sfcc(xml_path: str, lang_priority: List[str]) -> List[Dict[str, Any]]:
    parser = etree.XMLParser(remove_blank_text=True, recover=True, encoding="utf-8")
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    products: List[Dict[str, Any]] = []

    for p in root.findall(".//dwc:product", namespaces=NS):
        # ID prodotto
        pid = p.get("product-id")
        if not pid:
            # fallback: se non presente, prova id interno o genera hash deterministico
            # (in SFCC normalmente c'è product-id)
            dn_all = p.findall("dwc:display-name", namespaces=NS)
            ld_all = p.findall("dwc:long-description", namespaces=NS)
            sd_all = p.findall("dwc:short-description", namespaces=NS)
            title_tmp = pick_localized(dn_all, lang_priority) or pick_localized(sd_all, lang_priority) or pick_localized(ld_all, lang_priority)
            basis = (title_tmp or "")[:80]
            pid = hashlib.md5(basis.encode("utf-8")).hexdigest()

        # Localizzati
        display_all = p.findall("dwc:display-name", namespaces=NS)
        short_all   = p.findall("dwc:short-description", namespaces=NS)
        long_all    = p.findall("dwc:long-description", namespaces=NS)

        title = pick_localized(display_all, lang_priority)
        short_desc = pick_localized(short_all, lang_priority)
        long_desc  = pick_localized(long_all, lang_priority)
        description = long_desc or short_desc

        # Se il title è vuoto, prova a derivarlo dalla descrizione
        if not title:
            title = (description[:120] + "…") if len(description) > 120 else description

        # Custom attributes: mappa attribute-id -> {lang: value}
        custom_attrs: Dict[str, Dict[str, str]] = {}
        for ca in p.findall(".//dwc:custom-attributes/dwc:custom-attribute", namespaces=NS):
            attr_id = ca.get("attribute-id")
            if not attr_id:
                continue
            lang = (ca.get(f"{{{NS['xml']}}}lang") or "x-default").lower()
            val = strip_html(ca.text or "")
            # registra solo se c'è un valore non vuoto
            if val:
                custom_attrs.setdefault(attr_id, {})
                # se il lang esiste già e siamo in conflitto, mantieni il primo non vuoto
                if lang not in custom_attrs[attr_id]:
                    custom_attrs[attr_id][lang] = val

        # Campi base
        ean = strip_html((p.findtext("dwc:ean", namespaces=NS) or ""))
        upc = strip_html((p.findtext("dwc:upc", namespaces=NS) or ""))

        # Flag e tassazione
        # Attenzione: in alcuni XML certe flag possono comparire duplicate: prendiamo la prima significativa
        def first_text(tag: str) -> Optional[str]:
            for el in p.findall(f"dwc:{tag}", namespaces=NS):
                txt = strip_html(el.text or "")
                if txt != "":
                    return txt
            return None

        online_flag      = to_bool(first_text("online-flag"))
        available_flag   = to_bool(first_text("available-flag"))
        searchable_flag  = to_bool(first_text("searchable-flag"))
        tax_class        = strip_html(first_text("tax-class-id") or "")

        # Derivati da custom-attributes con priorità di lingua
        category   = safe_first(custom_attrs, "tipologia", lang_priority)
        if not category:
            category = safe_first(custom_attrs, "serieMerceologica", lang_priority) or safe_first(custom_attrs, "eventoCommerciale", lang_priority)

        themes     = safe_first(custom_attrs, "temi", lang_priority)
        made_in    = safe_first(custom_attrs, "made_in", lang_priority)
        material   = safe_first(custom_attrs, "materiale", lang_priority)
        material2  = safe_first(custom_attrs, "materialeSecondario", lang_priority)
        formato    = safe_first(custom_attrs, "formato", lang_priority)
        binding    = safe_first(custom_attrs, "rilegatura", lang_priority)

        dim_w      = safe_first(custom_attrs, "dimWidth", lang_priority)
        dim_h      = safe_first(custom_attrs, "dimHeight", lang_priority)
        dim_d      = safe_first(custom_attrs, "dimDepth", lang_priority)
        dim_weight = safe_first(custom_attrs, "dimWeight", lang_priority)

        # Brand: se fisso (es. Legami), puoi valorizzarlo qui; altrimenti lascia vuoto
        brand = ""

        prod: Dict[str, Any] = {
            "id": pid,
            "title": title or "",
            "description": description or "",
            "category": category or "",
            "brand": brand,
            "ean": ean,
            "upc": upc,
            "themes": themes or "",
            "material": material or "",
            "material_secondary": material2 or "",
            "made_in": made_in or "",
            "format": formato or "",
            "binding": binding or "",
            "online": online_flag,
            "available": available_flag,
            "searchable": searchable_flag,
            "tax_class": tax_class or "",
            "dimensions": {
                "width": dim_w or "",
                "height": dim_h or "",
                "depth": dim_d or "",
                "weight_g": dim_weight or ""
            },
            # Manteniamo tutti i custom attributes multi-lingua per usi futuri (estrazione keyword, tassonomia, ecc.)
            "custom_attributes": custom_attrs
        }

        products.append(prod)

    return products

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="Converti XML SFCC (Demandware) in JSON normalizzato per prodotto.")
    ap.add_argument("--xml", required=True, help="Percorso al file XML (catalogo SFCC)")
    ap.add_argument("--out", required=True, help="File di output (.jsonl o .json)")
    ap.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Formato di output (default: jsonl)")
    ap.add_argument("--lang", nargs="+", default=["it", "en", "x-default", "es", "fr", "de"],
                    help="Priorità di lingue per i campi localizzati (default: it en x-default es fr de)")
    ap.add_argument("--pretty", action="store_true", help="Pretty print (solo per formato json)")
    args = ap.parse_args()

    products = parse_sfcc(args.xml, args.lang)

    if args.format == "jsonl":
        with open(args.out, "w", encoding="utf-8") as f:
            for p in products:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            if args.pretty:
                json.dump(products, f, ensure_ascii=False, indent=2)
            else:
                json.dump(products, f, ensure_ascii=False)

    print(f"[DONE] Prodotti esportati: {len(products)} → {args.out}")

if __name__ == "__main__":
    main()

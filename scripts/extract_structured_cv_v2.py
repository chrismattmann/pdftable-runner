#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust extractor for Publications / Presentations from cv_out/combined.json
- Works with pages[*].text_lines (list[str]) OR pages[*].lines (list[dict/text])
- Splits on numbered items like "123. ..."
- Classifies pubs vs talks with keyword heuristics
- Flags invited/keynote talks
- Writes a compact JSON with stats
"""

import argparse, json, re, sys
from pathlib import Path

PUB_KW = r'journal|proceedings|trans\.|transactions|arxiv|doi|volume|vol\.|issue|pages|ieee|acm|springer|elsevier|proc\.|conference|symposium|workshop|letter\b|letters\b|book|chapter'
TALK_KW = r'keynote|invited|talk|presentation|colloquium|seminar|panel|guest lecture|lecture|webinar|tutorial|debate'
MEDIA_NOISE = r'press|news|podcast|article|interview|media|blog|op[- ]?ed'

def load_lines(path: Path):
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    lines = []

    # Support dict schema with "pages"
    if isinstance(data, dict) and 'pages' in data:
        for p in data['pages']:
            # 1) preferred: text_lines: list[str]
            tl = p.get('text_lines')
            if isinstance(tl, list) and tl and isinstance(tl[0], str):
                lines.extend(tl)
                continue
            # 2) alt: text_lines: list[dict{text:..}]
            if isinstance(tl, list) and tl and isinstance(tl[0], dict):
                lines.extend([(x.get('text') or '').strip() for x in tl])
                continue
            # 3) alt: lines: list[str] or list[dict{text}]
            alt = p.get('lines') or []
            if alt and isinstance(alt[0], dict):
                lines.extend([(x.get('text') or '').strip() for x in alt])
            else:
                lines.extend([str(x).strip() for x in alt])
        return lines

    # Support list-of-pages schema
    if isinstance(data, list):
        for p in data:
            tl = p.get('text_lines') if isinstance(p, dict) else None
            if isinstance(tl, list) and tl and isinstance(tl[0], str):
                lines.extend(tl)
                continue
            if isinstance(tl, list) and tl and isinstance(tl[0], dict):
                lines.extend([(x.get('text') or '').strip() for x in tl])
                continue
            alt = (p.get('lines') if isinstance(p, dict) else []) or []
            if alt and isinstance(alt[0], dict):
                lines.extend([(x.get('text') or '').strip() for x in alt])
            else:
                lines.extend([str(x).strip() for x in alt])
        return lines

    # Fallback: treat file as a bare list of strings
    if isinstance(data, list):
        return [str(x).strip() for x in data]

    raise SystemExit("Unsupported JSON structure for combined.json")

def parse_index_and_rest(entry: str):
    m = re.match(r'^\s*(\d+)\.\s*(.*)', entry, flags=re.S)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, entry.strip()

def parse_year(s: str):
    m = re.search(r'\b(19|20)\d{2}\b', s)
    return int(m.group(0)) if m else None

def parse_title(s: str):
    # Prefer quoted titles
    m = re.search(r'“([^”]+)”|"([^"]+)"', s)
    if m:
        return (m.group(1) or m.group(2)).strip()
    # Fallback: sentence after authors (authors usually end at first period)
    parts = s.split('.')
    if len(parts) >= 2:
        return parts[1].strip()
    return s[:200].strip()

def parse_authors(s: str):
    return s.split('.')[0].strip() if '.' in s else None

def parse_venue(s: str, title: str | None):
    after = s
    if title and title in s:
        after = s.split(title, 1)[1]
    # Try "In <VENUE>"
    m = re.search(r'\bIn\b\s+([^.,\n]+)', after)
    if m:
        return m.group(1).strip()
    # Otherwise, take a capitalized phrase before year/date
    m2 = re.search(r',\s*([^,]+?)(?:,\s*(?:[A-Z][a-z]+\s+\d{1,2},\s*\d{4}|\d{4}))', after)
    if m2:
        return m2.group(1).strip()
    return None

def is_media_noise(s: str):
    return re.search(MEDIA_NOISE, s, re.I) is not None

def classify(entry_lower: str):
    is_talk = re.search(TALK_KW, entry_lower) is not None and not re.search(r'proceedings|conference|journal', entry_lower)
    is_pub  = re.search(PUB_KW, entry_lower)  is not None
    if is_talk and not is_pub:
        return "talk"
    if is_pub:
        return "pub"
    return "unknown"

def main(in_path: Path, out_path: Path):
    lines = [ln for ln in load_lines(in_path) if ln]
    text = "\n".join(lines).replace('“','"').replace('”','"').replace("’","'")

    # Break into numbered entries (e.g., "123. ...")
    chunks = re.split(r'\n(?=\d+\.\s)', text)
    numbered = [c.strip() for c in chunks if re.match(r'^\d+\.\s', c.strip())]

    pubs, talks, unknown = [], [], []

    for e in numbered:
        idx, rest = parse_index_and_rest(e)
        if not rest or is_media_noise(rest):
            continue

        cls = classify(rest.lower())
        title  = parse_title(rest)
        year   = parse_year(rest)
        authors= parse_authors(rest)
        venue  = parse_venue(rest, title)
        invited = bool(re.search(r'\b(invited|keynote)\b', rest, re.I))

        obj = {
            "index": idx,
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": year,
            "invited": invited,
            "raw": rest
        }

        if cls == "pub":
            pubs.append(obj)
        elif cls == "talk":
            talks.append(obj)
        else:
            unknown.append(obj)

    invited_talks = [t for t in talks if t["invited"]]

    out = {
        "stats": {
            "total_numbered_items": len(numbered),
            "publications": len(pubs),
            "talks": len(talks),
            "invited_talks": len(invited_talks),
            "unknown": len(unknown),
        },
        "publications": pubs,
        "presentations": talks,
        "invited_talks": invited_talks,
        # uncomment if you want to debug:
        # "unknown": unknown[:50]
    }

    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote {out_path}  (pubs={len(pubs)}, talks={len(talks)}, invited={len(invited_talks)}, unknown={len(unknown)})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("combined_json", type=Path)
    ap.add_argument("--out", type=Path, default=Path("cv_structured.json"))
    args = ap.parse_args()
    main(args.combined_json, args.out)

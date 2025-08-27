#!/usr/bin/env python3
import argparse, json, re, sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

HEADING_RE = re.compile(r"""(?im)^\s*
    (publications|refereed\s+publications|selected\s+publications|peer[-\s]?reviewed
    |conference\s+papers|journal\s+articles
    |presentations|talks|invited\s+talks|invited\s+presentations|keynotes|seminars|colloquia?)
    \s*:?\s*$""", re.X)

BULLET_RE = re.compile(r"""^\s*(?:[-*•–—]|(\d+\.|\[\d+\]))\s+""")
MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_RE = re.compile(rf"(?i)\b((?:{MONTHS})\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})\b")

# --- Utilities ---------------------------------------------------------------

def load_export_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    # supports {"pages":[{"page":1,"text":"..."}]} as produced earlier
    if isinstance(data, dict) and "pages" in data:
        return "\n\n".join(p.get("text","") for p in data["pages"])
    # fallback: raw text
    if isinstance(data, str):
        return data
    raise ValueError("Unsupported export JSON format")

def dehyphenate_and_reflow(text: str) -> str:
    # normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # fix hyphenation at EOL: "foo-\nbar" -> "foobar"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    lines = text.split("\n")
    out: List[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf.strip():
            out.append(buf.strip())
        buf = ""

    for i, line in enumerate(lines):
        nxt = lines[i+1] if i + 1 < len(lines) else ""
        s = line.rstrip()

        # hard paragraph break?
        if not s.strip():
            flush()
            continue

        # bullet/numbered start → start new item
        if BULLET_RE.match(s):
            flush()
            buf = s
            # if next is continuation (indented/no bullet), we’ll merge below
            continue

        # decide whether to join with previous buffer or start new paragraph
        if not buf:
            buf = s
            continue

        # If buffer looks like a heading (short, titlecased/caps), break
        if is_heading_like(buf):
            flush()
            buf = s
            continue

        # If previous line clearly ends a sentence / clause, start new para
        if re.search(r"[.!?:;»”\"]\s*$", buf):
            flush()
            buf = s
            continue

        # If next line is a bullet or a heading, keep current and start new
        if BULLET_RE.match(nxt) or is_heading_like(nxt):
            flush()
            buf = s
            continue

        # Default: soft-wrap join
        buf += " " + s.lstrip()

    flush()
    return "\n".join(out)

def is_heading_like(s: str) -> bool:
    s_clean = s.strip().strip(":")
    if len(s_clean.split()) <= 6 and (s_clean.isupper() or s_clean.istitle()):
        # But don’t treat obvious sentences as headings
        if not re.search(r"[.!?]$", s_clean):
            # also match our known headings
            if HEADING_RE.match(s_clean) or re.search(r"(?i)\b(publications|talks|presentations)\b", s_clean):
                return True
    return False

def split_sections(text: str) -> Dict[str, List[str]]:
    # Walk paragraphs, track current section by last heading encountered
    sections: Dict[str, List[str]] = {}
    current = "other"
    for para in text.split("\n"):
        m = HEADING_RE.match(para)
        if m:
            current = m.group(1).lower()
            sections.setdefault(current, [])
            continue
        if para.strip():
            sections.setdefault(current, []).append(para)
    return sections

def section_items(paragraphs: List[str]) -> List[str]:
    """Flatten bullets & merge wrapped lines into per-item strings."""
    items: List[str] = []
    buf = ""
    for p in paragraphs:
        if BULLET_RE.match(p):
            if buf.strip():
                items.append(buf.strip())
            buf = BULLET_RE.sub("", p).strip()
        else:
            # continuation of previous bullet / wrapped line
            if buf:
                # join if not clearly ending
                if not re.search(r"[.!?]\s*$", buf):
                    buf += " " + p.strip()
                else:
                    items.append(buf.strip())
                    buf = p.strip()
            else:
                buf = p.strip()
    if buf.strip():
        items.append(buf.strip())
    # minor tidy
    return [re.sub(r"\s{2,}", " ", x).strip("•-–— ").strip() for x in items]

# --- Publication parsing -----------------------------------------------------

PUB_PATTERNS = [
    # APA-ish: Authors. (Year). Title. Venue, Vol(Issue), pages. DOI
    re.compile(r"""^(?P<authors>.+?)\s*\(\s*(?P<year>\d{4})\s*\)\.\s+
                   (?P<title>.+?)\.\s+(?P<venue>.+?)(?:[.,;]|$)""", re.X),
    # IEEE-ish: Authors, "Title," Venue, Year.
    re.compile(r"""^(?P<authors>.+?)\.\s+"(?P<title>.+?)",\s+
                   (?P<venue>.+?),\s+(?P<year>\d{4})(?:[.,;]|$)""", re.X),
    # Simple: Authors. Title. Venue Year
    re.compile(r"""^(?P<authors>.+?)\.\s+(?P<title>.+?)\.\s+
                   (?P<venue>.+?)\s+(?P<year>\d{4})(?:[.,;]|$)""", re.X),
]

def parse_publication(s: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {"raw": s}
    # DOI/arXiv if present
    doi = re.search(r"\b10\.\d{4,9}/\S+\b", s)
    arxiv = re.search(r"\barXiv:\s*([0-9]+\.[0-9]+)", s, re.I)
    if doi: d["doi"] = doi.group(0).rstrip(".,;)")
    if arxiv: d["arxiv"] = arxiv.group(1)

    for pat in PUB_PATTERNS:
        m = pat.search(s)
        if m:
            d.update({k: v.strip(' "\'') for k, v in m.groupdict().items() if v})
            break

    # Clean authors into a list if present
    if "authors" in d:
        # split on , and “and”/& variants
        parts = re.split(r"\s*(?:,|and|&)\s+", d["authors"])
        d["authors_list"] = [p.strip().strip(".") for p in parts if p.strip()]

    # fallback year
    if "year" not in d:
        ym = re.search(r"\b(19|20)\d{2}\b", s)
        if ym: d["year"] = ym.group(0)

    return d

# --- Presentation / Invited talk parsing ------------------------------------

def parse_talk(s: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {"raw": s}
    # Type (weak signal)
    typem = re.search(r"(?i)\b(keynote|invited (?:talk|presentation)|seminar|colloquium|tutorial|webinar|panel)\b", s)
    if typem: d["type"] = typem.group(1).title()

    # Date
    dm = DATE_RE.search(s)
    if dm: d["date"] = dm.group(1)

    # Title in quotes
    tm = re.search(r"“([^”]+)”|\"([^\"]+)\"", s)
    if tm:
        d["title"] = next(g for g in tm.groups() if g)
    else:
        # fallback: after colon or dash
        fm = re.search(r":\s*([^–—-]+)$", s)
        if fm: d["title"] = fm.group(1).strip()

    # Venue / host guess: text before date or surrounding keywords
    hostm = re.search(r"(?i)\b(at|hosted by|@)\s+([^,;]+)", s)
    if hostm: d["venue"] = hostm.group(2).strip()
    else:
        # try after comma following title
        if "title" in d:
            after = s.split(d["title"])[-1]
            vm = re.search(r",\s*([^,;]+)", after)
            if vm:
                d["venue"] = vm.group(1).strip()

    return d

# --- Optional: enrichment stub (Crossref, ORCID, etc.) ----------------------

def enrich_with_crossref(pub: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stub: you can hit Crossref /works?query.bibliographic=...
    Keep offline here by default; just return unchanged.
    """
    return pub

# --- Main --------------------------------------------------------------------

def main(inpath: Path, outpath: Path):
    raw = load_export_json(inpath)
    text = dehyphenate_and_reflow(raw)
    sections = split_sections(text)

    pubs_sec_keys = {"publications","refereed publications","selected publications",
                     "peer-reviewed","peer reviewed","conference papers","journal articles"}
    talks_sec_keys = {"presentations","talks","invited talks","invited presentations","keynotes","seminars","colloquia"}

    pubs_raw: List[str] = []
    talks_raw: List[str] = []

    for k, paras in sections.items():
        k_norm = k.lower()
        items = section_items(paras)
        if any(h in k_norm for h in pubs_sec_keys):
            pubs_raw += items
        elif any(h in k_norm for h in talks_sec_keys):
            talks_raw += items
        # else: ignore or add to "other"

    publications = [enrich_with_crossref(parse_publication(s)) for s in pubs_raw]
    presentations = [parse_talk(s) for s in talks_raw]

    # split invited vs other based on detected type
    invited = [t for t in presentations if t.get("type","").lower().startswith("invited") or "Keynote" in t.get("type","")]
    non_invited = [t for t in presentations if t not in invited]

    out: Dict[str, Any] = {
        "summary": {
            "n_publications": len(publications),
            "n_presentations": len(presentations),
            "n_invited_talks": len(invited),
        },
        "publications": publications,
        "presentations": non_invited,
        "invited_talks": invited,
        "unparsed": {
            "publications": [s for s in pubs_raw if not any(k in parse_publication(s) for k in ("title","venue","year"))],
            "presentations": [s for s in talks_raw if "title" not in parse_talk(s)],
        },
    }

    outpath.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {outpath}  (pubs={len(publications)}, talks={len(presentations)}, invited={len(invited)})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Extract structured pubs/talks from pdftable_export.json")
    ap.add_argument("export_json", type=Path, help="Path to pdftable_export.json")
    ap.add_argument("--out", type=Path, default=Path("cv_structured.json"))
    args = ap.parse_args()
    main(args.export_json, args.out)

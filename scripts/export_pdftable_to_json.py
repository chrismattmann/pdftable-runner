#!/usr/bin/env python3
import sys, os, glob, json, pathlib, datetime, re
from bs4 import BeautifulSoup
import pandas as pd

def read_text_lines_from_html(path):
    try:
        html = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    tags = soup.find_all(["p", "li", "div", "span"])
    lines = []
    for t in tags:
        txt = " ".join(t.get_text(separator=" ", strip=True).split())
        if txt:
            lines.append(txt)
    dedup = []
    for s in lines:
        if not dedup or dedup[-1] != s:
            dedup.append(s)
    return dedup

def read_tables_from_html(path):
    try:
        tables = pd.read_html(path)
    except Exception:
        return []
    out = []
    for i, df in enumerate(tables, 1):
        out.append({
            "index": i,
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "rows": [[None if pd.isna(x) else x for x in row] for row in df.astype(object).values.tolist()],
            "columns": [str(c) for c in df.columns.tolist()]
        })
    return out

def load_json_if_exists(path):
    p = pathlib.Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return None
    return None

def main(outdir, outjson):
    out = {
        "document": {
            "output_dir": str(pathlib.Path(outdir).resolve()),
            "generated_at": datetime.datetime.now().isoformat(),
            "final_runs": sorted([os.path.basename(p) for p in glob.glob(os.path.join(outdir, "a_pdf_*.html"))])
        },
        "pages": []
    }

    # Gather only files that look like page-<number>.html
    candidates = glob.glob(os.path.join(outdir, "page-*.html"))
    page_htmls = []
    for ph in candidates:
        base = os.path.splitext(os.path.basename(ph))[0]  # e.g., "page-7" or "page-7_table_structure"
        if re.fullmatch(r"page-\d+", base):
            page_htmls.append(ph)
    page_htmls.sort(key=lambda p: int(re.fullmatch(r"page-(\d+)", os.path.splitext(os.path.basename(p))[0]).group(1)))

    for ph in page_htmls:
        base = os.path.splitext(os.path.basename(ph))[0]     # e.g., page-7
        m = re.fullmatch(r"page-(\d+)", base)
        if not m:
            continue
        page_num = int(m.group(1))

        page_png = os.path.join(outdir, f"{base}.png")
        layout_json = os.path.join(outdir, f"{base}_layout.json")
        tsr_html = os.path.join(outdir, f"{base}_table_structure_post.html")
        tsr_html_db = os.path.join(outdir, f"{base}_table_structure_post_db.html")

        # Try both raw TSR JSON filename patterns
        tsr_raw_json = os.path.join(outdir, f"table_infer_{base}.json")
        if not os.path.exists(tsr_raw_json):
            tsr_raw_json = os.path.join(outdir, f"table_infer_page-{page_num}.json")
        tsr_raw = load_json_if_exists(tsr_raw_json)

        page_entry = {
            "page": page_num,
            "image": os.path.basename(page_png) if os.path.exists(page_png) else None,
            "ocr_html": os.path.basename(ph),
            "layout": load_json_if_exists(layout_json),   # int bboxes if present
            "text_lines": read_text_lines_from_html(ph),
            "tables": read_tables_from_html(ph),
            "tsr": {
                "debug_html": os.path.basename(tsr_html) if os.path.exists(tsr_html) else None,
                "debug_html_db": os.path.basename(tsr_html_db) if os.path.exists(tsr_html_db) else None,
                "raw": tsr_raw
            }
        }
        out["pages"].append(page_entry)

    pathlib.Path(outjson).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outjson} with {len(out['pages'])} page(s).")

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "./cv_out"
    outjson = sys.argv[2] if len(sys.argv) > 2 else os.path.join(outdir, "combined.json")
    main(outdir, outjson)

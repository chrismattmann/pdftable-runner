#!/usr/bin/env python3
# fix_unboundlocal_tsr.py
import io, re, shutil
from datetime import datetime
from pathlib import Path

p = Path("/Users/mattmann/git/pdf_table/src/pdftable/model/ocr_pdf/ocr_system_task.py")
src = p.read_text(encoding="utf-8")
backup = p.with_suffix(p.suffix + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak")
shutil.copy2(p, backup)

changed = False

# 1) Ensure `result` is initialized at the start of table_structure_detection
def_pat = r"(def\s+table_structure_detection\([^\)]*\):\s*\n)(\s+)"
if re.search(def_pat, src):
    def m(mo):
        head, indent = mo.group(1), mo.group(2)
        # Only insert if not already present within a few lines after def
        after_def_pat = re.compile(rf"{re.escape(head)}(?:{indent}.*\n){{0,8}}", re.DOTALL)
        block = after_def_pat.search(src, mo.start())
        insert_here = mo.end()
        # Check if there's already a `result =` very early in the function
        early_chunk = src[insert_here: insert_here + 400]
        if "result = None  # init to avoid UnboundLocal" not in early_chunk:
            return head + f"{indent}result = None  # init to avoid UnboundLocal\n"
        return mo.group(0)
    src2 = re.sub(def_pat, m, src, count=1)
    if src2 != src:
        src = src2
        changed = True

# 2) Make "if not isinstance(result, dict):" robust to undefined `result`
src2 = re.sub(
    r"\bif\s+not\s+isinstance\(\s*result\s*,\s*dict\s*\)\s*:",
    "if 'result' not in locals() or not isinstance(result, dict):",
    src
)
if src2 != src:
    src = src2
    changed = True

# 3) (Already done earlier) make len(table_structure_result['structure_str_list']) safe
# But do it again defensively in case it appears elsewhere.
src2 = re.sub(
    r"len\(\s*table_structure_result\['structure_str_list'\]\s*\)",
    "len(table_structure_result.get('structure_str_list', table_structure_result.get('structure_list', [])))",
    src
)
if src2 != src:
    src = src2
    changed = True

if changed:
    p.write_text(src, encoding="utf-8")
    print("Patched:", p)
else:
    print("No changes made:", p)
print("Backup :", backup)

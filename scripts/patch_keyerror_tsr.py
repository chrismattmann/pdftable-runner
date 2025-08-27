#!/usr/bin/env python3
# patch_keyerror_tsr.py
import io, os, re, shutil
from datetime import datetime

PATH = "/Users/mattmann/git/pdf_table/src/pdftable/model/ocr_pdf/ocr_system_task.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

backup = PATH + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
shutil.copy2(PATH, backup)

# 1) Make the table_structure_detection logger robust
# Replace direct ['structure_str_list'] usage with a safe count
pattern = r"len\(\s*table_structure_result\['structure_str_list'\]\s*\)"
replacement = "len(table_structure_result.get('structure_str_list', table_structure_result.get('structure_list', [])))"
src2 = re.sub(pattern, replacement, src)

# 2) Optionally, normalize result dict right after the recognizer call
# Insert a small guard: if result is None/non-dict, coerce to {}
guard_pat = r"(result\s*=\s*self\.table_structure_recognizer\([^)]+\)\s*\n)"
guard_add = (
    r"\1"
    "        if not isinstance(result, dict):\n"
    "            result = {}\n"
    "        if 'structure_str_list' not in result and 'structure_list' in result:\n"
    "            try:\n"
    "                result['structure_str_list'] = [str(x) for x in result.get('structure_list', [])]\n"
    "            except Exception:\n"
    "                result['structure_str_list'] = []\n"
)
src3 = re.sub(guard_pat, guard_add, src)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src3)

print("Patched:", PATH)
print("Backup :", backup)

#!/usr/bin/env python3
# unify_torch_device_patch.py
import io, os, re, shutil
from datetime import datetime
ROOT = "/Users/mattmann/git/pdf_table/src/pdftable"

def read(p):  return io.open(p, "r", encoding="utf-8").read()
def write(p,s): io.open(p, "w", encoding="utf-8").write(s)

HELPER = '''
def __pt_select_device():
    import os, torch
    force = os.environ.get("PDFTABLE_FORCE_DEVICE", "").lower()
    mps_ok = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    if force in {"cpu","mps","cuda","cuda:0"}:
        if force.startswith("cuda"):
            return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        if force == "mps":
            return torch.device("mps" if mps_ok else "cpu")
        return torch.device("cpu")
    if mps_ok:
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")

def __pt_get_device():
    import torch
    # cache once
    if not hasattr(__pt_get_device, "_dev"):
        __pt_get_device._dev = __pt_select_device()
    return __pt_get_device._dev
'''

def ensure_imports_and_helper(s):
    changed = False
    if "__pt_select_device" in s:
        return s, False
    # make sure at least one import block exists; add os/torch if missing
    if not re.search(r'^\s*import\s+os\b', s, re.M):
        s = 'import os\n' + s; changed = True
    if not re.search(r'^\s*import\s+torch\b', s, re.M):
        s = 'import torch\n' + s; changed = True
    # insert helper right after the last import
    imp_end = 0
    for m in re.finditer(r'^(?:from\s+\S+\s+import\s+.+|import\s+.+)\n', s, re.M):
        imp_end = m.end()
    s = s[:imp_end] + HELPER + s[imp_end:]
    return s, True

def replace_cuda_calls(s):
    # Replace .cuda(args...) -> .to(__pt_get_device(), args...)
    # Do the arg case first so we don't pre-empt it with the empty-call rule.
    s2 = re.sub(r'\.cuda\(\s*([^)]+?)\s*\)', r'.to(__pt_get_device(), \1)', s)
    s2 = re.sub(r'\.cuda\(\s*\)', r'.to(__pt_get_device())', s2)
    return s2, (s2 != s)

def patch_file(path):
    s = read(path)
    s, ch1 = ensure_imports_and_helper(s)
    s, ch2 = replace_cuda_calls(s)
    if ch1 or ch2:
        backup = f"{path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        shutil.copy2(path, backup)
        write(path, s)
        return True, backup, ch1, ch2
    return False, None, False, False

def main():
    patched = []
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "model")):
        for fn in filenames:
            if not fn.endswith(".py"): continue
            full = os.path.join(dirpath, fn)
            # quick prefilter
            with io.open(full, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            if ".cuda(" not in txt:
                continue
            ok, backup, ch1, ch2 = patch_file(full)
            if ok:
                patched.append((full, backup, ch1, ch2))
    if not patched:
        print("No .cuda(…) occurrences found under", os.path.join(ROOT, "model"))
    else:
        for p in patched:
            print("Patched:", p[0])
            print("  Backup:", p[1])
            print("  Added helper:", p[2], "Replaced .cuda:", p[3])

if __name__ == "__main__":
    main()

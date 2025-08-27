#!/usr/bin/env bash
set -euo pipefail

# 1) create venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# 2) install pdf_table in editable mode + deps for the exporter
pip install -e vendor/pdf_table
pip install bs4 pandas lxml

# 3) apply patches
python scripts/unify_torch_device_patch.py
python scripts/fix_unboundlocal_tsr.py

# 4) run pdftable
OUTDIR=./cv_out
mkdir -p "$OUTDIR"
pdftable --file_path_or_url "/path/to/your.pdf" --output_dir "$OUTDIR" --pages all --lang en

# 5) export to JSON
python scripts/export_pdftable_to_json.py "$OUTDIR" "$OUTDIR/combined.json"
echo "Done -> $OUTDIR/combined.json"

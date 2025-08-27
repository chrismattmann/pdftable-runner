# pdftable-runner

Helper repo to run the `pdftable` CLI on PDFs and export results to JSON.

It includes:
- A simple workflow to run `pdftable` over a PDF into an output folder (per-page PNG/PDF/HTML).
- `export_pdftable_to_json.py` – merges outputs into a single JSON file per run.
- Optional patch scripts we used to make the upstream code robust on CPU/Apple Silicon:
  - `unify_torch_device_patch.py`
  - `patch_keyerror_tsr.py`
  - `fix_unboundlocal_tsr.py`

> This repo **wraps** the upstream `pdftable` project. Ensure the `pdftable` CLI is installed and on PATH.

## Quick start

Run the extractor (example):
```bash
pdftable --file_path_or_url "/path/to/your.pdf" \
  --output_dir "./cv_out" \
  --pages all \
  --lang en
```

Export to JSON:

```bash
python export_pdftable_to_json.py --outdir ./cv_out --outjson ./cv_out/results.json
```

The ./cv_out folder will contain page-*.{pdf,png,html} and model artifacts;
results.json is a list of page objects with text blocks and (when present) table info.

License
Apache License, Version 2.0 — see LICENSE.txt.

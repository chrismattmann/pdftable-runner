# 1) remove the legacy script if it exists
[ -f extract_structured_cv.py ] && git rm -f extract_structured_cv.py

# 2) make the new script the canonical name (optional but cleaner)
[ -f extract_structured_cv_v2.py ] && git mv -f extract_structured_cv_v2.py extract_structured_cv.py

# 3) commit and push
git add -A
git commit -m "feat(extractor): replace legacy extractor with schema-agnostic version; remove old script"
git push origin HEAD

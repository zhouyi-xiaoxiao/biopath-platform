#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== BioPath pitch preflight check =="
echo "repo: $ROOT_DIR"

echo
echo "[1/5] Backend tests"
python -m pytest -q

echo
echo "[2/5] UI smoke tests"
npm run test:ui

echo
echo "[3/5] Critical local assets"
assets=(
  "site/assets/cambridge-university-farm.jpg"
  "site/assets/cambridge-photo-informed-transform.png"
  "site/data/latest.json"
  "site/data/latest-benchmark.json"
  "site/data/latest-heatmap.png"
)
for asset in "${assets[@]}"; do
  if [[ ! -f "$asset" ]]; then
    echo "Missing required asset: $asset" >&2
    exit 1
  fi
  echo "ok  $asset"
done

echo
echo "[4/5] Official source links"
urls=(
  "https://www.ceresagritech.org/lincam-linc-camb/concept/"
  "https://www.ceresagritech.org/lincam-linc-camb/"
  "https://bpca.org.uk/"
  "https://www.gov.uk/government/publications/farming-evidence-pack-a-high-level-overview-of-the-uk-agricultural-industry/farming-evidence-key-statistics-accessible-version"
)
for url in "${urls[@]}"; do
  code="$(curl -L -s -o /dev/null -w "%{http_code}" "$url")"
  if [[ "$code" != "200" ]]; then
    echo "Link check failed: $url (HTTP $code)" >&2
    exit 1
  fi
  echo "ok  $url"
done

echo
echo "[5/5] Script timing and deck mapping"
python - <<'PY'
from pathlib import Path
import re

script_html = Path("site/pitch-script.html").read_text(encoding="utf-8")

# Validate timeline totals exactly 600s.
ranges = re.findall(r'(\d+):(\d+)-(\d+):(\d+)', script_html)
seen = []
for r in ranges:
    if r not in seen:
        seen.append(r)

segments = []
for a, b, c, d in seen:
    start = int(a) * 60 + int(b)
    end = int(c) * 60 + int(d)
    if 0 <= start < 600 and 0 < end <= 600 and end > start:
        segments.append((start, end, end - start, f"{a}:{b}-{c}:{d}"))

segments.sort(key=lambda x: x[0])
total = sum(seg[2] for seg in segments)
if total != 600:
    raise SystemExit(f"Timeline sum must be 600 seconds; found {total}")

print("ok  Timeline sum is exactly 600 seconds")

# Validate deck mapping mentions slide 1..8 at least once.
slides = sorted({int(x) for x in re.findall(r'Deck Slide\s*(\d+)', script_html)})
if slides != [1, 2, 3, 4, 5, 6, 7, 8]:
    raise SystemExit(f"Deck mapping mismatch; found {slides}, expected [1..8]")

print("ok  Script references Deck Slide 1..8")
PY

echo
echo "All checks passed. Pitch build is stage-ready."

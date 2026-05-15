#!/usr/bin/env bash
set -euo pipefail

# Convert a Longbridge Daily Brief HTML file to PDF using local Google Chrome.
# Usage:
#   ./html_to_pdf_chrome.sh
#   ./html_to_pdf_chrome.sh /path/to/longbridge_memo_YYYYMMDD.html

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ ! -x "$CHROME" ]]; then
  echo "Error: Google Chrome not found at: $CHROME" >&2
  exit 1
fi

INPUT_HTML="${1:-}"

if [[ -z "$INPUT_HTML" ]]; then
  INPUT_HTML="$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name 'longbridge_memo_*.html' ! -name '*archive*' | sort | tail -n 1)"
fi

if [[ -z "$INPUT_HTML" || ! -f "$INPUT_HTML" ]]; then
  echo "Error: HTML file not found." >&2
  echo "Usage: ./html_to_pdf_chrome.sh /path/to/longbridge_memo_YYYYMMDD.html" >&2
  exit 1
fi

BASENAME="$(basename "$INPUT_HTML")"
DATE_PART="$(printf '%s' "$BASENAME" | sed -n 's/^longbridge_memo_\([0-9]\{8\}\)\.html$/\1/p')"

if [[ -z "$DATE_PART" ]]; then
  DATE_PART="$(date +%Y%m%d)"
fi

OUTPUT_PDF="$SCRIPT_DIR/longbridge_daily_brief.${DATE_PART}.chrome.pdf"
PROFILE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/longbridge-chrome-pdf.XXXXXX")"

cleanup() {
  if [[ -n "${PROFILE_DIR:-}" && -d "$PROFILE_DIR" ]]; then
    rm -r "$PROFILE_DIR"
  fi
}
trap cleanup EXIT

FILE_URL="file://$INPUT_HTML"

echo "Input : $INPUT_HTML"
echo "Output: $OUTPUT_PDF"
echo "Starting Chrome PDF export..."

"$CHROME" \
  --headless=new \
  --disable-gpu \
  --no-first-run \
  --no-default-browser-check \
  --disable-extensions \
  --user-data-dir="$PROFILE_DIR" \
  --print-to-pdf="$OUTPUT_PDF" \
  --print-to-pdf-no-header \
  "$FILE_URL"

if [[ ! -s "$OUTPUT_PDF" ]]; then
  echo "Error: PDF was not created." >&2
  exit 1
fi

echo "Done: $OUTPUT_PDF"

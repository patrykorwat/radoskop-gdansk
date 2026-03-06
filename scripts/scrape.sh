#!/usr/bin/env bash
set -euo pipefail

# Scrape danych głosowań Rady Miasta Gdańska (PDFy z BIP Gdańsk)
# Uruchom z katalogu radoskop-gdansk/ lub z dowolnego miejsca
#
# Krok 1: Pobierz PDFy głosowań (download_glosowania.sh)
# Krok 2: Przetwórz PDFy na data.json (scrape_protokoly.py)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Radoskop Gdańsk — scraper ==="
echo "Katalog projektu: $PROJECT_DIR"

# Setup venv
if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "[1/4] Tworzenie venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"

echo "[2/4] Instalacja zależności..."
pip install --quiet requests beautifulsoup4 lxml pymupdf

# Download PDFs if not already present
PDF_DIR="$PROJECT_DIR/pdfs"
if [ ! -d "$PDF_DIR" ] || [ "$(ls -A "$PDF_DIR" 2>/dev/null | wc -l)" -eq 0 ]; then
  echo "[3/4] Pobieranie PDF-ów głosowań..."
  bash "$PROJECT_DIR/download_glosowania.sh"
else
  echo "[3/4] PDFy już pobrane (${PDF_DIR}), pomijam..."
fi

echo "[4/4] Przetwarzanie PDF-ów..."
python3 "$SCRIPT_DIR/scrape_protokoly.py" \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  "$@"

echo ""
echo "Gotowe: $PROJECT_DIR/docs/data.json"

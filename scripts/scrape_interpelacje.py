#!/usr/bin/env python3
"""
Scraper interpelacji i zapytań radnych z BIP Gdańsk.

Źródło:
  - Interpelacje: https://bip.gdansk.pl/rada-miasta/publikacja-interpelacji-radnych-miasta-gdanska
  - Zapytania: https://bip.gdansk.pl/rada-miasta/publikacja-zapytan-radnych-miasta-gdanska

Strony BIP ładują dane AJAX-em po zmianie roku (pzrmg.changeYear).
Endpoint: POST z form-data year={rok} na tę samą stronę.

Użycie:
  python3 scrape_interpelacje.py [--lata 2024,2025,2026] [--output docs/interpelacje.json]
"""

import argparse
import json
import os
import re
import sys
import time
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    print("Wymagany moduł: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Wymagany moduł: pip install beautifulsoup4")
    sys.exit(1)


INTERP_URL = "https://bip.gdansk.pl/rada-miasta/publikacja-interpelacji-radnych-miasta-gdanska"
ZAP_URL = "https://bip.gdansk.pl/rada-miasta/publikacja-zapytan-radnych-miasta-gdanska"

HEADERS = {
    "User-Agent": "Radoskop/1.0 (https://gdansk.radoskop.pl; kontakt@radoskop.pl)"
}


def parse_date(raw):
    """Konwertuje datę z formatu DD.MM.YYYY lub YYYY-MM-DD na YYYY-MM-DD."""
    if not raw or not raw.strip():
        return ""
    raw = raw.strip()
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    return raw


def get_kadencja(data_wplywu):
    """Przypisuje kadencję na podstawie daty wpływu."""
    if not data_wplywu:
        return "?"
    if data_wplywu >= "2024-05":
        return "IX"
    elif data_wplywu >= "2018-11":
        return "VIII"
    elif data_wplywu >= "2014-11":
        return "VII"
    else:
        return "VI"


def fetch_year(session, base_url, year):
    """Pobiera stronę z interpelacjami/zapytaniami dla danego roku."""
    # Pierwsze żądanie GET, żeby pobrać cookies
    resp = session.get(base_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # POST z parametrem year
    data = {"year": str(year)}
    resp = session.post(base_url, data=data, headers={
        **HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse_tables(html, typ, url_prefix):
    """Parsuje tabelki z interpelacjami/zapytaniami z HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="table-sm")

    records = []
    for table in tables:
        obj = {}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            val_cell = cells[1]
            val_text = val_cell.get_text(strip=True)

            if "cr" in label and ("cri" in label or "crz" in label or label.startswith("cr")):
                obj["cri"] = val_text
            elif "ezd" in label:
                obj["ezd"] = val_text
            elif "data wpływu" in label or "data wplywu" in label:
                obj["data_wplywu"] = parse_date(val_text)
            elif "imię" in label or "imie" in label:
                obj["radny"] = val_text
            elif "przedmiot" in label:
                obj["przedmiot"] = val_text.replace("\n", " ").strip()
            elif label == "treść" or label == "tresc":
                a = val_cell.find("a")
                obj["tresc_url"] = a["href"] if a and a.get("href") else ""
            elif "data odpowiedzi" in label:
                obj["data_odpowiedzi"] = parse_date(val_text)
            elif "treść odpowiedzi" in label or "odpowiedz" in label:
                a = val_cell.find("a")
                obj["odpowiedz_url"] = a["href"] if a and a.get("href") else ""

        if obj.get("cri"):
            # Prefix zapytania with Z if not already
            if typ == "zapytanie" and not obj["cri"].startswith("Z"):
                obj["cri"] = "Z" + obj["cri"]

            obj.setdefault("ezd", "")
            obj.setdefault("data_wplywu", "")
            obj.setdefault("radny", "")
            obj.setdefault("przedmiot", "")
            obj.setdefault("data_odpowiedzi", "")
            obj.setdefault("tresc_url", "")
            obj.setdefault("odpowiedz_url", "")

            rok = int(obj["data_wplywu"][:4]) if obj["data_wplywu"] else 0
            obj["rok"] = rok
            obj["typ"] = typ
            obj["kadencja"] = get_kadencja(obj["data_wplywu"])

            records.append(obj)

    return records


def scrape(years, output_path):
    """Główna funkcja scrapowania."""
    session = requests.Session()
    all_records = []

    # Interpelacje
    print("=== Interpelacje ===")
    for year in years:
        print(f"  Rok {year}...", end=" ", flush=True)
        try:
            html = fetch_year(session, INTERP_URL, year)
            records = parse_tables(html, "interpelacja", "rmg_i")
            print(f"{len(records)} rekordów")
            all_records.extend(records)
        except Exception as e:
            print(f"BŁĄD: {e}")
        time.sleep(1)

    # Zapytania
    print("\n=== Zapytania ===")
    for year in years:
        print(f"  Rok {year}...", end=" ", flush=True)
        try:
            html = fetch_year(session, ZAP_URL, year)
            records = parse_tables(html, "zapytanie", "rmg_p")
            print(f"{len(records)} rekordów")
            all_records.extend(records)
        except Exception as e:
            print(f"BŁĄD: {e}")
        time.sleep(1)

    # Sortuj od najnowszych
    all_records.sort(key=lambda x: x.get("data_wplywu", ""), reverse=True)

    # Statystyki
    interp_count = sum(1 for r in all_records if r["typ"] == "interpelacja")
    zap_count = sum(1 for r in all_records if r["typ"] == "zapytanie")
    print(f"\n=== Podsumowanie ===")
    print(f"Interpelacje: {interp_count}")
    print(f"Zapytania:    {zap_count}")
    print(f"Razem:        {len(all_records)}")

    # Zapisz
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nZapisano: {output_path} ({size_kb:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Scraper interpelacji i zapytań z BIP Gdańsk")
    parser.add_argument(
        "--lata", default="2017,2018,2019,2020,2021,2022,2023,2024,2025,2026",
        help="Lata do scrapowania (oddzielone przecinkami)"
    )
    parser.add_argument(
        "--output", default="docs/interpelacje.json",
        help="Ścieżka do pliku wyjściowego"
    )
    args = parser.parse_args()

    years = [int(y.strip()) for y in args.lata.split(",")]
    scrape(years, args.output)


if __name__ == "__main__":
    main()

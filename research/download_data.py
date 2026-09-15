"""Descarca CSV-uri istorice de la football-data.co.uk (gratuit, fara cont).

Fiecare fisier = o liga x un sezon, cu rezultate + cote de la case de pariuri.
Datele sunt cache-uite local; rulari repetate nu re-descarca.
"""
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.football-data.co.uk/mmz4281"
DATA = Path(__file__).parent / "data"

# Ligile cu cel mai bun istoric de cote si acoperire consistenta
LEAGUES = {
    "E0": "Premier League",
    "E1": "Championship",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "B1": "Jupiler Pro League",
    "T1": "Super Lig",
    "G1": "Super League Greece",
    "SC0": "Scottish Premiership",
}

# 2014/15 .. 2026/27
SEASONS = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2014, 2027)]


def fetch(season: str, code: str) -> str | None:
    dest = DATA / season / f"{code}.csv"
    if dest.exists() and dest.stat().st_size > 1000:
        return "cached"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{season}/{code}.csv"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException as exc:
        return f"eroare: {exc}"
    if r.status_code != 200 or len(r.content) < 1000:
        return None
    dest.write_bytes(r.content)
    time.sleep(0.4)  # politicos fata de server
    return f"{len(r.content) // 1024} KB"


def main() -> int:
    ok = skipped = 0
    for season in SEASONS:
        line = []
        for code in LEAGUES:
            res = fetch(season, code)
            if res is None:
                skipped += 1
            else:
                ok += 1
                if res != "cached":
                    line.append(code)
        if line:
            print(f"  {season}: descarcat {' '.join(line)}", flush=True)
    print(f"\nGata: {ok} fisiere disponibile, {skipped} indisponibile (sezon/liga inexistenta).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

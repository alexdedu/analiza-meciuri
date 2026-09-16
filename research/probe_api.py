"""Verifica trei lucruri care decid cum construim integrarea.

1. Cat de scump e istoricul de meciuri? (o cerere per liga-sezon, sau mai multe?)
2. Exista cote pentru meciuri VECHI, nu doar pentru cele care urmeaza?
   Fara ele nu pot valida modelul pe cupele europene.
3. Cum se numesc echipele acolo fata de cum le avem noi? Daca difera mult,
   integrarea inseamna si o munca de potrivire a numelor.

Consuma ~8 cereri.
"""
from __future__ import annotations

import sys

import requests

from api_config import load_key, request_config

UCL, UEL = 2, 3


def get(base, headers, path, **params):
    r = requests.get(f"{base}/{path}", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body


def main() -> int:
    key = load_key()
    if not key:
        print("Cheia lipseste.")
        return 1
    base, headers = request_config(key)

    print("=" * 70)
    print("1. ISTORICUL DE MECIURI — cat costa in cereri")
    print("=" * 70)
    body = get(base, headers, "fixtures", league=UEL, season=2023)
    meciuri = body["response"]
    print(f"  Europa League 2023: {body['results']} meciuri intr-o singura cerere")
    print(f"  paginare: {body.get('paging')}")
    if meciuri:
        m = meciuri[0]
        gol = m["goals"]
        print(f"  exemplu: {m['teams']['home']['name']} {gol['home']}-{gol['away']} "
              f"{m['teams']['away']['name']}  ({m['fixture']['date'][:10]})")
        print(f"  contine scor final: {'da' if gol['home'] is not None else 'nu'}")
        print(f"  statistici in acelasi raspuns: "
              f"{'nu, cerere separata' if 'statistics' not in m else 'da'}")

    print("\n" + "=" * 70)
    print("2. COTE PENTRU MECIURI VECHI — punctul critic")
    print("=" * 70)
    for sezon in (2023, 2021, 2018, 2015):
        try:
            body = get(base, headers, "odds", league=UEL, season=sezon)
            total = body["results"]
            pagini = body.get("paging", {}).get("total", 1)
            print(f"  Europa League {sezon}: {total} meciuri cu cote, {pagini} pagini")
            if total and sezon == 2023:
                primul = body["response"][0]
                case = [b["name"] for b in primul.get("bookmakers", [])][:5]
                print(f"    case de pariuri: {len(primul.get('bookmakers', []))} "
                      f"(ex: {', '.join(case)})")
                piete = [b["name"] for b in primul["bookmakers"][0]["bets"]][:6]
                print(f"    piete disponibile: {', '.join(piete)}")
        except Exception as exc:
            print(f"  Europa League {sezon}: eroare -> {str(exc)[:60]}")

    print("\n" + "=" * 70)
    print("3. NUMELE ECHIPELOR — cat de mult difera de ce avem noi")
    print("=" * 70)
    body = get(base, headers, "teams", league=39, season=2025)  # Premier League
    nume = sorted(t["team"]["name"] for t in body["response"])
    print(f"  Premier League, {len(nume)} echipe:")
    print("   ", ", ".join(nume[:10]))
    print("  la noi (football-data.co.uk) apar ca:")
    print("    Arsenal, Aston Villa, Bournemouth, Brentford, Brighton, Chelsea, ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

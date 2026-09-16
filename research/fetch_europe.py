"""Descarca istoricul cupelor europene de la API-Football.

O cerere per competitie-sezon (~175 de meciuri fiecare), deci tot istoricul
costa sub 30 de cereri din cele 7.500 zilnice.

Meciurile astea sunt pretioase dintr-un motiv aparte: sunt singurele care
leaga campionatele intre ele. Modelul nostru masoara fiecare echipa fata de
restul ligii sale, deci o echipa olandeza si una spaniola de mijlocul
clasamentului arata la fel. Meciurile europene sunt exact locul unde cele doua
scari se ating, deci din ele se poate estima cat valoreaza un campionat fata
de altul.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

from api_config import load_key, request_config

OUT = Path(__file__).parent / "data" / "europa"

COMPETITII = {
    2: ("UCL", "Champions League", range(2011, 2027)),
    3: ("UEL", "Europa League", range(2014, 2027)),
    848: ("UECL", "Conference League", range(2021, 2027)),
}


def fetch_season(base: str, headers: dict, league_id: int, season: int) -> pd.DataFrame:
    r = requests.get(f"{base}/fixtures", headers=headers,
                     params={"league": league_id, "season": season}, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])

    randuri = []
    for item in body["response"]:
        fx, teams, goals = item["fixture"], item["teams"], item["goals"]
        # Meciurile neterminate sau anulate nu au scor: nu intra in istoric.
        if goals["home"] is None or goals["away"] is None:
            continue
        if fx["status"]["short"] not in ("FT", "AET", "PEN"):
            continue
        randuri.append({
            "fixture_id": fx["id"],
            "date": fx["date"][:10],
            "season": season,
            "round": item["league"]["round"],
            "home_id": teams["home"]["id"],
            "away_id": teams["away"]["id"],
            "home": teams["home"]["name"],
            "away": teams["away"]["name"],
            # La meciurile cu prelungiri, "goals" e scorul dupa 90 de minute plus
            # prelungiri. Pentru model ne trebuie timpul regulamentar.
            "hg": item["score"]["fulltime"]["home"] if item["score"]["fulltime"]["home"] is not None else goals["home"],
            "ag": item["score"]["fulltime"]["away"] if item["score"]["fulltime"]["away"] is not None else goals["away"],
        })
    return pd.DataFrame(randuri)


def main() -> int:
    key = load_key()
    if not key:
        print("Cheia lipseste. Vezi research/.secrets.env")
        return 1
    base, headers = request_config(key)
    OUT.mkdir(parents=True, exist_ok=True)

    cereri = 0
    for league_id, (cod, nume, sezoane) in COMPETITII.items():
        bucati = []
        for season in sezoane:
            dest = OUT / f"{cod}_{season}.csv"
            if dest.exists() and dest.stat().st_size > 200:
                bucati.append(pd.read_csv(dest))
                continue
            try:
                df = fetch_season(base, headers, league_id, season)
            except Exception as exc:
                print(f"  {cod} {season}: eroare {str(exc)[:60]}")
                continue
            cereri += 1
            if len(df):
                df.to_csv(dest, index=False)
                bucati.append(df)
            time.sleep(0.3)
        if bucati:
            total = pd.concat(bucati, ignore_index=True)
            print(f"  {cod}: {len(total):5d} meciuri, {total['season'].nunique()} sezoane, "
                  f"{total['date'].min()} -> {total['date'].max()}")

    print(f"\nCereri consumate: {cereri}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

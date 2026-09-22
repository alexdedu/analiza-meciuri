"""Descarca istoricul meciurilor dintre echipe nationale, de la API-Football.

De ce separat de tot restul: modelul nostru masoara cluburi, iar o echipa
nationala nu exista in datele football-data. Olanda nu joaca in Eredivisie.
Deci nationalele au nevoie de propriul lor bazin de meciuri si de propriul fit.

Ce luam la antrenament: preliminarii, Liga Natiunilor si amicale -- competitii
in care gazda joaca intr-adevar acasa. Turneele finale (Mondial, Euro, Cupa
Africii) se joaca la o singura tara gazda, deci "acasa" e o fictiune pentru
aproape toate meciurile; incluse, ar dilua avantajul terenului pentru toti.
Le lasam deoparte la antrenament, chiar daca le prezicem cand vin.

Cost: o cerere per competitie-sezon, ~90 in total, din 7.500 zilnice.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

from api_config import load_key, request_config

OUT = Path(__file__).parent / "data" / "national"

# Competitii cu avantajul terenului real: din ele invata modelul.
COMPETITII_ACASA = {
    5: ("NL", "UEFA Nations League", range(2018, 2027)),
    10: ("FRIENDLY", "Friendlies", range(2017, 2027)),
    29: ("WCQ_AFR", "Preliminarii CM - Africa", range(2018, 2027)),
    30: ("WCQ_ASIA", "Preliminarii CM - Asia", range(2018, 2027)),
    31: ("WCQ_CONCACAF", "Preliminarii CM - CONCACAF", range(2018, 2027)),
    32: ("WCQ_EUR", "Preliminarii CM - Europa", range(2018, 2027)),
    33: ("WCQ_OFC", "Preliminarii CM - Oceania", range(2018, 2027)),
    34: ("WCQ_SAM", "Preliminarii CM - America de Sud", range(2018, 2027)),
    35: ("ASIANQ", "Preliminarii Cupa Asiei", range(2019, 2027)),
    36: ("AFCONQ", "Preliminarii Cupa Africii", range(2021, 2028)),
    536: ("CONCACAF_NL", "CONCACAF Nations League", range(2020, 2027)),
    960: ("EUROQ", "Preliminarii Euro", range(2023, 2027)),
}

# Turnee finale: nu intra la antrenament (teren neutru), dar le prezicem.
COMPETITII_TURNEU = {
    1: ("WC", "Campionatul Mondial"),
    4: ("EURO", "Campionatul European"),
    6: ("AFCON", "Cupa Africii"),
    7: ("ASIAN", "Cupa Asiei"),
    9: ("COPA", "Copa America"),
    22: ("GOLD", "Gold Cup"),
    24: ("ASEAN", "Campionatul ASEAN"),
    25: ("GULF", "Cupa Golfului"),
}


def _api(base: str, headers: dict, **params) -> list[dict]:
    r = requests.get(f"{base}/fixtures", headers=headers, params=params, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def randuri(raspuns: list[dict], cod: str, season: int) -> pd.DataFrame:
    out = []
    for item in raspuns:
        fx, goals = item["fixture"], item["goals"]
        if fx["status"]["short"] not in ("FT", "AET", "PEN"):
            continue
        if goals["home"] is None or goals["away"] is None:
            continue
        final = item["score"]["fulltime"]
        out.append({
            "fixture_id": fx["id"],
            "date": fx["date"][:10],
            "competition": cod,
            "season": season,
            "home": item["teams"]["home"]["name"],
            "away": item["teams"]["away"]["name"],
            # La meciurile cu prelungiri pariul e pe timpul regulamentar.
            "hg": final["home"] if final["home"] is not None else goals["home"],
            "ag": final["away"] if final["away"] is not None else goals["away"],
        })
    return pd.DataFrame(out)


def descarca(force: bool = False) -> int:
    key = load_key()
    if not key:
        print("Cheia API lipseste. Vezi research/.secrets.env")
        return 0
    base, headers = request_config(key)
    OUT.mkdir(parents=True, exist_ok=True)

    cereri = 0
    for liga_id, (cod, nume, sezoane) in COMPETITII_ACASA.items():
        for season in sezoane:
            dest = OUT / f"{cod}_{season}.csv"
            # Sezonul in curs se reimprospateaza; cele incheiate, niciodata.
            incheiat = season < 2026
            if dest.exists() and incheiat and not force:
                continue
            try:
                df = randuri(_api(base, headers, league=liga_id, season=season),
                             cod, season)
                cereri += 1
            except Exception as exc:
                print(f"  {cod} {season}: {str(exc)[:70]}")
                continue
            # Scriem si fisierele goale: altfel cerem la nesfarsit sezoane
            # care chiar n-au avut meciuri.
            df.to_csv(dest, index=False)
            time.sleep(0.4)  # politete fata de API
    return cereri


def incarca() -> pd.DataFrame:
    """Tot istoricul de nationale, pregatit ca datele de club."""
    if not OUT.exists():
        return pd.DataFrame()
    bucati = [pd.read_csv(f) for f in sorted(OUT.glob("*.csv"))
              if f.stat().st_size > 50]
    if not bucati:
        return pd.DataFrame()
    df = pd.concat(bucati, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["home", "away", "hg", "ag"])
    df["hg"] = df["hg"].astype(int)
    df["ag"] = df["ag"].astype(int)
    # Acelasi meci poate aparea in doua sezoane la granita de an.
    return df.drop_duplicates(subset=["fixture_id"]).sort_values("date")


def main() -> int:
    cereri = descarca()
    df = incarca()
    if df.empty:
        print("Niciun meci de nationale descarcat.")
        return 1
    echipe = sorted(set(df["home"]) | set(df["away"]))
    print(f"{len(df):,} meciuri de nationale, {len(echipe)} echipe, "
          f"{df['date'].min().date()} .. {df['date'].max().date()} "
          f"({cereri} cereri noi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

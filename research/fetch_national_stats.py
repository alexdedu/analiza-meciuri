"""Cornere si cartonase pentru meciurile dintre echipe nationale.

De ce separat: cornerele si cartonasele de la cluburi vin din arhivele
football-data, care nu contin niciun meci de nationala. Iar in pauzele
competitionale -- adica exact cand aplicatia arata numai nationale -- sectiunea
de cornere si cartonase lipsea de peste tot.

API-ul are statisticile, dar o cerere per meci. Se aduna la fel ca minutele
cartonaselor: cate incap in buget la fiecare rulare, cele mai noi intai.

Datele se comit in repo (`istoric/statistici_nationale/`), nu in cache-ul CI:
costa mii de cereri, iar cache-ul se poate sterge oricand.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from api_config import load_key, request_config
from fetch_national import incarca as incarca_meciuri

OUT = Path(__file__).parent.parent / "istoric" / "statistici_nationale"

BUGET_IMPLICIT = 500

# Cat de departe in trecut are rost sa mergem. Nationalele isi schimba
# generatiile; un meci de acum sase ani spune putin despre echipa de azi.
ANI_INAPOI = 5

COLOANE = ["fixture_id", "date", "competition", "home", "away",
           "hc", "ac", "hy", "ay", "hr", "ar", "statistici"]

# Cum se numesc in API statisticile care ne intereseaza.
CHEI = {"Corner Kicks": ("hc", "ac"), "Yellow Cards": ("hy", "ay"),
        "Red Cards": ("hr", "ar")}


def _fisier(an: int) -> Path:
    return OUT / f"statistici_{an}.csv"


def incarca(doar_utile: bool = False) -> pd.DataFrame:
    """Statisticile adunate pana acum.

    `doar_utile` scoate meciurile pentru care API-ul n-are statistici: acolo
    zerourile ar insemna "nu stim", nu "n-a fost niciun corner".
    """
    if not OUT.exists():
        return pd.DataFrame(columns=COLOANE)
    bucati = [pd.read_csv(f) for f in sorted(OUT.glob("statistici_*.csv"))
              if f.stat().st_size > 50]
    if not bucati:
        return pd.DataFrame(columns=COLOANE)
    df = pd.concat(bucati, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["fixture_id"])
    if doar_utile:
        df = df[pd.to_numeric(df["statistici"], errors="coerce").fillna(0) > 0]
    return df


def _api(base: str, headers: dict, fixture_id: int) -> list[dict]:
    r = requests.get(f"{base}/fixtures/statistics", headers=headers,
                     params={"fixture": fixture_id}, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def citeste_statistici(raspuns: list[dict], gazda: str) -> dict:
    """Cornerele si cartonasele fiecarei echipe, dintr-un raspuns de statistici."""
    out = {c: 0 for c in ("hc", "ac", "hy", "ay", "hr", "ar")}
    for echipa in raspuns:
        acasa = (echipa.get("team") or {}).get("name") == gazda
        for stat in echipa.get("statistics", []):
            pereche = CHEI.get(stat.get("type"))
            if not pereche:
                continue
            valoare = stat.get("value")
            if valoare is None:
                continue
            out[pereche[0] if acasa else pereche[1]] = int(valoare)
    return out


def colecteaza(buget: int = BUGET_IMPLICIT, meciuri: pd.DataFrame | None = None,
               fetch=None) -> dict:
    if fetch is None:
        key = load_key()
        if not key:
            print("Cheia API lipseste; nu pot aduna statisticile nationalelor.")
            return {"cereri": 0, "meciuri": 0, "ramase": 0}
        base, headers = request_config(key)

        def fetch(fixture_id: int) -> list[dict]:
            return _api(base, headers, fixture_id)

    OUT.mkdir(parents=True, exist_ok=True)
    if meciuri is None:
        meciuri = incarca_meciuri()
    if meciuri.empty:
        return {"cereri": 0, "meciuri": 0, "ramase": 0}

    limita = pd.Timestamp.now().normalize() - pd.DateOffset(years=ANI_INAPOI)
    meciuri = meciuri[meciuri["date"] >= limita].sort_values("date", ascending=False)

    avute = set(incarca()["fixture_id"].astype(int)) if OUT.exists() else set()
    de_luat = [r for r in meciuri.itertuples(index=False)
               if int(r.fixture_id) not in avute]

    def scrie(loturi: dict[int, list[dict]]) -> None:
        for an, lot in loturi.items():
            if not lot:
                continue
            dest = _fisier(an)
            vechi = pd.read_csv(dest) if dest.exists() else pd.DataFrame(columns=COLOANE)
            nou = pd.concat([vechi, pd.DataFrame(lot)], ignore_index=True)
            nou.drop_duplicates(subset=["fixture_id"])[COLOANE] \
               .sort_values("date").to_csv(dest, index=False)

    cereri = 0
    adunate = 0
    randuri: dict[int, list[dict]] = {}
    for r in de_luat:
        if cereri >= buget:
            break
        try:
            raspuns = fetch(int(r.fixture_id))
            cereri += 1
        except Exception as exc:
            print(f"  meciul {r.fixture_id}: {str(exc)[:60]}")
            continue

        rand = {"fixture_id": int(r.fixture_id), "date": r.date.strftime("%Y-%m-%d"),
                "competition": r.competition, "home": r.home, "away": r.away,
                "statistici": len(raspuns)}
        rand.update(citeste_statistici(raspuns, r.home))
        randuri.setdefault(r.date.year, []).append(rand)
        adunate += 1
        # Scriem din 200 in 200: o rulare lunga intrerupta nu trebuie sa piarda
        # tot ce a adunat pana atunci.
        if adunate % 200 == 0:
            scrie(randuri)
            randuri = {}
        time.sleep(0.12)

    scrie(randuri)
    return {"cereri": cereri, "meciuri": adunate,
            "ramase": max(len(de_luat) - cereri, 0)}


def main() -> int:
    buget = int(os.environ.get("STATISTICI_BUGET", BUGET_IMPLICIT))
    raport = colecteaza(buget)
    total = incarca()
    utile = incarca(doar_utile=True)
    print(f"Adunate acum: {raport['meciuri']} meciuri ({raport['cereri']} cereri). "
          f"Total: {len(total)}, din care {len(utile)} cu statistici.")
    if raport["ramase"]:
        print(f"Mai sunt {raport['ramase']} meciuri de adunat "
              f"(~{raport['ramase'] // max(buget, 1) + 1} rulari).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

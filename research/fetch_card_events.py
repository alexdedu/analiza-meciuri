"""Aduna cartonasele pe reprize, meci cu meci, de la API-Football.

De ce e nevoie de un colector separat: arhivele football-data dau doar totalul
pe meci. Minutul fiecarui cartonas exista doar in evenimentele API-ului, iar
acolo se cere o cerere pentru fiecare meci in parte. Un sezon de zece
campionate inseamna ~3.500 de cereri, deci nu se poate lua dintr-o data.

Cum functioneaza: la fiecare rulare se iau cate meciuri incap in buget, cele
mai noi intai, si se scriu in `istoric/cartonase_reprize/`. Rularile urmatoare
continua de unde s-a ramas. Dupa cateva zile e adunat un sezon intreg.

DE CE in `istoric/` si nu in `research/data/`: fisierele de acolo se tin in
cache-ul CI, care se poate sterge oricand. Datele astea costa mii de cereri --
un istoric pierdut ar insemna zile de recolectare. Deci se comit in repo.

Numaratoarea urmeaza conventia football-data, ca sa se poata compara cu
totalurile pe meci de acolo: un al doilea galben se numara si ca galben, si ca
rosu.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from api_config import load_key, request_config
from rezultate_api import LIGI, STATUSURI_FINALE
from team_matching import build_matcher

OUT = Path(__file__).parent.parent / "istoric" / "cartonase_reprize"

# Sezoanele se aduna de la cel mai nou catre cel mai vechi: un sezon recent
# spune mai mult despre echipele de azi decat unul de acum trei ani.
SEZOANE = [2026, 2025, 2024]

# Cate cereri cheltuim pe rulare. Planul are 7.500 pe zi, iar restul
# pipeline-ului foloseste ~200; patru rulari pe zi la 600 inseamna 2.400.
BUGET_IMPLICIT = 600

COLOANE = ["fixture_id", "date", "div", "season", "home_api", "away_api",
           "home", "away", "hy1", "hy2", "ay1", "ay2", "hr1", "hr2", "ar1", "ar2",
           # Cate evenimente de orice fel avea meciul. Zero inseamna ca API-ul
           # n-are cronica meciului, nu ca s-a jucat fara cartonase -- iar
           # diferenta asta decide daca randul e folosibil sau nu.
           "evenimente"]


def _fisier(div: str, season: int) -> Path:
    return OUT / f"{div}_{season}.csv"


def incarca(div: str | None = None, doar_utile: bool = False) -> pd.DataFrame:
    """Tot ce s-a adunat pana acum, gata de folosit intr-un model.

    `doar_utile` scoate meciurile fara cronica in API: acolo zerourile n-ar
    insemna "fara cartonase", ci "nu stim".
    """
    if not OUT.exists():
        return pd.DataFrame(columns=COLOANE)
    fisiere = sorted(OUT.glob(f"{div}_*.csv" if div else "*.csv"))
    bucati = [pd.read_csv(f) for f in fisiere if f.stat().st_size > 50]
    if not bucati:
        return pd.DataFrame(columns=COLOANE)
    df = pd.concat(bucati, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    for col in COLOANE:
        if col not in df.columns:
            df[col] = pd.NA
    df = df.drop_duplicates(subset=["fixture_id"])
    if doar_utile:
        df = df[pd.to_numeric(df["evenimente"], errors="coerce").fillna(0) > 0]
    return df


def completeaza_nume(hist: pd.DataFrame | None = None) -> int:
    """Umple numele locale lipsa, fara nicio cerere noua.

    Se foloseste dupa ce s-au adaugat aliasuri: datele adunate raman pe disc,
    doar traducerea numelor se reface.
    """
    if hist is None:
        from data_loader import load_all
        hist = load_all()

    completate = 0
    for cale in sorted(OUT.glob("*.csv")):
        df = pd.read_csv(cale)
        lipsa = df["home"].isna() | df["away"].isna()
        if not lipsa.any():
            continue
        match = _potrivire_locala(hist, str(df["div"].iloc[0]))
        # O coloana numai cu valori lipsa se citeste ca numerica, si atunci un
        # nume de echipa nu incape in ea.
        for parte in ("home", "away"):
            df[parte] = df[parte].astype("object")
        for i in df.index[lipsa]:
            for parte in ("home", "away"):
                if pd.isna(df.at[i, parte]):
                    gasit = match(df.at[i, f"{parte}_api"])
                    if gasit:
                        df.at[i, parte] = gasit
                        completate += 1
        df.to_csv(cale, index=False)
    return completate


def _api(base: str, headers: dict, cale: str, **params) -> list[dict]:
    r = requests.get(f"{base}/{cale}", headers=headers, params=params, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def cartonase_pe_reprize(evenimente: list[dict], gazda_api: str) -> dict:
    """Numara cartonasele fiecarei echipe, pe reprize.

    Repriza se decide dupa minutul scurs: 45+3 e tot prima repriza, 46 e a doua.
    """
    out = {c: 0 for c in ("hy1", "hy2", "ay1", "ay2", "hr1", "hr2", "ar1", "ar2")}
    for ev in evenimente:
        if ev.get("type") != "Card":
            continue
        minut = (ev.get("time") or {}).get("elapsed")
        if minut is None:
            continue
        repriza = 1 if minut <= 45 else 2
        parte = "h" if (ev.get("team") or {}).get("name") == gazda_api else "a"
        detaliu = (ev.get("detail") or "").lower()

        if detaliu.startswith("yellow"):
            out[f"{parte}y{repriza}"] += 1
        elif "second yellow" in detaliu:
            # Conventia football-data: al doilea galben se numara in ambele.
            out[f"{parte}y{repriza}"] += 1
            out[f"{parte}r{repriza}"] += 1
        elif detaliu.startswith("red"):
            out[f"{parte}r{repriza}"] += 1
    return out


def _potrivire_locala(hist: pd.DataFrame, div: str):
    """Traduce numele API in numele nostru, pentru un singur campionat."""
    liga = hist[hist["div"] == div]
    if liga.empty:
        return lambda nume: None
    return build_matcher(sorted(set(liga["home"]) | set(liga["away"])))


def colecteaza(buget: int = BUGET_IMPLICIT, hist: pd.DataFrame | None = None) -> dict:
    key = load_key()
    if not key:
        print("Cheia API lipseste; nu pot aduna cartonasele pe reprize.")
        return {"cereri": 0, "meciuri": 0}
    base, headers = request_config(key)
    OUT.mkdir(parents=True, exist_ok=True)

    if hist is None:
        from data_loader import load_all
        hist = load_all()

    cereri = 0
    adunate = 0
    ramase = {}

    for season in SEZOANE:
        for div, liga_id in LIGI.items():
            if cereri >= buget:
                break

            # Un sezon incheiat si adunat complet nu mai are ce sa ne dea: fara
            # marcajul asta, fiecare rulare ar cheltui degeaba o cerere pe el.
            gata = OUT / f"{div}_{season}.complet"
            if gata.exists():
                continue

            dest = _fisier(div, season)
            existente = set()
            if dest.exists():
                vechi = pd.read_csv(dest)
                existente = set(vechi["fixture_id"].astype(int))
            else:
                vechi = pd.DataFrame(columns=COLOANE)

            try:
                fixturi = _api(base, headers, "fixtures", league=liga_id, season=season)
                cereri += 1
            except Exception as exc:
                print(f"  {div} {season}: lista de meciuri a picat ({str(exc)[:60]})")
                continue

            de_luat = [f for f in fixturi
                       if f["fixture"]["status"]["short"] in STATUSURI_FINALE
                       and int(f["fixture"]["id"]) not in existente]
            # Cele mai noi intai: daca bugetul se termina, macar avem recentul.
            de_luat.sort(key=lambda f: f["fixture"]["date"], reverse=True)
            if not de_luat:
                # Sezonul curent mai primeste meciuri; cele trecute, nu.
                if season < SEZOANE[0]:
                    gata.write_text("adunat complet\n", encoding="utf-8")
                continue
            ramase[f"{div} {season}"] = len(de_luat)

            match = _potrivire_locala(hist, div)
            randuri = []
            for f in de_luat:
                if cereri >= buget:
                    break
                fx = f["fixture"]
                try:
                    evenimente = _api(base, headers, "fixtures/events", fixture=fx["id"])
                    cereri += 1
                except Exception as exc:
                    print(f"  {div} {season} meciul {fx['id']}: {str(exc)[:60]}")
                    continue

                gazda_api = f["teams"]["home"]["name"]
                oaspete_api = f["teams"]["away"]["name"]
                rand = {
                    "fixture_id": int(fx["id"]),
                    "date": fx["date"][:10],
                    "div": div,
                    "season": season,
                    "home_api": gazda_api,
                    "away_api": oaspete_api,
                    # Numele nostru, ca datele sa se poata lipi de restul
                    # modelului fara potriviri repetate mai tarziu.
                    "home": match(gazda_api) or "",
                    "away": match(oaspete_api) or "",
                }
                rand["evenimente"] = len(evenimente)
                rand.update(cartonase_pe_reprize(evenimente, gazda_api))
                randuri.append(rand)
                adunate += 1
                time.sleep(0.12)  # sub limita de cereri pe minut

            if randuri:
                nou = pd.concat([vechi, pd.DataFrame(randuri)], ignore_index=True)
                nou = nou.drop_duplicates(subset=["fixture_id"])[COLOANE]
                nou.sort_values("date").to_csv(dest, index=False)
                ramase[f"{div} {season}"] -= len(randuri)

    return {"cereri": cereri, "meciuri": adunate, "ramase": ramase}


def main() -> int:
    buget = int(os.environ.get("CARTONASE_BUGET", BUGET_IMPLICIT))
    # Intai traducerile ramase in urma (gratis), apoi meciurile noi.
    if OUT.exists():
        completate = completeaza_nume()
        if completate:
            print(f"Nume locale completate fara nicio cerere: {completate}")
    raport = colecteaza(buget)
    total = incarca()
    print(f"Adunate acum: {raport['meciuri']} meciuri ({raport['cereri']} cereri). "
          f"Total in istoric: {len(total)} meciuri.")

    ramase = {k: v for k, v in (raport.get("ramase") or {}).items() if v > 0}
    if ramase:
        de_luat = sum(ramase.values())
        print(f"Mai sunt de adunat cel putin {de_luat} meciuri "
              f"(~{de_luat // max(buget, 1) + 1} rulari).")
    if not total.empty:
        # Numele lipsa se citesc ca NaN, nu ca sir gol: verificam ambele.
        fara_nume = int((total["home"].isna() | total["away"].isna()
                         | (total["home"].astype(str) == "")
                         | (total["away"].astype(str) == "")).sum())
        if fara_nume:
            print(f"Atentie: {fara_nume} meciuri fara nume local potrivit.")
        fara_cronica = int((pd.to_numeric(total["evenimente"], errors="coerce")
                            .fillna(-1) == 0).sum())
        if fara_cronica:
            print(f"{fara_cronica} meciuri fara cronica in API (nu se folosesc).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

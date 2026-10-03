"""Meciurile viitoare din campionate, luate de la API cand feedul intarzie.

Problema pe care o rezolva: fisierul de meciuri viitoare de la football-data se
publica de cateva ori pe saptamana si tine doar vreo saptamana inainte. In
pauzele competitionale el ramane gol zile intregi, desi programul exista de
mult -- iar aplicatia arata "pauza" cand de fapt urmatoarea etapa e stiuta.

Deci: cand feedul n-are meciuri pentru un campionat in fereastra afisata, le
luam de la API-Football, cu tot cu cote. Modelul ramane acelasi, antrenat pe
datele football-data; de aici vin doar numele echipelor si cotele.

Cost: o cerere per campionat, plus una per meci pentru cote -- sub 100 pe
rulare, din 7.500 zilnice.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

from api_config import load_key, request_config
from rezultate_api import LIGI, sezonul
from team_matching import build_matcher

# Cate zile inainte cerem. Fereastra afisata e de trei zile, dar o cerem mai
# larg ca sa prindem si cazul "urmatoarea etapa e peste cinci zile".
ZILE_CERUTE = 12


def _api(base: str, headers: dict, cale: str, **params) -> list[dict]:
    r = requests.get(f"{base}/{cale}", headers=headers, params=params, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def cote_meci(base: str, headers: dict, fixture_id: int) -> dict:
    """Cotele medii 1X2 si peste/sub 2.5, ca in feedul football-data."""
    try:
        raspuns = _api(base, headers, "odds", fixture=fixture_id)
    except Exception:
        return {}

    valori: dict[str, list[float]] = {}
    for item in raspuns:
        for casa in item.get("bookmakers", []):
            for pariu in casa.get("bets", []):
                nume = pariu.get("name")
                for v in pariu.get("values", []):
                    cheie = None
                    if nume == "Match Winner":
                        cheie = {"Home": "AvgH", "Draw": "AvgD",
                                 "Away": "AvgA"}.get(v.get("value"))
                    elif nume == "Goals Over/Under":
                        cheie = {"Over 2.5": "Avg>2.5",
                                 "Under 2.5": "Avg<2.5"}.get(v.get("value"))
                    if not cheie:
                        continue
                    try:
                        valori.setdefault(cheie, []).append(float(v["odd"]))
                    except (TypeError, ValueError):
                        pass
    return {k: round(float(np.mean(v)), 2) for k, v in valori.items() if v}


def fixturi_lipsa(divs: list[str], hist: pd.DataFrame, zile: int,
                  deja_avute: set[tuple[str, str, str]] | None = None) -> pd.DataFrame:
    """Meciurile viitoare ale campionatelor date, in forma feedului.

    `deja_avute` sunt perechile (div, gazda, oaspete, data) venite din feed, ca
    sa nu le adaugam de doua ori.
    """
    key = load_key()
    if not key:
        return pd.DataFrame()
    base, headers = request_config(key)

    azi = datetime.now().date()
    pana = azi + timedelta(days=zile)
    deja_avute = deja_avute or set()
    randuri = []

    for div in divs:
        liga_id = LIGI.get(div)
        if liga_id is None:
            continue
        try:
            # API-ul cere sezonul odata cu intervalul de date.
            raspuns = _api(base, headers, "fixtures", league=liga_id,
                           season=sezonul(azi.isoformat()),
                           **{"from": azi.isoformat(), "to": pana.isoformat()})
        except Exception as exc:
            print(f"  ({div}: nu am putut lua programul de la API: {str(exc)[:60]})")
            continue

        liga = hist[hist["div"] == div]
        if liga.empty:
            continue
        match = build_matcher(sorted(set(liga["home"]) | set(liga["away"])))

        for item in raspuns:
            fx = item["fixture"]
            if fx["status"]["short"] not in ("NS", "TBD"):
                continue
            gazda = match(item["teams"]["home"]["name"])
            oaspete = match(item["teams"]["away"]["name"])
            if not gazda or not oaspete:
                continue  # echipa pe care n-o stim din datele de antrenament
            data = fx["date"][:10]
            if (div, gazda, oaspete, data) in deja_avute:
                continue

            rand = {"div": div, "Date": data, "Time": fx["date"][11:16],
                    "home": gazda, "away": oaspete, "fixture_id": fx["id"]}
            rand.update(cote_meci(base, headers, fx["id"]))
            randuri.append(rand)

    if not randuri:
        return pd.DataFrame()
    out = pd.DataFrame(randuri)
    # Feedul foloseste zi/luna/an; aici data vine deja in forma ISO, deci o
    # marcam ca atare ca sa nu fie citita invers.
    out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%d/%m/%Y")
    return out

"""Predictii pentru meciurile din cupele europene.

Foloseste fortele echipelor din campionatele lor plus puterea fiecarui
campionat, estimata separat in fit_strengths.py. Daca lipseste fisierul cu
puteri, sau daca o echipa nu poate fi identificata, meciul e sarit — mai bine
lipsa decat un procent inventat.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

from api_config import load_key, request_config
from backtest import WINDOW_DAYS
from backtest_xg import XI, fit_on
from europe_model import EUROPA, PREFIXE_NEEUROPENE, div_la_data, este_european, liga_echipei
from team_matching import build_matcher

PUTERI_FISIER = EUROPA / "puteri.json"

COMPETITII = {
    2: "UEFA Champions League",
    3: "UEFA Europa League",
    848: "UEFA Conference League",
}
ZILE_INAINTE = 10


def incarca_puteri() -> dict | None:
    if not PUTERI_FISIER.exists():
        return None
    try:
        return json.loads(PUTERI_FISIER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _api(base, headers, path, **params):
    r = requests.get(f"{base}/{path}", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["response"]


def fixturi_viitoare(base, headers) -> list[dict]:
    """Meciurile europene din urmatoarele zile, cu numele si data lor."""
    azi = datetime.now().date()
    pana = azi + timedelta(days=ZILE_INAINTE)
    out = []
    for liga_id, nume in COMPETITII.items():
        try:
            raspuns = _api(base, headers, "fixtures", league=liga_id, season=azi.year,
                           **{"from": azi.isoformat(), "to": pana.isoformat()})
        except Exception as exc:
            print(f"  {nume}: nu am putut lua meciurile ({str(exc)[:60]})")
            continue
        for item in raspuns:
            fx = item["fixture"]
            if fx["status"]["short"] not in ("NS", "TBD"):
                continue  # deja jucat sau in desfasurare
            out.append({
                "fixture_id": fx["id"],
                "liga_id": liga_id,
                "liga_nume": nume,
                "data": fx["date"][:10],
                "ora": fx["date"][11:16],
                "home_api": item["teams"]["home"]["name"],
                "away_api": item["teams"]["away"]["name"],
            })
    return out


def cote_1x2(base, headers, fixture_id: int) -> dict:
    """Cotele medii 1X2 de la casele disponibile, ca reper."""
    try:
        raspuns = _api(base, headers, "odds", fixture=fixture_id)
    except Exception:
        return {}
    valori = {"home": [], "draw": [], "away": []}
    for item in raspuns:
        for casa in item.get("bookmakers", []):
            for pariu in casa.get("bets", []):
                if pariu.get("name") != "Match Winner":
                    continue
                for v in pariu.get("values", []):
                    cheie = {"Home": "home", "Draw": "draw", "Away": "away"}.get(v.get("value"))
                    if cheie:
                        try:
                            valori[cheie].append(float(v["odd"]))
                        except (TypeError, ValueError):
                            pass
    return {k: round(float(np.mean(v)), 2) for k, v in valori.items() if v}


def pregateste(hist: pd.DataFrame):
    """Unelte refolosite pentru toate meciurile: potrivire nume si apartenenta."""
    nume_locale = sorted(set(hist["home"]) | set(hist["away"]))
    return build_matcher(nume_locale), liga_echipei(hist)


def fit_pentru_divs(hist: pd.DataFrame, divs: set[str], azi: pd.Timestamp) -> dict:
    """Antreneaza modelul pentru fiecare campionat de care avem nevoie."""
    fits = {}
    for div in divs:
        liga = hist[hist["div"] == div]
        train = liga[liga["date"] >= azi - pd.Timedelta(days=WINDOW_DAYS)]
        if len(train) < 150:
            continue
        teams = sorted(set(train["home"]) | set(train["away"]))
        idx = {t: k for k, t in enumerate(teams)}
        fit, _ = fit_on(train, azi, ("hg", "ag"), XI, {}, teams, idx, len(teams))
        if fit is not None:
            fits[div] = (fit, train)
    return fits


def construieste_predictii(hist: pd.DataFrame) -> list[dict]:
    """Lista de meciuri europene gata de pus in predictions.json."""
    puteri = incarca_puteri()
    if not puteri:
        print("  lipsesc puterile campionatelor (ruleaza fit_strengths.py); sar peste cupe")
        return []

    key = load_key()
    if not key:
        print("  lipseste cheia API-Football; sar peste cupele europene")
        return []
    base, headers = request_config(key)

    fixturi = fixturi_viitoare(base, headers)
    if not fixturi:
        print("  niciun meci european in urmatoarele zile")
        return []
    print(f"  {len(fixturi)} meciuri europene gasite")

    match, apartenenta = pregateste(hist)
    azi = pd.Timestamp(datetime.now().date())

    # Traducem numele si aflam campionatul fiecarei echipe.
    pregatite, divs = [], set()
    for f in fixturi:
        h = match(f["home_api"])
        a = match(f["away_api"])
        if not h or not a:
            print(f"    sar peste {f['home_api']} - {f['away_api']} (echipa necunoscuta)")
            continue
        dh = div_la_data(apartenenta.get(h), f["data"])
        da = div_la_data(apartenenta.get(a), f["data"])
        if not este_european(dh) or not este_european(da):
            print(f"    sar peste {f['home_api']} - {f['away_api']} (campionat necunoscut)")
            continue
        f.update({"home": h, "away": a, "div_home": dh, "div_away": da})
        pregatite.append(f)
        divs.update({dh, da})

    if not pregatite:
        return []
    fits = fit_pentru_divs(hist, divs, azi)

    gamma = puteri["avantaj_teren"]
    rho = puteri["rho"]
    tabel_puteri = puteri["puteri"]

    from predict import head_to_head, team_context, top_scores
    from dixon_coles import markets_from_rates

    out = []
    for f in pregatite:
        par_h = fits.get(f["div_home"])
        par_a = fits.get(f["div_away"])
        if not par_h or not par_a:
            continue
        fit_h, train_h = par_h
        fit_a, train_a = par_a
        ih = fit_h.teams.get(f["home"])
        ia = fit_a.teams.get(f["away"])
        if ih is None or ia is None:
            continue

        s_h = tabel_puteri.get(f["div_home"], 0.0)
        s_a = tabel_puteri.get(f["div_away"], 0.0)
        lam = float(np.exp(fit_h.attack[ih] + s_h + fit_a.defence[ia] - s_a + gamma))
        mu = float(np.exp(fit_a.attack[ia] + s_a + fit_h.defence[ih] - s_h))
        lam, mu = min(lam, 8.0), min(mu, 8.0)

        p = markets_from_rates(lam, mu, rho)
        p["p_under25"] = 1 - p["p_over25"]
        p["p_no_btts"] = 1 - p["p_btts"]

        ctx_h = team_context(hist[hist["div"] == f["div_home"]], f["home"])
        ctx_a = team_context(hist[hist["div"] == f["div_away"]], f["away"])
        n_home = int(((train_h["home"] == f["home"]) | (train_h["away"] == f["home"])).sum())
        n_away = int(((train_a["home"] == f["away"]) | (train_a["away"] == f["away"])).sum())
        n_min = min(n_home, n_away)
        confidence = "ridicata" if n_min >= 40 else ("medie" if n_min >= 15 else "scazuta")

        fav, pf = ((f["home"], p["p_home"]) if p["p_home"] > p["p_away"]
                   else (f["away"], p["p_away"]))
        explicatie = (
            f"{fav} e favorita, cu {pf:.0%} sanse de victorie. "
            f"Goluri asteptate: {lam:.2f} pentru {f['home']}, {mu:.2f} pentru {f['away']}. "
            f"Fiind un meci intre campionate diferite, fortele echipelor sunt aduse pe "
            f"aceeasi scara folosind puterea estimata a fiecarui campionat "
            f"({f['div_home']}: {s_h:+.2f}, {f['div_away']}: {s_a:+.2f}), calculata din "
            f"{puteri['meciuri_folosite']:,} de meciuri europene anterioare. "
            "Pentru cupele europene nu exista cote istorice, deci aceste probabilitati "
            "nu au putut fi comparate cu piata asa cum s-a facut pentru campionate."
        )

        out.append({
            "id": f"EU{f['fixture_id']}",
            "league": f"EU_{f['liga_id']}",
            "league_name": f["liga_nume"],
            "date": f["data"],
            "time": f["ora"],
            "home": f["home"],
            "away": f["away"],
            "probs": {k: round(v, 4) for k, v in p.items()},
            "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
            "confidence": confidence,
            "sample": {"home_matches": n_home, "away_matches": n_away},
            "top_scores": top_scores(lam, mu, rho),
            "reference_odds": cote_1x2(base, headers, f["fixture_id"]),
            "context": {
                "home": ctx_h,
                "away": ctx_a,
                "h2h": head_to_head(hist, f["home"], f["away"]),
            },
            "explanation": explicatie,
        })

    print(f"  {len(out)} predictii europene")
    return out

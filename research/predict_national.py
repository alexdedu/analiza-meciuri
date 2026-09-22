"""Predictii pentru meciurile dintre echipe nationale.

In pauzele competitionale (de patru-cinci ori pe an, cate zece zile) nu se
joaca nimic in campionate, dar se joaca Liga Natiunilor si preliminariile.
Fara sectiunea asta, aplicatia ar fi goala exact in saptamanile alea.

Modelul e masurat, nu presupus: pe 3.339 de meciuri neatinse la antrenare,
log-loss 0,897 fata de 1,055 cat da ghicitul ratelor de baza, si 58,9%
acuratete (backtest_national.py). Cotele istorice nu exista pentru meciurile
astea, deci NU se poate spune daca bate piata -- doar ca bate ghicitul.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

import national_model
from api_config import load_key, request_config
from fetch_national import COMPETITII_ACASA, COMPETITII_TURNEU, incarca

# Ce afisam: tot ce e competitie oficiala intre nationale, plus amicalele.
NUME_COMPETITII = {
    liga_id: nume for liga_id, (_, nume, _) in COMPETITII_ACASA.items()
}
NUME_COMPETITII.update({liga_id: nume for liga_id, (_, nume) in COMPETITII_TURNEU.items()})

# Cate meciuri trebuie sa aiba o nationala in ultimii patru ani ca sa avem ce
# spune despre ea. O nationala joaca ~10 pe an; sub 20 inseamna ca e fie
# exotica, fie abia intrata in circuit.
PRAG_INCREDERE_RIDICATA = 25
PRAG_INCREDERE_MEDIE = 12


def _api(base, headers, path, **params):
    r = requests.get(f"{base}/{path}", headers=headers, params=params, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def fixturi_viitoare(base, headers, zile: int) -> list[dict]:
    """Meciurile de nationale din fereastra afisata.

    O cerere per zi, nu per competitie: /fixtures?date= intoarce tot ce se
    joaca in lume in ziua aceea, iar noi pastram doar competitiile noastre.
    Trei cereri in loc de douazeci.
    """
    azi = datetime.now().date()
    out = []
    for i in range(zile):
        zi = (azi + timedelta(days=i)).isoformat()
        try:
            raspuns = _api(base, headers, "fixtures", date=zi)
        except Exception as exc:
            print(f"  nu am putut lua meciurile zilei {zi}: {str(exc)[:60]}")
            continue
        for item in raspuns:
            liga_id = item["league"]["id"]
            if liga_id not in NUME_COMPETITII:
                continue
            fx = item["fixture"]
            if fx["status"]["short"] not in ("NS", "TBD"):
                continue
            out.append({
                "fixture_id": fx["id"],
                "liga_id": liga_id,
                "liga_nume": NUME_COMPETITII[liga_id],
                "data": fx["date"][:10],
                "ora": fx["date"][11:16],
                "home": item["teams"]["home"]["name"],
                "away": item["teams"]["away"]["name"],
            })
    return out


def cote(base, headers, fixture_id: int) -> dict:
    """Cotele medii 1X2 si peste/sub 2.5, ca reper si ca filtru pentru selectii."""
    try:
        raspuns = _api(base, headers, "odds", fixture=fixture_id)
    except Exception:
        return {}

    valori: dict[str, list[float]] = {}

    def adauga(cheie: str, cota) -> None:
        try:
            valori.setdefault(cheie, []).append(float(cota))
        except (TypeError, ValueError):
            pass

    for item in raspuns:
        for casa in item.get("bookmakers", []):
            for pariu in casa.get("bets", []):
                nume = pariu.get("name")
                for v in pariu.get("values", []):
                    if nume == "Match Winner":
                        cheie = {"Home": "home", "Draw": "draw",
                                 "Away": "away"}.get(v.get("value"))
                        if cheie:
                            adauga(cheie, v.get("odd"))
                    elif nume == "Goals Over/Under":
                        cheie = {"Over 2.5": "over25",
                                 "Under 2.5": "under25"}.get(v.get("value"))
                        if cheie:
                            adauga(cheie, v.get("odd"))
    return {k: round(float(np.mean(v)), 2) for k, v in valori.items() if v}


def construieste_predictii(zile: int) -> list[dict]:
    """Lista de meciuri de nationale, gata de pus in predictions.json."""
    hist = incarca()
    if hist.empty:
        print("  lipseste istoricul de nationale (ruleaza fetch_national.py)")
        return []

    key = load_key()
    if not key:
        print("  lipseste cheia API-Football; sar peste nationale")
        return []
    base, headers = request_config(key)

    fixturi = fixturi_viitoare(base, headers, zile)
    if not fixturi:
        print("  niciun meci de nationale in urmatoarele zile")
        return []
    print(f"  {len(fixturi)} meciuri de nationale gasite")

    azi = pd.Timestamp(datetime.now().date())
    model = national_model.fit(hist, azi)
    if model is None:
        print("  prea putine date pentru modelul de nationale")
        return []

    # team_context se asteapta la coloanele de suturi; nationalele nu le au.
    hist_context = hist.assign(hst=np.nan, ast=np.nan)

    from dixon_coles import markets_from_rates  # noqa: F401  (documentar)
    from predict import head_to_head, team_context, top_scores

    out = []
    for f in fixturi:
        rezultat = national_model.probabilitati(model, f["home"], f["away"])
        if rezultat is None:
            print(f"    sar peste {f['home']} - {f['away']} (echipa fara istoric)")
            continue

        p, lam, mu = rezultat["probs"], rezultat["lam"], rezultat["mu"]
        n_home = national_model.meciuri_jucate(hist, f["home"], azi)
        n_away = national_model.meciuri_jucate(hist, f["away"], azi)
        n_min = min(n_home, n_away)
        confidence = ("ridicata" if n_min >= PRAG_INCREDERE_RIDICATA
                      else "medie" if n_min >= PRAG_INCREDERE_MEDIE else "scazuta")

        fav, pf = ((f["home"], p["p_home"]) if p["p_home"] > p["p_away"]
                   else (f["away"], p["p_away"]))
        explicatie = (
            f"{fav} e favorita, cu {pf:.0%} sanse de victorie. "
            f"Goluri asteptate: {lam:.2f} pentru {f['home']}, {mu:.2f} pentru {f['away']}. "
            f"Fortele sunt estimate dintr-un model antrenat separat pe meciuri "
            f"intre echipe nationale ({len(hist):,} meciuri din 2015 incoace), "
            f"pentru ca nationalele nu apar in datele de club. "
            f"{f['home']} are {n_home} meciuri in ultimii patru ani, "
            f"{f['away']} are {n_away}. "
            "Modelul a fost verificat pe meciuri neatinse la antrenare, unde a fost "
            "clar mai bun decat ratele de baza, dar pentru nationale nu exista cote "
            "istorice, deci nu s-a putut compara cu piata."
        )

        out.append({
            "id": f"NAT{f['fixture_id']}",
            "league": f"NAT_{f['liga_id']}",
            "league_name": f["liga_nume"],
            "date": f["data"],
            "time": f["ora"],
            "home": f["home"],
            "away": f["away"],
            "probs": {k: round(float(v), 4) for k, v in p.items()},
            "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
            "confidence": confidence,
            "sample": {"home_matches": n_home, "away_matches": n_away},
            "top_scores": top_scores(lam, mu, model.rho),
            "reference_odds": cote(base, headers, f["fixture_id"]),
            "context": {
                "home": team_context(hist_context, f["home"]),
                "away": team_context(hist_context, f["away"]),
                "h2h": head_to_head(hist, f["home"], f["away"]),
            },
            "explanation": explicatie,
        })

    print(f"  {len(out)} predictii pentru nationale")
    return out

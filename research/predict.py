"""Pipeline de productie: antreneaza pe tot istoricul, prezice meciurile viitoare.

Ruleaza zilnic (local sau in GitHub Actions) si scrie predictions.json,
pe care il citeste aplicatia Flutter. Fara chei API, fara server.
"""
from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.special import gammaln

from backtest import WINDOW_DAYS
from backtest_xg import XI, fit_on
from data_loader import load_all
from dixon_coles import MAX_GOALS, markets_from_rates
from download_data import LEAGUES, SEASONS, fetch

ALPHA = 0.50  # pondere goluri vs suturi, aleasa pe perioada de validare
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
OUT = Path(__file__).parent.parent / "app" / "assets" / "predictions.json"


def refresh_current_season() -> None:
    """Re-descarca sezonul curent ca sa avem rezultatele din ultima etapa."""
    current = SEASONS[-1]
    for code in LEAGUES:
        path = Path(__file__).parent / "data" / current / f"{code}.csv"
        if path.exists():
            path.unlink()
        fetch(current, code)


def get_fixtures() -> pd.DataFrame:
    r = requests.get(FIXTURES_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    # Citim octetii, nu r.text: requests ghiceste ISO-8859-1 si sparge BOM-ul
    # UTF-8 in trei caractere, iar prima coloana devine de necitit.
    fx = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
    fx.columns = [c.strip() for c in fx.columns]
    fx = fx[fx["Div"].isin(LEAGUES)].copy()
    fx["date"] = pd.to_datetime(fx["Date"], format="mixed", dayfirst=True, errors="coerce")
    return fx.dropna(subset=["date", "HomeTeam", "AwayTeam"])


def team_context(hist: pd.DataFrame, team: str, n: int = 6) -> dict:
    """Forma recenta si mediile echipei -- partea de 'analiza pe istoric'."""
    games = hist[(hist["home"] == team) | (hist["away"] == team)].tail(n)
    form, gf, ga, sot = [], [], [], []
    for _, g in games.iterrows():
        at_home = g["home"] == team
        scored, conceded = (g["hg"], g["ag"]) if at_home else (g["ag"], g["hg"])
        form.append("V" if scored > conceded else ("E" if scored == conceded else "I"))
        gf.append(scored)
        ga.append(conceded)
        s = g["hst"] if at_home else g["ast"]
        if pd.notna(s):
            sot.append(float(s))
    return {
        "form": form,
        "goals_for_avg": round(float(np.mean(gf)), 2) if gf else None,
        "goals_against_avg": round(float(np.mean(ga)), 2) if ga else None,
        "shots_on_target_avg": round(float(np.mean(sot)), 2) if sot else None,
        "matches_analysed": len(games),
    }


def head_to_head(hist: pd.DataFrame, home: str, away: str, n: int = 5) -> list[dict]:
    mask = (((hist["home"] == home) & (hist["away"] == away))
            | ((hist["home"] == away) & (hist["away"] == home)))
    rows = []
    for _, g in hist[mask].tail(n).iterrows():
        rows.append({
            "date": g["date"].strftime("%Y-%m-%d"),
            "home": g["home"],
            "away": g["away"],
            "score": f"{int(g['hg'])}-{int(g['ag'])}",
        })
    return rows[::-1]


def top_scores(lam: float, mu: float, rho: float, k: int = 5) -> list[dict]:
    idx = np.arange(MAX_GOALS + 1)
    mat = np.exp((idx * np.log(lam) - lam - gammaln(idx + 1))[:, None]
                 + (idx * np.log(mu) - mu - gammaln(idx + 1))[None, :])
    mat[0, 0] *= 1 - lam * mu * rho
    mat[0, 1] *= 1 + lam * rho
    mat[1, 0] *= 1 + mu * rho
    mat[1, 1] *= 1 - rho
    mat = np.maximum(mat, 0)
    mat /= mat.sum()
    flat = [(f"{i}-{j}", float(mat[i, j])) for i in range(6) for j in range(6)]
    flat.sort(key=lambda x: -x[1])
    return [{"score": s, "p": round(p, 4)} for s, p in flat[:k]]


def explain(home, away, p, ctx_h, ctx_a, lam, mu, rank_h, rank_a, n_teams) -> str:
    """Explicatie determinista, in romana. Fara LLM: reproductibila si gratuita."""
    parts = []
    if abs(p["p_home"] - p["p_away"]) < 0.08:
        parts.append(
            "Meci echilibrat: modelul nu vede un favorit clar "
            f"({p['p_home']:.0%} / {p['p_draw']:.0%} / {p['p_away']:.0%})."
        )
    else:
        fav, pf = (home, p["p_home"]) if p["p_home"] > p["p_away"] else (away, p["p_away"])
        parts.append(f"{fav} e favorita, cu {pf:.0%} sanse de victorie.")

    parts.append(f"Goluri asteptate: {lam:.2f} pentru {home}, {mu:.2f} pentru {away}.")

    if ctx_h["form"] and ctx_a["form"]:
        forma_h = "".join(ctx_h["form"])
        forma_a = "".join(ctx_a["form"])
        parts.append(
            f"Forma recenta — {home}: {forma_h}, {away}: {forma_a} "
            "(cel mai recent meci la dreapta)."
        )

    parts.append(
        f"In clasamentul intern al modelului, {home} e pe locul {rank_h} la atac, "
        f"{away} pe {rank_a}, din {n_teams} echipe."
    )

    if p["p_over25"] > 0.56:
        parts.append(f"Se asteapta un meci deschis: {p['p_over25']:.0%} sanse la peste 2.5 goluri.")
    elif p["p_over25"] < 0.44:
        under = 1 - p["p_over25"]
        parts.append(f"Se asteapta un meci inchis: {under:.0%} sanse la sub 2.5 goluri.")

    parts.append(
        "Probabilitatile sunt bine calibrate istoric, dar modelul NU bate cotele de "
        "inchidere. Foloseste-le ca reper de plecare, nu ca garantie."
    )
    return " ".join(parts)


def main() -> None:
    print("Actualizez sezonul curent...")
    refresh_current_season()
    hist = load_all()
    print(f"  {len(hist):,} meciuri in istoric, pana la {hist['date'].max().date()}")

    fx = get_fixtures()
    print(f"  {len(fx)} meciuri viitoare in ligile acoperite")

    today = pd.Timestamp(datetime.now().date())
    out = []
    for div, group in fx.groupby("Div"):
        league = hist[hist["div"] == div]
        train = league[league["date"] >= today - pd.Timedelta(days=WINDOW_DAYS)]
        if len(train) < 150:
            print(f"  {div}: prea putine date, sar peste")
            continue
        teams = sorted(set(train["home"]) | set(train["away"]))
        idx = {t: k for k, t in enumerate(teams)}
        fit_g, _ = fit_on(train, today, ("hg", "ag"), XI, {}, teams, idx, len(teams))
        fit_s, _ = fit_on(train, today, ("hst", "ast"), XI, {}, teams, idx, len(teams))
        if fit_g is None:
            continue
        shots = train.dropna(subset=["hst", "ast"])
        total_sot = shots["hst"].sum() + shots["ast"].sum() if len(shots) else 0
        conv = float((shots["hg"].sum() + shots["ag"].sum()) / total_sot) if total_sot > 0 else 0.33
        atk_rank = {t: r + 1 for r, t in enumerate(
            sorted(teams, key=lambda name: -fit_g.attack[idx[name]]))}

        n_div = 0
        for _, m in group.iterrows():
            home = str(m["HomeTeam"]).strip()
            away = str(m["AwayTeam"]).strip()
            if home not in fit_g.teams or away not in fit_g.teams:
                print(f"  {div}: sar peste {home} - {away} (istoric insuficient)")
                continue
            lg, mg = fit_g.rates(home, away)
            if fit_s is not None and home in fit_s.teams and away in fit_s.teams:
                ls, ms = fit_s.rates(home, away)
                lam = float(np.exp(ALPHA * np.log(lg) + (1 - ALPHA) * np.log(ls * conv)))
                mu = float(np.exp(ALPHA * np.log(mg) + (1 - ALPHA) * np.log(ms * conv)))
            else:
                lam, mu = lg, mg

            p = markets_from_rates(lam, mu, fit_g.rho)
            p["p_under25"] = 1 - p["p_over25"]
            p["p_no_btts"] = 1 - p["p_btts"]
            ctx_h = team_context(league, home)
            ctx_a = team_context(league, away)

            # Cate meciuri sta in spatele fiecarei estimari. O echipa nou promovata
            # are foarte putine meciuri in liga curenta, deci forta ei e prost
            # estimata -- aplicatia trebuie sa spuna asta, nu sa ascunda.
            n_home = int(((train["home"] == home) | (train["away"] == home)).sum())
            n_away = int(((train["home"] == away) | (train["away"] == away)).sum())
            n_min = min(n_home, n_away)
            confidence = "ridicata" if n_min >= 40 else ("medie" if n_min >= 15 else "scazuta")

            odds = {}
            for key, col in (("home", "B365H"), ("draw", "B365D"), ("away", "B365A")):
                value = m.get(col)
                if pd.notna(value):
                    odds[key] = float(value)

            match_id = f"{div}_{m['date'].strftime('%Y%m%d')}_{home}_{away}".replace(" ", "")
            out.append({
                "id": match_id,
                "league": div,
                "league_name": LEAGUES[div],
                "date": m["date"].strftime("%Y-%m-%d"),
                "time": str(m.get("Time", "")),
                "home": home,
                "away": away,
                "probs": {k: round(v, 4) for k, v in p.items()},
                "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
                "confidence": confidence,
                "sample": {"home_matches": n_home, "away_matches": n_away},
                "top_scores": top_scores(lam, mu, fit_g.rho),
                "reference_odds": odds,
                "context": {
                    "home": ctx_h,
                    "away": ctx_a,
                    "h2h": head_to_head(league, home, away),
                },
                "explanation": explain(home, away, p, ctx_h, ctx_a, lam, mu,
                                       atk_rank[home], atk_rank[away], len(teams)),
            })
            n_div += 1
        print(f"  {div}: {n_div} predictii")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": {
            "name": "Dixon-Coles + suturi pe poarta",
            "goals_weight": ALPHA,
            "xi": XI,
            "backtest": {
                "matches_tested": 28675,
                "period": "2019-2026",
                "log_loss": 0.99155,
                "accuracy": 0.5175,
                "ece": 0.0070,
                "market_log_loss": 0.96980,
                "beats_market": False,
                "note": ("Calibrare foarte buna, dar modelul NU bate cotele de inchidere "
                         "si nu a produs ROI pozitiv in backtest."),
            },
        },
        "matches": sorted(out, key=lambda x: (x["date"], x["time"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(out)} predictii scrise in {OUT}")


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Durata: {time.time() - start:.1f}s")

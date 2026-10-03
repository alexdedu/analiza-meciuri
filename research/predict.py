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
from data_loader import league_slug, load_all
from dixon_coles import MAX_GOALS, markets_from_rates
from download_data import EXTRA_LEAGUES, LEAGUES, SEASONS, fetch

ALPHA = 0.50  # pondere goluri vs suturi, aleasa pe perioada de validare

# Amestecul de acum, cu cornerele adaugate ca al treilea semn de dominare.
# Masurat in backtest_corners_signal.py pe 28.827 de meciuri: fata de amestecul
# goluri+suturi, log-loss-ul scade cu 0,00077 la 1X2 (t = +3,60) si cu 0,00123
# la peste/sub 2.5 (t = +6,77). Castigul e mic, dar constant de la meci la meci
# si nu costa nimic: cornerele erau deja in fisierele descarcate.
# ALPHA ramane pentru campionatele fara cornere (feedul suplimentar).
W_GOLURI, W_SUTURI, W_CORNERE = 0.45, 0.40, 0.15

# Doar competitiile care apar in aplicatie. Restul raman in model -- ajuta la
# estimarea puterii campionatelor -- dar nu se afiseaza.
LIGI_AFISATE = {
    "E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1", "ROU_Superliga",
}
# Cate zile inainte aratam, inclusiv ziua curenta: joi -> joi, vineri, sambata.
ZILE_AFISATE = 3
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
EXTRA_FIXTURES_URL = "https://www.football-data.co.uk/new_league_fixtures.csv"
OUT = Path(__file__).parent.parent / "app" / "assets" / "predictions.json"


def refresh_current_season() -> int:
    """Re-descarca sezonul curent ca sa avem rezultatele din ultima etapa.

    Nu sterge nimic in avans: `fetch(force=True)` inlocuieste fisierul doar dupa
    ce noile date au ajuns intregi. Altfel o pana de retea ne lasa fara sezonul
    curent, iar modelul ar prezice pe date vechi fara sa spuna nimic.
    """
    current = SEASONS[-1]
    reusite = sum(1 for code in LEAGUES if fetch(current, code, force=True))
    if reusite < len(LEAGUES):
        print(f"  atentie: {len(LEAGUES) - reusite} din {len(LEAGUES)} fisiere "
              "nu s-au putut reimprospata; folosim ce aveam")
    return reusite


def _download_csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    # Citim octetii, nu r.text: requests ghiceste ISO-8859-1 si sparge BOM-ul
    # UTF-8 in trei caractere, iar prima coloana devine de necitit.
    fx = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
    fx.columns = [c.strip() for c in fx.columns]
    return fx


def get_fixtures() -> pd.DataFrame:
    """Meciurile viitoare din ambele feeduri, aduse la aceleasi coloane."""
    parts = []

    try:
        core = _download_csv(FIXTURES_URL)
        core = core[core["Div"].isin(LEAGUES)].copy()
        core["div"] = core["Div"]
        core["home"] = core["HomeTeam"]
        core["away"] = core["AwayTeam"]
        parts.append(core)
    except Exception as exc:
        print(f"  (feedul principal nu a raspuns: {str(exc)[:80]})")

    # Codul tarii nu apare in feedul suplimentar, doar numele ei.
    code_by_country = {country: code for code, (country, _) in EXTRA_LEAGUES.items()}
    try:
        extra = _download_csv(EXTRA_FIXTURES_URL)
    except Exception as exc:
        print(f"  (feedul suplimentar nu a raspuns: {str(exc)[:80]})")
        extra = pd.DataFrame()
    if not extra.empty and {"Country", "League", "Home", "Away"}.issubset(extra.columns):
        extra = extra[extra["Country"].isin(code_by_country)].copy()
        extra["div"] = (extra["Country"].map(code_by_country) + "_"
                        + extra["League"].map(league_slug))
        extra["home"] = extra["Home"]
        extra["away"] = extra["Away"]
        parts.append(extra)

    if not parts:
        # Amandoua feedurile au picat. Mai departe n-am ce prezice, iar o lista
        # goala ar sterge meciurile din aplicatie -- deci oprim cu eroare.
        raise RuntimeError("Niciun feed de meciuri viitoare nu a raspuns.")

    keep = ["div", "Date", "Time", "home", "away",
            "AvgH", "AvgD", "AvgA", "B365H", "B365D", "B365A",
            "Avg>2.5", "Avg<2.5"]
    frames = []
    for part in parts:
        for col in keep:
            if col not in part.columns:
                part[col] = pd.NA
        frames.append(part[keep])

    fx = pd.concat(frames, ignore_index=True)
    fx["date"] = pd.to_datetime(fx["Date"], format="mixed", dayfirst=True, errors="coerce")
    fx["home"] = fx["home"].astype("string").str.strip()
    fx["away"] = fx["away"].astype("string").str.strip()
    fx = fx.dropna(subset=["date", "home", "away"])

    fx = fx[fx["div"].isin(LIGI_AFISATE)]
    azi = pd.Timestamp(datetime.now().date())

    # Feedul tine doar vreo saptamana inainte si se publica de cateva ori pe
    # saptamana. Pentru campionatele care n-au nimic in el, intrebam API-ul:
    # programul exista acolo cu luni inainte.
    lipsesc = [div for div in sorted(LIGI_AFISATE)
               if fx[(fx["div"] == div) & (fx["date"] >= azi)].empty]
    if lipsesc:
        try:
            from fixturi_api import ZILE_CERUTE, fixturi_lipsa
            from data_loader import load_all
            completare = fixturi_lipsa(lipsesc, load_all(), ZILE_CERUTE)
            if not completare.empty:
                completare["date"] = pd.to_datetime(completare["Date"],
                                                    format="%d/%m/%Y")
                for col in fx.columns:
                    if col not in completare.columns:
                        completare[col] = pd.NA
                fx = pd.concat([fx, completare[fx.columns]], ignore_index=True)
                print(f"  {len(completare)} meciuri luate de la API pentru "
                      f"{', '.join(lipsesc)}")
        except Exception as exc:
            print(f"  (completarea de la API a esuat: {str(exc)[:70]})")

    viitoare = fx[fx["date"] >= azi]
    fereastra = viitoare[viitoare["date"] < azi + pd.Timedelta(days=ZILE_AFISATE)]

    # Daca in urmatoarele trei zile nu se joaca nimic in campionate, aratam
    # urmatoarea etapa in loc de o lista goala. Regula de trei zile ramane,
    # doar ca se masoara de la prima zi cu meciuri.
    if fereastra.empty and not viitoare.empty:
        prima = viitoare["date"].min()
        fereastra = viitoare[viitoare["date"] < prima + pd.Timedelta(days=ZILE_AFISATE)]
        print(f"  nimic in trei zile; arat etapa care incepe pe {prima.date()} "
              f"({len(fereastra)} meciuri)")
    return fereastra


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


def _rezultat_dupa_id(match_id: str):
    """Scorul unui meci identificat direct prin fixture-ul din API-Football.

    Asa sunt cupele europene ("EU123") si nationalele ("NAT123"): pentru ele nu
    exista randuri in fisierele football-data, deci singura cale catre rezultat
    e identificatorul.
    """
    try:
        from api_config import load_key, request_config
        key = load_key()
        if not key:
            return None
        base, headers = request_config(key)
        fixture = match_id.removeprefix("NAT").removeprefix("EU")
        r = requests.get(f"{base}/fixtures", headers=headers,
                         params={"id": fixture}, timeout=30)
        r.raise_for_status()
        raspuns = r.json().get("response") or []
        if not raspuns:
            return None
        scor = raspuns[0]["score"]["fulltime"]
        if scor["home"] is None or scor["away"] is None:
            return None
        return int(scor["home"]), int(scor["away"])
    except Exception:
        return None


def main() -> None:
    print("Actualizez sezonul curent...")
    refresh_current_season()
    hist = load_all()
    print(f"  {len(hist):,} meciuri in istoric, pana la {hist['date'].max().date()}")

    fx = get_fixtures()
    print(f"  {len(fx)} meciuri viitoare in ligile acoperite")

    # Numele afisat al competitiei vine din datele istorice, ca sa fie identic
    # pentru ambele formate de fisiere.
    nume_liga = dict(zip(hist["div"], hist["league_name"]))

    today = pd.Timestamp(datetime.now().date())
    out = []
    for div, group in fx.groupby("div"):
        league = hist[hist["div"] == div]
        train = league[league["date"] >= today - pd.Timedelta(days=WINDOW_DAYS)]
        if len(train) < 150:
            print(f"  {div}: prea putine date, sar peste")
            continue
        teams = sorted(set(train["home"]) | set(train["away"]))
        idx = {t: k for k, t in enumerate(teams)}
        fit_g, _ = fit_on(train, today, ("hg", "ag"), XI, {}, teams, idx, len(teams))
        fit_s, _ = fit_on(train, today, ("hst", "ast"), XI, {}, teams, idx, len(teams))
        fit_c, _ = fit_on(train, today, ("hc", "ac"), XI, {}, teams, idx, len(teams))
        if fit_g is None:
            continue
        shots = train.dropna(subset=["hst", "ast"])
        total_sot = shots["hst"].sum() + shots["ast"].sum() if len(shots) else 0
        conv = float((shots["hg"].sum() + shots["ag"].sum()) / total_sot) if total_sot > 0 else 0.33
        # Aceeasi aducere pe scara golurilor si pentru cornere.
        cornere = train.dropna(subset=["hc", "ac"])
        total_c = cornere["hc"].sum() + cornere["ac"].sum() if len(cornere) else 0
        conv_c = (float((cornere["hg"].sum() + cornere["ag"].sum()) / total_c)
                  if total_c > 0 else 0.10)
        atk_rank = {t: r + 1 for r, t in enumerate(
            sorted(teams, key=lambda name: -fit_g.attack[idx[name]]))}

        n_div = 0
        for _, m in group.iterrows():
            home = str(m["home"]).strip()
            away = str(m["away"]).strip()
            if home not in fit_g.teams or away not in fit_g.teams:
                print(f"  {div}: sar peste {home} - {away} (istoric insuficient)")
                continue
            lg, mg = fit_g.rates(home, away)
            if fit_s is not None and home in fit_s.teams and away in fit_s.teams:
                ls, ms = fit_s.rates(home, away)
                are_cornere = (fit_c is not None and home in fit_c.teams
                               and away in fit_c.teams)
                if are_cornere:
                    lc, mc = fit_c.rates(home, away)
                    lam = float(np.exp(W_GOLURI * np.log(lg)
                                       + W_SUTURI * np.log(ls * conv)
                                       + W_CORNERE * np.log(lc * conv_c)))
                    mu = float(np.exp(W_GOLURI * np.log(mg)
                                      + W_SUTURI * np.log(ms * conv)
                                      + W_CORNERE * np.log(mc * conv_c)))
                else:
                    # Feedul suplimentar n-are cornere: ramane amestecul vechi.
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
            for key, coloane in (("home", ("AvgH", "B365H")),
                                 ("draw", ("AvgD", "B365D")),
                                 ("away", ("AvgA", "B365A")),
                                 ("over25", ("Avg>2.5",)),
                                 ("under25", ("Avg<2.5",))):
                for col in coloane:
                    value = m.get(col)
                    if value is not None and pd.notna(value):
                        odds[key] = float(value)
                        break

            match_id = f"{div}_{m['date'].strftime('%Y%m%d')}_{home}_{away}".replace(" ", "")
            out.append({
                "id": match_id,
                "league": div,
                "league_name": nume_liga.get(div, div),
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


    # Cupele europene vin din alta sursa (API-Football) si folosesc un model in
    # plus, pentru ca echipele sunt din campionate diferite. Daca ceva lipseste
    # -- cheia, puterile campionatelor, conexiunea -- pipeline-ul merge mai
    # departe cu meciurile interne in loc sa cada de tot.
    try:
        from predict_europa import construieste_predictii
        print("Cupe europene:")
        out.extend(construieste_predictii(hist))
    except Exception as exc:
        print(f"  cupele europene au fost sarite: {str(exc)[:100]}")

    # Nationalele au model propriu: nu apar in niciun campionat, deci fortele
    # lor nu se pot deduce din datele de club. In pauzele competitionale, ele
    # sunt singurul lucru care se joaca.
    try:
        from predict_national import construieste_predictii as predictii_nationale
        print("Echipe nationale:")
        out.extend(predictii_nationale(ZILE_AFISATE))
    except Exception as exc:
        print(f"  nationalele au fost sarite: {str(exc)[:100]}")

    # Cornere si cartonase, doar unde exista datele: campionatele din feedul
    # principal. Nu intra in recomandari (vezi predict_counts.py).
    selectii_contori = []
    try:
        from predict_counts import imbogateste, selectii as selectii_contori_fn
        n_extra = imbogateste(out, hist)
        # Toti candidatii: gruparea pe meciuri alege mai departe.
        selectii_contori = selectii_contori_fn(out, toate=True)
        # Nationalele NU primesc cornere si cartonase, desi avem statisticile
        # adunate si modelul scris (predict_counts_national.py). Motivul e
        # masurat in backtest_counts_national.py: pe 409 meciuri de verificare,
        # modelul e mai slab decat media pe absolut toate pietele (-0,01 pana
        # la -0,50 la log-loss), fiindca o nationala are ~12 meciuri in bazin,
        # iar din atatea nu ies forte, iese zgomot. Se reia masuratoarea cand
        # se aduna de doua-trei ori mai multe date.
        print(f"Cornere si cartonase: {n_extra} meciuri imbogatite")
    except Exception as exc:
        print(f"  cornerele si cartonasele au fost sarite: {str(exc)[:90]}")

    from recomandari import construieste as construieste_recomandari
    from recomandari import grupeaza_pe_meci

    # Gruparea e cea care ajunge in aplicatie: un meci, cu toate pietele lui
    # intr-un loc, ca alegerea sa fie a utilizatorului. Lista plata ramane,
    # fiindca din ea se noteaza selectiile in evidenta.
    toate_cu_cota = construieste_recomandari(out, toate=True)
    meciuri_recomandate = grupeaza_pe_meci(toate_cu_cota, selectii_contori)

    # Ce s-a afisat efectiv, ca sa notam in evidenta exact atat.
    afisate = {(m["match_id"], p["market"])
               for m in meciuri_recomandate for p in m["picks"]}
    # Lista plata isi pastreaza forma veche, cu toate campurile ei: versiunile
    # mai vechi ale aplicatiei o citesc si ar cadea fara ele.
    recomandari = [c for c in toate_cu_cota
                   if (c["match_id"], c["market"]) in afisate]
    de_notat = recomandari + [c for c in selectii_contori
                              if (c["match_id"], c["market"]) in afisate]

    # Fisa de rezultate: notam selectiile de azi si verificam ce s-a intamplat
    # cu cele mai vechi. Daca ceva pica aici, predictiile de azi tot se scriu.
    import scorecard
    try:
        # Doar ce se afiseaza se si noteaza: evidenta trebuie sa raspunda la
        # "ce s-a intamplat cu selectiile pe care le-am vazut".
        selectii = scorecard.adauga(scorecard.incarca(), de_notat)
        # Arhivele football-data publica scorurile cu una-doua zile intarziere.
        # Pentru verificarea selectiilor luam scorul de la API-Football, care il
        # are in aceeasi seara; fara cheie, `rezolvator` intoarce None si
        # ramane doar cautarea in istoric.
        from rezultate_api import rezolvator
        selectii, rezolvate_acum = scorecard.rezolva(
            selectii, hist,
            rezultat_dupa_id=_rezultat_dupa_id,
            scor_extern=rezolvator())
        scorecard.salveaza(selectii)
        bilant = scorecard.rezumat(selectii)
        # Lista propriu-zisa: ecranul principal arata doar trei zile, deci fara
        # ea selectiile jucate ar disparea fara urma.
        bilant["selections"] = scorecard.recente(selectii)
        print(f"Fisa de rezultate: {bilant['resolved']} verificate din {bilant['total']}"
              + (f", {bilant['hits']} reusite ({bilant['hit_rate']:.0%})"
                 if bilant['resolved'] else "")
              + (f", {rezolvate_acum} noi" if rezolvate_acum else ""))
    except Exception as exc:
        print(f"  fisa de rezultate a esuat: {str(exc)[:90]}")
        bilant = None
    print(f"\nMeciuri recomandate: {len(meciuri_recomandate)} "
          f"({len(de_notat)} selectii in total)")
    for m in meciuri_recomandate:
        print(f"  {m['home']} - {m['away']}")
        for p in m["picks"]:
            cota = (f"cota {p['odds']}" if p.get("odds")
                    else f"cota corecta {p['fair_odds']}")
            print(f"     [{p['family']}] {p['market_label']}: "
                  f"{p['probability']:.0%}, {cota}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Un meci, cu toate pietele lui la un loc: rezultat, goluri, cornere,
        # cartonase. Lista plata ramane pentru compatibilitate cu versiunile
        # mai vechi ale aplicatiei.
        "recommended_matches": meciuri_recomandate,
        "recommendations": recomandari,
        # Tot pentru versiunile mai vechi, care au o sectiune separata.
        "count_picks": [c for c in selectii_contori
                        if (c["match_id"], c["market"]) in afisate][:4],
        "track_record": bilant,
        "model": {
            "name": "Dixon-Coles + suturi pe poarta + cornere",
            "goals_weight": W_GOLURI,
            "shots_weight": W_SUTURI,
            "corners_weight": W_CORNERE,
            "xi": XI,
            "backtest": {
                "matches_tested": 60539,
                "period": "2019-2026",
                "log_loss": 1.01648,
                "accuracy": 0.4997,
                "ece": 0.0080,
                "market_log_loss": 0.98846,
                "beats_market": False,
                "note": ("Calibrare foarte buna, dar modelul NU bate cotele de inchidere "
                         "si nu a produs ROI pozitiv in backtest."),
            },
        },
        "matches": sorted(out, key=lambda x: (x["date"], x["time"])),
    }
    # Zero meciuri inseamna doua lucruri complet diferite: ori e pauza
    # competitionala (si atunci aplicatia trebuie sa spuna asta, nu sa arate
    # meciuri de saptamana trecuta), ori sursele au picat (si atunci fisierul
    # vechi e mai bun decat unul gol). Le deosebim intreband API-ul cand se
    # reiau meciurile: daca raspunde, stim ca pauza e reala.
    if not out:
        etapa = None
        try:
            from rezultate_api import urmatoarea_etapa
            etapa = urmatoarea_etapa()
        except Exception as exc:
            print(f"  (nu am putut afla cand se reiau meciurile: {str(exc)[:70]})")

        if etapa and etapa.get("date"):
            payload["next_round"] = etapa
            print(f"\nPauza competitionala. Urmatoarele meciuri pe "
                  f"{etapa['date']}: {', '.join(etapa['competitions'])}")
        elif OUT.exists():
            try:
                vechi = json.loads(OUT.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                vechi = {}
            if vechi.get("matches"):
                print(f"\nNiciun meci nou de prezis si nu stiu de ce. Pastram "
                      f"cele {len(vechi['matches'])} predictii existente.")
                return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(out)} predictii scrise in {OUT}")


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Durata: {time.time() - start:.1f}s")

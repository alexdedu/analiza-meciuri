"""Model pentru meciuri intre echipe din campionate diferite.

Problema: modelul nostru masoara fiecare echipa fata de restul ligii sale. O
echipa de mijlocul clasamentului din Olanda si una din Spania au amandoua atac
aproape de zero, desi nu sunt la fel de bune. Scarile sunt separate.

Solutia: meciurile din cupele europene sunt singurul loc unde scarile se ating.
Adaugam un parametru de putere `s` pentru fiecare campionat si il estimam din
acele meciuri, tinand fixe fortele echipelor:

    log lambda_gazda  = atac_A + s_LA + aparare_B - s_LB + avantaj_teren
    log lambda_oaspete = atac_B + s_LB + aparare_A - s_LA

Doar ~30 de parametri, estimati pe mii de meciuri: robust si verificabil.
Suma lui s e fixata la zero, altfel modelul ar avea o libertate inutila.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

from backtest import WINDOW_DAYS
from backtest_xg import XI, fit_on
from data_loader import load_all
from dixon_coles import MAX_GOALS
from team_matching import build_matcher

EUROPA = Path(__file__).parent / "data" / "europa"
XI_EURO = 0.0015  # meciurile europene sunt rare: uitam mai incet decat in campionat

# Campionate din afara Europei. O echipa din cupele UEFA nu poate juca in ele,
# deci daca potrivirea de nume duce acolo, potrivirea e gresita -- s-a intamplat
# cu "SC Braga" (Portugalia), confundata cu "Bragantino" (Brazilia). Verificarea
# asta prinde clasa intreaga de greseli, nu doar cazul cunoscut.
PREFIXE_NEEUROPENE = ("BRA_", "MEX_", "USA_", "ARG_", "JPN_", "CHN_")


def este_european(div: str | None) -> bool:
    return bool(div) and not str(div).startswith(PREFIXE_NEEUROPENE)


# --------------------------------------------------------------------------
# 1. Pregatirea datelor
# --------------------------------------------------------------------------

def incarca_europa(hist: pd.DataFrame) -> pd.DataFrame:
    """Meciurile europene, cu numele traduse in cele din datele noastre."""
    fisiere = sorted(glob.glob(str(EUROPA / "*.csv")))
    if not fisiere:
        raise SystemExit("Lipsesc datele europene. Ruleaza fetch_europe.py.")
    eu = pd.concat([pd.read_csv(f) for f in fisiere], ignore_index=True)
    eu["date"] = pd.to_datetime(eu["date"])

    nume_locale = sorted(set(hist["home"]) | set(hist["away"]))
    match = build_matcher(nume_locale)
    harta = {n: match(n) for n in set(eu["home"]) | set(eu["away"])}

    eu["home_local"] = eu["home"].map(harta)
    eu["away_local"] = eu["away"].map(harta)
    eu = eu.dropna(subset=["home_local", "away_local"]).copy()
    eu["hg"] = eu["hg"].astype(int)
    eu["ag"] = eu["ag"].astype(int)
    return eu.sort_values("date").reset_index(drop=True)


def liga_echipei(hist: pd.DataFrame) -> dict:
    """Ultimul campionat in care a jucat fiecare echipa, pe fiecare data.

    O echipa poate promova sau retrograda, deci apartenenta se schimba in timp.
    Pastram, pentru fiecare echipa, lista (data, campionat) ca sa putem intreba
    "in ce liga era la momentul X".
    """
    lung = pd.concat([
        hist[["date", "home", "div"]].rename(columns={"home": "team"}),
        hist[["date", "away", "div"]].rename(columns={"away": "team"}),
    ], ignore_index=True).sort_values("date")
    return {t: g[["date", "div"]].to_numpy() for t, g in lung.groupby("team")}


def div_la_data(istoric_echipa, moment) -> str | None:
    """Campionatul in care juca echipa cel mai recent inainte de `moment`."""
    if istoric_echipa is None:
        return None
    date = istoric_echipa[:, 0]
    poz = np.searchsorted(date, np.datetime64(moment)) - 1
    return istoric_echipa[poz, 1] if poz >= 0 else None


# --------------------------------------------------------------------------
# 2. Fortele echipelor la momentul fiecarui meci european
# --------------------------------------------------------------------------

def ratinguri_saptamanale(hist: pd.DataFrame, momente: list[pd.Timestamp],
                          divs: set[str], verbose: bool = True) -> dict:
    """Antreneaza modelul pe fiecare campionat, la fiecare moment cerut.

    Meciurile europene sunt grupate in ~200 de saptamani, deci antrenam doar
    pentru acele momente, nu pentru fiecare zi.
    """
    rezultat = {}
    for i, moment in enumerate(momente):
        for div in divs:
            liga = hist[(hist["div"] == div) & (hist["date"] < moment)]
            train = liga[liga["date"] >= moment - pd.Timedelta(days=WINDOW_DAYS)]
            if len(train) < 150:
                continue
            teams = sorted(set(train["home"]) | set(train["away"]))
            idx = {t: k for k, t in enumerate(teams)}
            fit, _ = fit_on(train, moment, ("hg", "ag"), XI, {}, teams, idx, len(teams))
            if fit is None:
                continue
            rezultat[(moment, div)] = fit
        if verbose and (i + 1) % 25 == 0:
            print(f"    {i + 1}/{len(momente)} momente", flush=True)
    return rezultat


# --------------------------------------------------------------------------
# 3. Estimarea puterii campionatelor
# --------------------------------------------------------------------------

def _tau(h, a, lam, mu, rho):
    t = np.ones_like(lam)
    m00 = (h == 0) & (a == 0)
    m01 = (h == 0) & (a == 1)
    m10 = (h == 1) & (a == 0)
    m11 = (h == 1) & (a == 1)
    t[m00] = np.maximum(1 - lam[m00] * mu[m00] * rho, 1e-10)
    t[m01] = np.maximum(1 + lam[m01] * rho, 1e-10)
    t[m10] = np.maximum(1 + mu[m10] * rho, 1e-10)
    t[m11] = np.maximum(1 - rho, 1e-10)
    return t


def fit_puteri(df: pd.DataFrame, ligi: list[str], moment: pd.Timestamp):
    """Estimeaza puterea fiecarui campionat plus avantajul terenului in cupe."""
    idx = {d: i for i, d in enumerate(ligi)}
    ih = df["div_home"].map(idx).to_numpy()
    ia = df["div_away"].map(idx).to_numpy()
    atk_h, def_h = df["atk_home"].to_numpy(), df["def_home"].to_numpy()
    atk_a, def_a = df["atk_away"].to_numpy(), df["def_away"].to_numpy()
    hg, ag = df["hg"].to_numpy(float), df["ag"].to_numpy(float)
    varsta = (moment - df["date"]).dt.days.to_numpy(float)
    w = np.exp(-XI_EURO * varsta)

    n = len(ligi)

    def neg_ll(p):
        s = np.concatenate([p[:n - 1], [-p[:n - 1].sum()]])  # suma fixata la zero
        gamma, rho = p[-2], p[-1]
        lam = np.exp(atk_h + s[ih] + def_a - s[ia] + gamma)
        mu = np.exp(atk_a + s[ia] + def_h - s[ih])
        lam = np.clip(lam, 1e-6, 12)
        mu = np.clip(mu, 1e-6, 12)
        tau = _tau(df["hg"].to_numpy(), df["ag"].to_numpy(), lam, mu, rho)
        ll = w * (np.log(tau) + hg * np.log(lam) - lam + ag * np.log(mu) - mu)
        return -ll.sum()

    p0 = np.concatenate([np.zeros(n - 1), [0.25, -0.05]])
    bounds = [(-1.5, 1.5)] * (n - 1) + [(-0.5, 1.0), (-0.15, 0.15)]
    res = minimize(neg_ll, p0, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 500})
    s = np.concatenate([res.x[:n - 1], [-res.x[:n - 1].sum()]])
    return dict(zip(ligi, s)), float(res.x[-2]), float(res.x[-1])


def probabilitati(lam: float, mu: float, rho: float) -> tuple[float, float, float]:
    k = np.arange(MAX_GOALS + 1)
    mat = np.exp((k * np.log(lam) - lam - gammaln(k + 1))[:, None]
                 + (k * np.log(mu) - mu - gammaln(k + 1))[None, :])
    mat[0, 0] *= 1 - lam * mu * rho
    mat[0, 1] *= 1 + lam * rho
    mat[1, 0] *= 1 + mu * rho
    mat[1, 1] *= 1 - rho
    mat = np.maximum(mat, 0)
    mat /= mat.sum()
    d = k[:, None] - k[None, :]
    return float(mat[d > 0].sum()), float(mat[d == 0].sum()), float(mat[d < 0].sum())


if __name__ == "__main__":
    sys.exit("Acest fisier e o biblioteca. Ruleaza backtest_europa.py.")

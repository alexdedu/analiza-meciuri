"""Model pentru cornere si cartonase: cine le produce si cine le provoaca.

Structura e aceeasi ca la goluri -- fiecare echipa are o forta de "producere"
si una de "concedere", plus un avantaj al terenului comun -- dar fara corectia
Dixon-Coles pentru scoruri mici: la cornere nu exista fenomenul de 0-0 in exces
care a facut-o necesara la goluri.

Doua deosebiri fata de goluri conteaza la interpretare:

1. Cartonasele depind mult de arbitru, iar arbitrul nu intra in model. Asta
   inseamna zgomot in plus pe care nu-l putem explica -- se vede in calibrare.
2. Distributia reala e mai imprastiata decat Poisson (unele meciuri "se aprind"
   si atunci se aduna si cornere, si cartonase). De aceea calibrarea se masoara
   inainte sa iasa ceva in aplicatie, in backtest_counts.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln

# Cornerele trec des de 10 pe echipa; plafonul de la goluri ar taia din masa.
MAX_CONTOR = 30

# Aceeasi penalizare ca la goluri: fixeaza scara, altfel atacul si apararea pot
# aluneca impreuna fara sa schimbe verosimilitatea.
SUM_PENALTY = 1000.0


@dataclass
class CountsFit:
    teams: dict[str, int]
    produce: np.ndarray   # cate produce echipa
    concede: np.ndarray   # cate ii produce adversarul
    home_adv: float
    converged: bool

    def rates(self, home: str, away: str) -> tuple[float, float] | None:
        ih, ia = self.teams.get(home), self.teams.get(away)
        if ih is None or ia is None:
            return None
        lam = float(np.exp(self.produce[ih] + self.concede[ia] + self.home_adv))
        mu = float(np.exp(self.produce[ia] + self.concede[ih]))
        return min(lam, 25.0), min(mu, 25.0)


def fit_counts(home_idx: np.ndarray, away_idx: np.ndarray,
               home_val: np.ndarray, away_val: np.ndarray,
               weights: np.ndarray, n_teams: int,
               teams: dict[str, int]) -> CountsFit:
    hv = home_val.astype(float)
    av = away_val.astype(float)

    def objective(p):
        prod = p[:n_teams]
        conc = p[n_teams:2 * n_teams]
        gamma = p[-1]

        lam = np.exp(prod[home_idx] + conc[away_idx] + gamma)
        mu = np.exp(prod[away_idx] + conc[home_idx])

        ll = weights * (hv * np.log(lam) - lam + av * np.log(mu) - mu)
        neg = -ll.sum() + SUM_PENALTY * prod.sum() ** 2

        # Gradient analitic: fara el, optimizarea pe 600 de parametri ar face
        # zeci de mii de evaluari numerice.
        d_lam = weights * (lam - hv)      # d(neg)/d(log lam)
        d_mu = weights * (mu - av)
        g_prod = np.zeros(n_teams)
        g_conc = np.zeros(n_teams)
        np.add.at(g_prod, home_idx, d_lam)
        np.add.at(g_prod, away_idx, d_mu)
        np.add.at(g_conc, away_idx, d_lam)
        np.add.at(g_conc, home_idx, d_mu)
        g_prod += 2.0 * SUM_PENALTY * prod.sum()
        g_gamma = d_lam.sum()

        return neg, np.concatenate([g_prod, g_conc, [g_gamma]])

    init = np.concatenate([np.zeros(2 * n_teams), [0.05]])
    res = minimize(objective, init, jac=True, method="L-BFGS-B",
                   options={"maxiter": 500})

    return CountsFit(
        teams=teams,
        produce=res.x[:n_teams],
        concede=res.x[n_teams:2 * n_teams],
        home_adv=float(res.x[-1]),
        converged=bool(res.success),
    )


def _poisson_pmf(rata: float) -> np.ndarray:
    k = np.arange(MAX_CONTOR + 1)
    return np.exp(k * np.log(rata) - rata - gammaln(k + 1))


def nb_pmf(medie: float, k: float, maxim: int = 2 * MAX_CONTOR) -> np.ndarray:
    """Binomiala negativa: aceeasi medie ca Poisson, dar cu coada mai groasa.

    Pentru totalul pe meci, Poisson iese prea increzator: sunt meciuri care "se
    aprind" si aduna si cornere, si cartonase, iar varianta reala e mai mare
    decat media. Masurat pe 16.676 de meciuri, trecerea la binomiala negativa
    imbunatateste toate liniile de cartonase si aproape toate cele de cornere.
    """
    x = np.arange(maxim + 1)
    return np.exp(gammaln(x + k) - gammaln(k) - gammaln(x + 1)
                  + k * np.log(k / (k + medie)) + x * np.log(medie / (k + medie)))


def fit_dispersie(medii: np.ndarray, observate: np.ndarray) -> float:
    """Dispersia comuna a totalurilor, invatata doar din trecut."""
    def neg(log_k: float) -> float:
        k = np.exp(log_k)
        return -float(np.sum(
            gammaln(observate + k) - gammaln(k) - gammaln(observate + 1)
            + k * np.log(k / (k + medii)) + observate * np.log(medii / (k + medii))))

    rezultat = minimize_scalar(neg, bounds=(np.log(2.0), np.log(500.0)),
                               method="bounded")
    return float(np.exp(rezultat.x))


def distributii(lam: float, mu: float) -> dict[str, np.ndarray]:
    """Distributiile pentru gazda, oaspete si total."""
    ph, pa = _poisson_pmf(lam), _poisson_pmf(mu)
    total = np.convolve(ph, pa)
    return {"home": ph, "away": pa, "total": total}


def peste(dist: np.ndarray, linie: float) -> float:
    """Probabilitatea ca valoarea sa treaca de linie (linii cu .5, fara egal)."""
    k = np.arange(len(dist))
    return float(dist[k > linie].sum() / dist.sum())


def cine_mai_multe(lam: float, mu: float) -> dict[str, float]:
    """Cine produce mai multe: gazda, egalitate, oaspete."""
    ph, pa = _poisson_pmf(lam), _poisson_pmf(mu)
    m = np.outer(ph, pa)
    m /= m.sum()
    gazda = float(np.tril(m, -1).sum())   # linii > coloane
    egal = float(np.trace(m))
    return {"home": gazda, "draw": egal, "away": 1.0 - gazda - egal}

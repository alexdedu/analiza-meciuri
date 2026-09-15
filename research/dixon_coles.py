"""Modelul Dixon-Coles (1997) cu ponderare temporala exponentiala.

Idee: fiecare echipa are o forta de atac si una de aparare. Numarul de goluri
marcate e aproximativ Poisson, dar scorurile mici (0-0, 1-0, 0-1, 1-1) sunt
corelate -- de aceea Poisson simplu subestimeaza egalurile. Parametrul rho
corecteaza exact acele patru celule.

Meciurile vechi conteaza mai putin: greutate = exp(-xi * zile_in_urma).
xi = 0.0065 => "jumatate de viata" ~107 zile (valoarea din lucrarea originala).

Gradientul e calculat analitic; fara el, un backtest complet ar dura ore.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_GOALS = 10
RHO_BOUND = 0.15
SUM_PENALTY = 100.0  # fixeaza gradul de libertate atac/aparare


def _tau_and_grads(h, a, lam, mu, rho):
    """Corectia Dixon-Coles pentru scoruri mici + derivatele ei partiale."""
    tau = np.ones_like(lam)
    d_lam = np.zeros_like(lam)
    d_mu = np.zeros_like(lam)
    d_rho = np.zeros_like(lam)

    m00 = (h == 0) & (a == 0)
    m01 = (h == 0) & (a == 1)
    m10 = (h == 1) & (a == 0)
    m11 = (h == 1) & (a == 1)

    t = 1.0 - lam[m00] * mu[m00] * rho
    t = np.maximum(t, 1e-10)
    tau[m00] = t
    d_lam[m00] = -mu[m00] * rho / t
    d_mu[m00] = -lam[m00] * rho / t
    d_rho[m00] = -lam[m00] * mu[m00] / t

    t = np.maximum(1.0 + lam[m01] * rho, 1e-10)
    tau[m01] = t
    d_lam[m01] = rho / t
    d_rho[m01] = lam[m01] / t

    t = np.maximum(1.0 + mu[m10] * rho, 1e-10)
    tau[m10] = t
    d_mu[m10] = rho / t
    d_rho[m10] = mu[m10] / t

    t = np.maximum(1.0 - rho, 1e-10)
    tau[m11] = t
    d_rho[m11] = -1.0 / t

    return tau, d_lam, d_mu, d_rho


@dataclass
class DixonColesFit:
    teams: dict[str, int]
    attack: np.ndarray
    defence: np.ndarray
    home_adv: float
    rho: float
    converged: bool

    def rates(self, home: str, away: str) -> tuple[float, float]:
        """Ratele de goluri asteptate (lambda gazda, lambda oaspete)."""
        ih = self.teams.get(home)
        ia = self.teams.get(away)
        # echipa nevazuta in fereastra de antrenare (nou promovata) -> media ligii
        atk_h = self.attack[ih] if ih is not None else 0.0
        def_h = self.defence[ih] if ih is not None else 0.0
        atk_a = self.attack[ia] if ia is not None else 0.0
        def_a = self.defence[ia] if ia is not None else 0.0
        lam = np.exp(atk_h + def_a + self.home_adv)
        mu = np.exp(atk_a + def_h)
        return float(lam), float(mu)

    def score_matrix(self, home: str, away: str) -> np.ndarray:
        """Matricea de probabilitati P(scor gazda = i, scor oaspete = j)."""
        lam, mu = self.rates(home, away)
        k = np.arange(MAX_GOALS + 1)
        log_pois_h = k * np.log(lam) - lam - gammaln(k + 1)
        log_pois_a = k * np.log(mu) - mu - gammaln(k + 1)
        mat = np.exp(log_pois_h[:, None] + log_pois_a[None, :])
        mat[0, 0] *= 1.0 - lam * mu * self.rho
        mat[0, 1] *= 1.0 + lam * self.rho
        mat[1, 0] *= 1.0 + mu * self.rho
        mat[1, 1] *= 1.0 - self.rho
        mat = np.maximum(mat, 0.0)
        return mat / mat.sum()

    def markets(self, home: str, away: str) -> dict[str, float]:
        """Probabilitatile pentru toate pietele pe care le afisam in aplicatie."""
        m = self.score_matrix(home, away)
        idx = np.arange(MAX_GOALS + 1)
        diff = idx[:, None] - idx[None, :]
        total = idx[:, None] + idx[None, :]
        both = (idx[:, None] >= 1) & (idx[None, :] >= 1)
        return {
            "p_home": float(m[diff > 0].sum()),
            "p_draw": float(m[diff == 0].sum()),
            "p_away": float(m[diff < 0].sum()),
            "p_over25": float(m[total > 2.5].sum()),
            "p_under25": float(m[total < 2.5].sum()),
            "p_btts": float(m[both].sum()),
            "p_no_btts": float(m[~both].sum()),
        }


def fit_dixon_coles(
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    weights: np.ndarray,
    n_teams: int,
    teams: dict[str, int],
    init: np.ndarray | None = None,
) -> DixonColesFit:
    hg = home_goals.astype(float)
    ag = away_goals.astype(float)

    def objective(p):
        atk = p[:n_teams]
        dfn = p[n_teams : 2 * n_teams]
        gamma = p[-2]
        rho = p[-1]

        lam = np.exp(atk[home_idx] + dfn[away_idx] + gamma)
        mu = np.exp(atk[away_idx] + dfn[home_idx])
        tau, dt_lam, dt_mu, dt_rho = _tau_and_grads(home_goals, away_goals, lam, mu, rho)

        ll = weights * (np.log(tau) + hg * np.log(lam) - lam + ag * np.log(mu) - mu)
        neg = -ll.sum() + SUM_PENALTY * atk.sum() ** 2

        # d(log-verosimilitate)/d(lambda) * lambda, respectiv pentru mu
        g_lam = weights * (dt_lam * lam + hg - lam)
        g_mu = weights * (dt_mu * mu + ag - mu)

        grad = np.zeros_like(p)
        np.add.at(grad, home_idx, -g_lam)              # atac gazda
        np.add.at(grad, away_idx, -g_mu)               # atac oaspete
        np.add.at(grad, n_teams + away_idx, -g_lam)    # aparare oaspete
        np.add.at(grad, n_teams + home_idx, -g_mu)     # aparare gazda
        grad[-2] = -g_lam.sum()
        grad[-1] = -(weights * dt_rho).sum()
        grad[:n_teams] += 2.0 * SUM_PENALTY * atk.sum()
        return neg, grad

    if init is None or len(init) != 2 * n_teams + 2:
        init = np.concatenate([np.zeros(2 * n_teams), [0.25, -0.05]])

    bounds = [(-3.0, 3.0)] * (2 * n_teams) + [(-1.0, 1.0), (-RHO_BOUND, RHO_BOUND)]
    res = minimize(objective, init, jac=True, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 300, "ftol": 1e-9})
    p = res.x
    return DixonColesFit(
        teams=teams,
        attack=p[:n_teams],
        defence=p[n_teams : 2 * n_teams],
        home_adv=float(p[-2]),
        rho=float(p[-1]),
        converged=bool(res.success),
    )


def markets_from_rates(lam: float, mu: float, rho: float) -> dict[str, float]:
    """Acelasi calcul ca DixonColesFit.markets, dar pornind de la rate brute.

    Necesar cand combinam doua modele (goluri + suturi pe poarta) inainte de
    a construi matricea de scoruri.
    """
    k = np.arange(MAX_GOALS + 1)
    mat = np.exp((k * np.log(lam) - lam - gammaln(k + 1))[:, None]
                 + (k * np.log(mu) - mu - gammaln(k + 1))[None, :])
    mat[0, 0] *= 1.0 - lam * mu * rho
    mat[0, 1] *= 1.0 + lam * rho
    mat[1, 0] *= 1.0 + mu * rho
    mat[1, 1] *= 1.0 - rho
    mat = np.maximum(mat, 0.0)
    mat /= mat.sum()
    idx = np.arange(MAX_GOALS + 1)
    diff = idx[:, None] - idx[None, :]
    total = idx[:, None] + idx[None, :]
    both = (idx[:, None] >= 1) & (idx[None, :] >= 1)
    return {
        "p_home": float(mat[diff > 0].sum()),
        "p_draw": float(mat[diff == 0].sum()),
        "p_away": float(mat[diff < 0].sum()),
        "p_over25": float(mat[total > 2.5].sum()),
        "p_btts": float(mat[both].sum()),
    }

"""Teste pentru cornerele si cartonasele echipelor nationale.

Aceleasi capcane ca la cluburi, plus una specifica: o nationala poate avea
doua meciuri in bazin, iar din doua meciuri nu iese nicio forta -- iese zgomot
care arata ca o predictie.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import fetch_national_stats as colector
import predict_counts_national as pcn

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def statistici(echipa, cornere, galbene, rosii=0):
    return {"team": {"name": echipa}, "statistics": [
        {"type": "Corner Kicks", "value": cornere},
        {"type": "Yellow Cards", "value": galbene},
        {"type": "Red Cards", "value": rosii},
        {"type": "Ball Possession", "value": "55%"},
    ]}


def test_citeste_statisticile_pe_echipa() -> None:
    raspuns = [statistici("Portugal", 7, 2), statistici("Wales", 3, 1, rosii=1)]
    c = colector.citeste_statistici(raspuns, "Portugal")
    verifica(c["hc"] == 7 and c["ac"] == 3, f"cornere gresite: {c}")
    verifica(c["hy"] == 2 and c["ay"] == 1, f"galbene gresite: {c}")
    verifica(c["ar"] == 1 and c["hr"] == 0, f"rosii gresite: {c}")


def test_valorile_lipsa_nu_devin_zero_fals() -> None:
    raspuns = [{"team": {"name": "Portugal"},
                "statistics": [{"type": "Corner Kicks", "value": None}]}]
    c = colector.citeste_statistici(raspuns, "Portugal")
    verifica(c["hc"] == 0, "o valoare lipsa ar trebui sa ramana pe zero implicit")


def _meciuri():
    return pd.DataFrame({
        "fixture_id": [1, 2, 3],
        "date": pd.to_datetime(["2026-09-01", "2026-09-05", "2026-09-08"]),
        "competition": ["NL"] * 3,
        "home": ["Portugal", "Spain", "Italy"],
        "away": ["Wales", "France", "Germany"],
    })


def test_aduna_respecta_bugetul_si_nu_repeta() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        cerute: list[int] = []

        def fetch(fixture_id):
            cerute.append(fixture_id)
            return [statistici("Portugal", 5, 1), statistici("Wales", 4, 2)]

        with mock.patch.object(colector, "OUT", tmp), \
             mock.patch.object(colector.time, "sleep", lambda s: None):
            raport = colector.colecteaza(buget=2, meciuri=_meciuri(), fetch=fetch)
            verifica(raport["cereri"] == 2, f"cereri: {raport['cereri']}")
            verifica(raport["ramase"] == 1, f"ramase: {raport['ramase']}")

            cerute.clear()
            colector.colecteaza(buget=5, meciuri=_meciuri(), fetch=fetch)
            verifica(len(cerute) == 1,
                     f"a recerut meciuri deja adunate: {cerute}")


def test_meciul_fara_statistici_e_marcat() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        with mock.patch.object(colector, "OUT", tmp), \
             mock.patch.object(colector.time, "sleep", lambda s: None):
            colector.colecteaza(buget=1, meciuri=_meciuri(), fetch=lambda f: [])
            tot = colector.incarca()
            utile = colector.incarca(doar_utile=True)
        verifica(len(tot) == 1 and len(utile) == 0,
                 f"meci fara statistici: pastrat {len(tot)}, folosit {len(utile)}")


def _bazin(n: int = 600) -> pd.DataFrame:
    """Un bazin in care 'Ofensiva' produce constant mai multe cornere."""
    rng = np.random.default_rng(5)
    tari = {"Ofensiva": 7.0, "Medie": 5.0, "Defensiva": 3.0}
    echipe = list(tari)
    randuri = []
    zi = pd.Timestamp("2023-01-01")
    for i in range(n):
        gazda = echipe[i % 3]
        oaspete = echipe[(i + 1 + (i // 3) % 2) % 3]
        if gazda == oaspete:
            continue
        randuri.append({
            "fixture_id": i, "date": zi + pd.Timedelta(days=i * 2),
            "competition": "NL", "home": gazda, "away": oaspete,
            "hc": rng.poisson(tari[gazda]), "ac": rng.poisson(tari[oaspete]),
            "hy": rng.poisson(1.6), "ay": rng.poisson(1.9),
            "hr": 0, "ar": 0, "statistici": 2,
        })
    return pd.DataFrame(randuri)


def test_imbogateste_doar_nationalele() -> None:
    meciuri = [
        {"id": "N1", "league": "NAT_5", "home": "Ofensiva", "away": "Defensiva"},
        {"id": "C1", "league": "E0", "home": "Ofensiva", "away": "Defensiva"},
    ]
    with mock.patch.object(pcn, "incarca", lambda doar_utile=False: _bazin()):
        n = pcn.imbogateste(meciuri)

    verifica(n == 1, f"imbogatite {n}, asteptat 1")
    verifica("extra_markets" in meciuri[0], "meciul de nationala nu a primit piete")
    verifica("extra_markets" not in meciuri[1],
             "un meci de club a fost imbogatit din bazinul nationalelor")

    c = meciuri[0]["extra_markets"]["corners"]
    verifica(c["expected"]["home"] > c["expected"]["away"] + 2,
             f"diferenta dintre echipe nu se vede: {c['expected']}")
    verifica(c["winner"]["home"] > 0.6, f"favorita la cornere: {c['winner']}")


def test_echipa_cu_prea_putine_meciuri_nu_primeste_procente() -> None:
    bazin = _bazin()
    # O echipa aparuta o singura data: nu are de unde sa aiba forte.
    bazin = pd.concat([bazin, pd.DataFrame([{
        "fixture_id": 9999, "date": pd.Timestamp("2026-01-01"), "competition": "NL",
        "home": "Ofensiva", "away": "Exotica", "hc": 6, "ac": 2,
        "hy": 1, "ay": 1, "hr": 0, "ar": 0, "statistici": 2,
    }])], ignore_index=True)

    meciuri = [{"id": "N2", "league": "NAT_5", "home": "Ofensiva", "away": "Exotica"}]
    with mock.patch.object(pcn, "incarca", lambda doar_utile=False: bazin):
        pcn.imbogateste(meciuri)
    verifica("extra_markets" not in meciuri[0],
             "o echipa cu un singur meci a primit totusi procente")


def main() -> int:
    for test in (test_citeste_statisticile_pe_echipa,
                 test_valorile_lipsa_nu_devin_zero_fals,
                 test_aduna_respecta_bugetul_si_nu_repeta,
                 test_meciul_fara_statistici_e_marcat,
                 test_imbogateste_doar_nationalele,
                 test_echipa_cu_prea_putine_meciuri_nu_primeste_procente):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru cornerele nationalelor au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

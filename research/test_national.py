"""Teste pentru partea de echipe nationale.

Riscul aici nu e matematica -- e acelasi Dixon-Coles verificat in alta parte --
ci ce intra in el: un meci de club luat drept meci de nationala, o echipa
necunoscuta careia i se inventeaza forte, sau o cota citita gresit.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import national_model
import predict_national

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def istoric_sintetic(n: int = 400) -> pd.DataFrame:
    """Un bazin mic in care 'Puternica' e clar mai buna decat 'Slaba'."""
    rng = np.random.default_rng(7)
    randuri = []
    zi = pd.Timestamp("2024-01-01")
    for i in range(n):
        gazda, oaspete = ("Puternica", "Slaba") if i % 2 else ("Slaba", "Puternica")
        tari = {"Puternica": 2.2, "Slaba": 0.6}
        randuri.append({
            "date": zi + pd.Timedelta(days=i * 3),
            "home": gazda, "away": oaspete,
            "hg": int(rng.poisson(tari[gazda])),
            "ag": int(rng.poisson(tari[oaspete])),
        })
    return pd.DataFrame(randuri)


def test_modelul_invata_diferenta_de_valoare() -> None:
    hist = istoric_sintetic()
    azi = hist["date"].max() + pd.Timedelta(days=1)
    model = national_model.fit(hist, azi)
    verifica(model is not None, "modelul nu s-a antrenat pe un bazin valid")

    rezultat = national_model.probabilitati(model, "Puternica", "Slaba")
    verifica(rezultat["probs"]["p_home"] > 0.6,
             f"echipa clar mai buna nu e favorita: {rezultat['probs']['p_home']:.2f}")


def test_echipa_necunoscuta_nu_primeste_procente_inventate() -> None:
    hist = istoric_sintetic()
    model = national_model.fit(hist, hist["date"].max() + pd.Timedelta(days=1))
    verifica(national_model.probabilitati(model, "Puternica", "Vanuatu") is None,
             "o echipa fara istoric a primit totusi o predictie")


def test_increderea_urmeaza_numarul_de_meciuri() -> None:
    hist = istoric_sintetic()
    azi = hist["date"].max() + pd.Timedelta(days=1)
    n = national_model.meciuri_jucate(hist, "Puternica", azi)
    verifica(n > 100, f"numaratoarea de meciuri pare gresita: {n}")
    verifica(national_model.meciuri_jucate(hist, "Vanuatu", azi) == 0,
             "o echipa inexistenta are meciuri jucate")


def test_ia_doar_competitiile_de_nationale_si_doar_meciurile_neincepute() -> None:
    def fixture(liga_id, status="NS"):
        return {
            "league": {"id": liga_id},
            "fixture": {"id": 100 + liga_id, "date": "2026-09-24T18:45:00+00:00",
                        "status": {"short": status}},
            "teams": {"home": {"name": "Netherlands"}, "away": {"name": "Germany"}},
        }

    raspuns = [
        fixture(5),      # Liga Natiunilor: da
        fixture(39),     # Premier League: nu e meci de nationale
        fixture(5, "FT"),  # deja jucat
    ]
    # O singura zi, ca sa nu se dubleze raspunsul inlocuit.
    original = predict_national._api
    predict_national._api = lambda *a, **k: raspuns
    try:
        out = predict_national.fixturi_viitoare(None, None, zile=1)
    finally:
        predict_national._api = original

    verifica(len(out) == 1, f"au trecut {len(out)} meciuri in loc de unul")
    verifica(out and out[0]["liga_nume"] == "UEFA Nations League",
             "numele competitiei lipseste sau e gresit")


def test_cotele_medii_din_mai_multe_case() -> None:
    def pariu(nume, valori):
        return {"name": nume, "values": [{"value": v, "odd": o} for v, o in valori]}

    raspuns = [{
        "bookmakers": [
            {"name": "A", "bets": [
                pariu("Match Winner", [("Home", "1.50"), ("Draw", "4.00"),
                                       ("Away", "6.00")]),
                pariu("Goals Over/Under", [("Over 2.5", "1.80"),
                                           ("Under 2.5", "2.00"),
                                           ("Over 3.5", "3.20")]),
            ]},
            {"name": "B", "bets": [
                pariu("Match Winner", [("Home", "1.60"), ("Draw", "4.20"),
                                       ("Away", "5.80")]),
            ]},
        ]
    }]
    original = predict_national._api
    predict_national._api = lambda *a, **k: raspuns
    try:
        c = predict_national.cote(None, None, 1)
    finally:
        predict_national._api = original

    verifica(abs(c["home"] - 1.55) < 1e-9, f"media cotelor gazda: {c['home']}")
    verifica(c["over25"] == 1.80 and c["under25"] == 2.00,
             f"cotele de goluri: {c.get('over25')}, {c.get('under25')}")
    verifica("over35" not in c, "au intrat si linii pe care nu le folosim")


def test_fara_cote_nu_se_arunca() -> None:
    original = predict_national._api

    def cade(*a, **k):
        raise RuntimeError("fara retea")

    predict_national._api = cade
    try:
        verifica(predict_national.cote(None, None, 1) == {},
                 "o eroare la cote ar trebui sa dea un dictionar gol")
    finally:
        predict_national._api = original


def main() -> int:
    for test in (test_modelul_invata_diferenta_de_valoare,
                 test_echipa_necunoscuta_nu_primeste_procente_inventate,
                 test_increderea_urmeaza_numarul_de_meciuri,
                 test_ia_doar_competitiile_de_nationale_si_doar_meciurile_neincepute,
                 test_cotele_medii_din_mai_multe_case,
                 test_fara_cote_nu_se_arunca):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru nationale au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

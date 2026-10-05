"""Teste pentru cornere si cartonase.

Ce poate merge prost aici: sa dam procente unde nu avem date (Romania, cupe,
nationale), sa citim gresit distributia totalului, sau sa promitem mai mult
decat a aratat backtestul.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import counts_model
import predict_counts

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def istoric_sintetic(n: int = 600) -> pd.DataFrame:
    """Un campionat in care 'Ofensiva' produce mult mai multe cornere."""
    rng = np.random.default_rng(11)
    tari = {"Ofensiva": 7.0, "Medie": 5.0, "Defensiva": 3.0}
    echipe = list(tari)
    randuri = []
    zi = pd.Timestamp("2024-06-01")
    for i in range(n):
        gazda = echipe[i % 3]
        oaspete = echipe[(i + 1 + i // 3 % 2) % 3]
        if gazda == oaspete:
            continue
        randuri.append({
            "div": "E0", "date": zi + pd.Timedelta(days=i),
            "home": gazda, "away": oaspete,
            "hc": rng.poisson(tari[gazda]), "ac": rng.poisson(tari[oaspete]),
            "hy": rng.poisson(1.8), "ay": rng.poisson(2.1),
            "hr": 0, "ar": 0,
        })
    return pd.DataFrame(randuri)


def test_distributia_totalului_e_o_distributie() -> None:
    d = counts_model.distributii(5.2, 4.1)
    verifica(abs(float(d["total"].sum()) - 1.0) < 1e-9,
             f"totalul nu insumeaza 1: {d['total'].sum()}")
    verifica(abs(counts_model.peste(d["total"], 8.5)
                 + (1 - counts_model.peste(d["total"], 8.5)) - 1.0) < 1e-12,
             "peste si sub nu se completeaza")


def test_binomiala_negativa_are_coada_mai_groasa() -> None:
    medie = 10.0
    poisson = counts_model.distributii(5.0, 5.0)["total"]
    nb = counts_model.nb_pmf(medie, k=30.0)
    verifica(counts_model.peste(nb, 14.5) > counts_model.peste(poisson, 14.5),
             "binomiala negativa ar trebui sa dea mai multa masa la extreme")
    verifica(abs(float((np.arange(len(nb)) * nb).sum()) - medie) < 0.05,
             "media binomialei negative nu e cea ceruta")


def test_cine_da_mai_multe_insumeaza_unu() -> None:
    c = counts_model.cine_mai_multe(6.0, 3.0)
    verifica(abs(sum(c.values()) - 1.0) < 1e-9, f"suma: {sum(c.values())}")
    verifica(c["home"] > c["away"],
             "echipa cu rata mai mare ar trebui sa fie favorita la cornere")


def test_modelul_prinde_diferenta_dintre_echipe() -> None:
    hist = istoric_sintetic()
    meciuri = [{"id": "M1", "league": "E0", "home": "Ofensiva", "away": "Defensiva"},
               {"id": "M2", "league": "E0", "home": "Defensiva", "away": "Ofensiva"}]
    n = predict_counts.imbogateste(meciuri, hist)
    verifica(n == 2, f"imbogatite {n} din 2")

    c1 = meciuri[0]["extra_markets"]["corners"]["expected"]
    verifica(c1["home"] > c1["away"] + 2,
             f"diferenta dintre echipe nu se vede: {c1}")
    verifica(meciuri[0]["extra_markets"]["corners"]["winner"]["home"] > 0.6,
             "favorita la cornere nu e recunoscuta")


def test_nu_dam_procente_unde_nu_avem_date() -> None:
    hist = istoric_sintetic()
    meciuri = [
        {"id": "R1", "league": "ROU_Superliga", "home": "FCSB", "away": "Rapid"},
        {"id": "E1", "league": "EU_2", "home": "Ofensiva", "away": "Defensiva"},
        {"id": "N1", "league": "NAT_5", "home": "Ofensiva", "away": "Defensiva"},
    ]
    predict_counts.imbogateste(meciuri, hist)
    for m in meciuri:
        verifica("extra_markets" not in m,
                 f"{m['id']} a primit cornere desi sursa nu are datele")


def test_echipa_nevazuta_nu_primeste_predictie() -> None:
    hist = istoric_sintetic()
    meciuri = [{"id": "X", "league": "E0", "home": "Ofensiva", "away": "Necunoscuta"}]
    predict_counts.imbogateste(meciuri, hist)
    verifica("extra_markets" not in meciuri[0],
             "o echipa fara istoric a primit totusi procente")


def test_calitatea_declarata_e_cea_masurata() -> None:
    # Daca cineva schimba cifrele fara sa refaca backtestul, testul cade.
    verifica(predict_counts.CALITATE["corners_total"]["gain"] == 0.0,
             "totalul de cornere nu mai e marcat ca neinformativ")
    verifica(predict_counts.CALITATE["corners_winner"]["gain"] >
             predict_counts.CALITATE["cards_total"]["gain"],
             "ierarhia pietelor nu mai corespunde masuratorii")


def test_factorul_arbitrului() -> None:
    profil = {
        "strict": (600.0, 400.0, 100),   # da cu 50% mai mult decat se astepta
        "nou": (12.0, 8.0, 2),           # la fel, dar doar doua meciuri
    }
    f_strict, n = predict_counts.factor_arbitru(profil, "strict")
    f_nou, _ = predict_counts.factor_arbitru(profil, "nou")
    verifica(f_strict > 1.25 and n == 100, f"arbitrul strict: {f_strict}")
    # Doua meciuri nu fac un profil: factorul trebuie sa ramana aproape de 1.
    verifica(1.0 < f_nou < 1.05, f"arbitrul cu doua meciuri: {f_nou}")
    verifica(predict_counts.factor_arbitru(profil, None) == (1.0, 0),
             "fara arbitru cunoscut, factorul trebuie sa fie 1")
    verifica(predict_counts.factor_arbitru(profil, "necunoscut")[0] == 1.0,
             "arbitru fara istoric: factorul trebuie sa fie 1")


def test_arbitrul_muta_cartonasele_asteptate() -> None:
    hist = istoric_sintetic()
    meciuri = [{"id": "M1", "league": "E0", "home": "Ofensiva", "away": "Defensiva"}]
    predict_counts.imbogateste(meciuri, hist)
    fara = meciuri[0]["extra_markets"]["cards"]["expected"]["total"]

    import counts_model
    pregatit = predict_counts.pregateste(hist)
    fit, dispersii, _, baze = predict_counts._fit_liga(
        pregatit[pregatit["div"] == "E0"], ("cy", "ca"),
        pregatit["date"].max() + pd.Timedelta(days=1))
    cu = predict_counts._piete(fit, dispersii, baze, "cards",
                               "Ofensiva", "Defensiva", factor=1.3)
    verifica(cu["expected"]["total"] > fara * 1.2,
             f"factorul 1.3 nu a crescut asteptarea: {fara} -> {cu['expected']['total']}")


def main() -> int:
    for test in (test_distributia_totalului_e_o_distributie,
                 test_binomiala_negativa_are_coada_mai_groasa,
                 test_cine_da_mai_multe_insumeaza_unu,
                 test_modelul_prinde_diferenta_dintre_echipe,
                 test_nu_dam_procente_unde_nu_avem_date,
                 test_echipa_nevazuta_nu_primeste_predictie,
                 test_calitatea_declarata_e_cea_masurata,
                 test_factorul_arbitrului,
                 test_arbitrul_muta_cartonasele_asteptate):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru cornere si cartonase au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

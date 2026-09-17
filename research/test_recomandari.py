"""Teste pentru selectia automata de pariuri.

Regulile vin din masuratori (backtest_recomandari.py), deci trebuie sa ramana
exact cele masurate. O relaxare tacuta a unui prag ar transforma sectiunea
intr-una care recomanda lucruri pe care nu le-am verificat niciodata.
"""
from __future__ import annotations

import sys

from recomandari import MAXIM_RECOMANDARI, construieste

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def meci(id_="M1", probs=None, cote=None, confidence="ridicata") -> dict:
    return {
        "id": id_, "league_name": "Test", "date": "2026-09-20", "time": "18:00",
        "home": "Gazda", "away": "Oaspete", "confidence": confidence,
        "probs": probs or {}, "reference_odds": cote or {},
    }


def test_alege_cand_modelul_e_sigur_si_piata_de_acord() -> None:
    # 1 / X / 2 cu marja: 1.45 -> ~66% dupa scoaterea marjei.
    r = construieste([meci(
        probs={"p_home": 0.66, "p_draw": 0.20, "p_away": 0.14},
        cote={"home": 1.45, "draw": 4.30, "away": 6.50},
    )])
    verifica(len(r) == 1, f"asteptam o recomandare, am primit {len(r)}")
    if r:
        verifica(r[0]["market"] == "home", f"piata gresita: {r[0]['market']}")
        verifica(r[0]["historical_hit_rate"] > 0.6,
                 "rata istorica lipseste sau e implauzibila")


def test_respinge_probabilitate_mica() -> None:
    r = construieste([meci(
        probs={"p_home": 0.52, "p_draw": 0.25, "p_away": 0.23},
        cote={"home": 1.90, "draw": 3.60, "away": 4.00},
    )])
    verifica(not r, "a recomandat desi modelul nu e destul de sigur")


def test_respinge_dezacordul_mare() -> None:
    """Cazul in care modelul crede ca a gasit valoare: istoric, se inseala."""
    r = construieste([meci(
        probs={"p_home": 0.70, "p_draw": 0.18, "p_away": 0.12},
        cote={"home": 2.60, "draw": 3.40, "away": 2.90},  # piata da ~37%
    )])
    verifica(not r, "a recomandat un pariu unde modelul contrazice puternic piata")


def test_respinge_datele_slabe() -> None:
    r = construieste([meci(
        confidence="scazuta",
        probs={"p_home": 0.70, "p_draw": 0.18, "p_away": 0.12},
        cote={"home": 1.40, "draw": 4.50, "away": 7.00},
    )])
    verifica(not r, "a recomandat un meci cu date insuficiente")


def test_ignora_pietele_fara_cota() -> None:
    """Fara cota nu exista verificare; acolo modelul s-a dovedit prea increzator."""
    r = construieste([meci(
        probs={"p_home": 0.40, "p_draw": 0.25, "p_away": 0.35, "p_btts": 0.85},
        cote={"home": 2.50, "draw": 3.40, "away": 2.90},
    )])
    verifica(not r, "a recomandat o piata pentru care nu avem cota")


def test_un_singur_pariu_per_meci() -> None:
    r = construieste([meci(
        probs={"p_home": 0.66, "p_draw": 0.20, "p_away": 0.14,
               "p_over25": 0.64, "p_under25": 0.36},
        cote={"home": 1.45, "draw": 4.30, "away": 6.50,
              "over25": 1.50, "under25": 2.65},
    )])
    verifica(len(r) == 1, f"un meci a produs {len(r)} recomandari")


def test_ordonare_si_limita() -> None:
    meciuri = []
    for i, p in enumerate([0.62, 0.81, 0.71, 0.66, 0.75, 0.68, 0.63, 0.79]):
        cota = round(1 / (p / 0.97), 2)  # cota aproape corecta: piata e de acord
        rest = (1 - p) / 2
        meciuri.append(meci(
            id_=f"M{i}",
            probs={"p_home": p, "p_draw": rest, "p_away": rest},
            cote={"home": cota, "draw": round(1 / (rest / 0.97), 2),
                  "away": round(1 / (rest / 0.97), 2)},
        ))
    r = construieste(meciuri)
    verifica(len(r) == MAXIM_RECOMANDARI,
             f"asteptam {MAXIM_RECOMANDARI} recomandari, am primit {len(r)}")
    probabilitati = [x["probability"] for x in r]
    verifica(probabilitati == sorted(probabilitati, reverse=True),
             "recomandarile nu sunt ordonate descrescator")
    if r:
        verifica(abs(r[0]["probability"] - 0.81) < 1e-6,
                 f"prima recomandare ar trebui sa fie cea mai sigura, e {r[0]['probability']}")


def main() -> int:
    for test in (test_alege_cand_modelul_e_sigur_si_piata_de_acord,
                 test_respinge_probabilitate_mica,
                 test_respinge_dezacordul_mare,
                 test_respinge_datele_slabe,
                 test_ignora_pietele_fara_cota,
                 test_un_singur_pariu_per_meci,
                 test_ordonare_si_limita):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru recomandari au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

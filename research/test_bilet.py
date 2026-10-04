"""Teste pentru biletul zilei.

Trei lucruri pot strica un bilet: doua picioare din acelasi meci (atunci
inmultirea sanselor minte), un bilet care se rescrie peste zi, si un verdict
dat inainte sa se fi jucat toate meciurile.
"""
from __future__ import annotations

import sys
from datetime import datetime

import bilet

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def pick(familie, market, p, cota=None, rata=0.65):
    return {"family": familie, "market": market,
            "market_label": f"{familie} {market}", "probability": p,
            "odds": cota, "fair_odds": round(1 / p, 2),
            "historical_hit_rate": rata}


def meci(mid, picks, ora="18:00"):
    return {"match_id": mid, "league_name": "Test", "date": "2026-10-10",
            "time": ora, "home": f"Gazda{mid}", "away": f"Oaspete{mid}",
            "picks": picks}


def test_cate_un_picior_din_fiecare_meci() -> None:
    b = bilet.construieste([
        meci("A", [pick("1x2", "home", 0.62, 1.60),
                   pick("goluri", "over25", 0.61, 1.50)]),
        meci("B", [pick("cornere", "corners_home_over_3.5", 0.66)]),
    ])
    meciuri = [p["match_id"] for p in b["legs"]]
    verifica(len(meciuri) == len(set(meciuri)),
             f"doua picioare din acelasi meci: {meciuri}")


def test_amesteca_tipurile_de_piata() -> None:
    b = bilet.construieste([
        meci("A", [pick("1x2", "home", 0.62, 1.60)]),
        meci("B", [pick("goluri", "over25", 0.61, 1.50)]),
        meci("C", [pick("cornere", "corners_home_over_3.5", 0.66)]),
        meci("D", [pick("cartonașe", "cards_total_over_3.5", 0.63)]),
        meci("E", [pick("cornere", "corners_away_over_3.5", 0.69)]),
    ])
    familii = sorted({p["family"] for p in b["legs"]})
    verifica(familii == sorted(bilet.ORDINE_FAMILII),
             f"biletul nu acopera toate tipurile disponibile: {familii}")
    verifica(len(b["legs"]) == bilet.MAXIM_PICIOARE,
             f"asteptam {bilet.MAXIM_PICIOARE} picioare, am {len(b['legs'])}")


def test_sansele_si_cotele_se_inmultesc() -> None:
    b = bilet.construieste([
        meci("A", [pick("1x2", "home", 0.60, 1.60)]),
        meci("B", [pick("goluri", "over25", 0.50, 2.00)]),
    ])
    verifica(abs(b["combined_probability"] - 0.30) < 1e-9,
             f"sansa combinata: {b['combined_probability']}")
    verifica(abs(b["combined_odds"] - 3.20) < 1e-9,
             f"cota combinata: {b['combined_odds']}")
    verifica(b["odds_estimated"] is False, "cotele erau toate reale")


def test_cota_e_marcata_estimata_cand_lipsesc_cote() -> None:
    b = bilet.construieste([
        meci("A", [pick("1x2", "home", 0.60, 1.60)]),
        meci("B", [pick("cornere", "corners_home_over_3.5", 0.65)]),
    ])
    verifica(b["odds_estimated"] is True,
             "un picior pe cornere n-are cota, deci totalul e estimat")


def test_prea_putine_selectii_inseamna_fara_bilet() -> None:
    b = bilet.construieste([meci("A", [pick("1x2", "home", 0.62, 1.60)])])
    verifica(b is None, "un bilet dintr-un singur picior nu e bilet")


def test_biletul_zilei_nu_se_rescrie() -> None:
    primul = bilet.construieste([
        meci("A", [pick("1x2", "home", 0.62, 1.60)]),
        meci("B", [pick("goluri", "over25", 0.61, 1.50)]),
    ])
    bilete, azi = bilet.biletul_zilei([], primul)
    altul = bilet.construieste([
        meci("C", [pick("1x2", "home", 0.65, 1.55)]),
        meci("D", [pick("goluri", "under25", 0.63, 1.58)]),
    ])
    bilete, din_nou = bilet.biletul_zilei(bilete, altul)
    verifica(len(bilete) == 1, f"s-au adunat {len(bilete)} bilete pe aceeasi zi")
    verifica(din_nou["legs"][0]["match_id"] == azi["legs"][0]["match_id"],
             "biletul zilei s-a schimbat la a doua rulare")


def _selectie(cheie, castigat):
    return {"cheie": cheie, "castigat": castigat}


def test_verdictul_biletului() -> None:
    def bilet_nou():
        b = bilet.construieste([
            meci("A", [pick("1x2", "home", 0.62, 1.60)]),
            meci("B", [pick("goluri", "over25", 0.61, 1.50)]),
        ])
        return [dict(b, castigat=None)]

    # Un picior jucat si castigat, celalalt nejucat: inca nu stim.
    b = bilet.rezolva(bilet_nou(), [_selectie("A|home", True),
                                    _selectie("B|over25", None)])
    verifica(b[0]["castigat"] is None, "bilet declarat inainte de ultimul meci")

    # Un picior pierdut pierde biletul, chiar daca celalalt nu s-a jucat.
    b = bilet.rezolva(bilet_nou(), [_selectie("A|home", False),
                                    _selectie("B|over25", None)])
    verifica(b[0]["castigat"] is False, "un picior pierdut nu a pierdut biletul")

    b = bilet.rezolva(bilet_nou(), [_selectie("A|home", True),
                                    _selectie("B|over25", True)])
    verifica(b[0]["castigat"] is True, "toate picioarele au iesit, dar biletul nu")


def test_rezumatul() -> None:
    b1 = {"date": "2026-10-01", "legs": [], "castigat": True, "expected_hit_rate": 0.2}
    b2 = {"date": "2026-10-02", "legs": [], "castigat": False, "expected_hit_rate": 0.2}
    b3 = {"date": "2026-10-03", "legs": [], "castigat": None, "expected_hit_rate": 0.2}
    r = bilet.rezumat([b1, b2, b3])
    verifica(r["total"] == 3 and r["resolved"] == 2 and r["won"] == 1,
             f"rezumat gresit: {r}")


def main() -> int:
    for test in (test_cate_un_picior_din_fiecare_meci,
                 test_amesteca_tipurile_de_piata,
                 test_sansele_si_cotele_se_inmultesc,
                 test_cota_e_marcata_estimata_cand_lipsesc_cote,
                 test_prea_putine_selectii_inseamna_fara_bilet,
                 test_biletul_zilei_nu_se_rescrie,
                 test_verdictul_biletului,
                 test_rezumatul):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru biletul zilei au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

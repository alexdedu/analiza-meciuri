"""Teste pentru biletul zilei.

Ce poate strica un bilet: picioare din meciuri prea indepartate (casele n-au
inca pietele), o cota sub pragul cerut, doua picioare din acelasi meci (atunci
inmultirea sanselor minte), un bilet care se rescrie peste zi, si un verdict
dat inainte sa se fi jucat toate meciurile.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

import bilet

esecuri: list[str] = []
AZI = date(2026, 10, 5)


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def sel(mid, market, p, cota=None, zile=0, rata=0.65):
    """O selectie plata, la `zile` distanta de azi."""
    return {"match_id": mid, "league_name": "Test",
            "date": (AZI + timedelta(days=zile)).isoformat(), "time": "18:00",
            "home": f"Gazda{mid}", "away": f"Oaspete{mid}", "market": market,
            "market_label": f"{market} {mid}", "probability": p, "odds": cota,
            "fair_odds": round(1 / p, 2), "historical_hit_rate": rata}


def destule(zile=0):
    """Selectii cu cote de ~1.6, din meciuri diferite: ajung la 10 din cinci."""
    return [sel(f"M{i}", "home", 0.62, 1.60, zile=zile) for i in range(7)]


def test_ajunge_la_cota_minima() -> None:
    b = bilet.construieste(destule(), azi=AZI)
    verifica(b is not None, "nu s-a facut bilet desi erau destule selectii")
    if b:
        verifica(b["combined_odds"] >= bilet.COTA_MINIMA,
                 f"cota totala {b['combined_odds']} sub {bilet.COTA_MINIMA}")
        # 1.6^5 = 10.49: cinci picioare ajung, al saselea ar fi in plus.
        verifica(len(b["legs"]) == 5,
                 f"asteptam cinci picioare, am {len(b['legs'])}")


def test_doar_meciuri_din_urmatoarele_trei_zile() -> None:
    aproape = [sel("A", "home", 0.62, 1.60, zile=0),
               sel("B", "home", 0.62, 1.60, zile=1),
               sel("C", "home", 0.62, 1.60, zile=2)]
    departe = [sel(f"D{i}", "home", 0.62, 1.60, zile=4) for i in range(6)]
    b = bilet.construieste(aproape + departe, azi=AZI)
    # Cu doar trei meciuri apropiate, cota 10 nu se poate atinge.
    verifica(b is None,
             "biletul a folosit meciuri de peste trei zile ca sa ajunga la 10")


def test_fara_doua_picioare_din_acelasi_meci() -> None:
    selectii = []
    for i in range(6):
        selectii.append(sel(f"M{i}", "home", 0.62, 1.60))
        selectii.append(sel(f"M{i}", "over25", 0.61, 1.55))
    b = bilet.construieste(selectii, azi=AZI)
    meciuri = [p["match_id"] for p in b["legs"]]
    verifica(len(meciuri) == len(set(meciuri)),
             f"doua picioare din acelasi meci: {meciuri}")


def test_cota_prudenta_la_cornere() -> None:
    """Fara cota reala, se foloseste cea corecta scazuta cu marja casei."""
    s = sel("A", "corners_home_over_3.5", 0.60)   # corecta 1.67
    b_eligibil = bilet._cota_efectiva(s)
    verifica(abs(b_eligibil - 1.67 * (1 - bilet.MARJA_CASA)) < 1e-9,
             f"cota prudenta gresita: {b_eligibil}")


def test_cota_e_marcata_estimata_cand_intra_cornere() -> None:
    selectii = destule()[:4] + [sel("C1", "corners_home_over_3.5", 0.60),
                                sel("C2", "cards_total_over_3.5", 0.60)]
    b = bilet.construieste(selectii, azi=AZI)
    if b and any(p["odds"] is None for p in b["legs"]):
        verifica(b["odds_estimated"] is True,
                 "biletul are picioare fara cota reala, dar nu scrie estimata")


def test_cel_mult_trei_din_acelasi_tip() -> None:
    selectii = [sel(f"G{i}", "over25", 0.62, 1.60) for i in range(5)]
    selectii += [sel(f"R{i}", "home", 0.62, 1.58) for i in range(5)]
    b = bilet.construieste(selectii, azi=AZI)
    goluri = sum(1 for p in b["legs"] if p["family"] == "goluri")
    verifica(goluri <= bilet.MAXIM_PE_FAMILIE,
             f"{goluri} picioare pe goluri, peste limita")


def test_biletul_zilei_nu_se_rescrie() -> None:
    primul = bilet.construieste(destule(), azi=AZI)
    primul["date"] = __import__("datetime").datetime.now().date().isoformat()
    bilete, azi = bilet.biletul_zilei([], primul)
    altul = dict(primul, legs=list(reversed(primul["legs"])))
    bilete, din_nou = bilet.biletul_zilei(bilete, altul)
    verifica(len(bilete) == 1, f"s-au adunat {len(bilete)} bilete pe aceeasi zi")
    verifica(din_nou["legs"] == azi["legs"], "biletul zilei s-a schimbat")


def test_regulile_noi_inlocuiesc_biletul_de_azi() -> None:
    azi = __import__("datetime").datetime.now().date().isoformat()
    vechi = {"date": azi, "rules": "reguli-vechi", "legs": [],
             "expected_hit_rate": 0.2, "castigat": None}
    nou = dict(bilet.construieste(destule(), azi=AZI), date=azi)
    bilete, actual = bilet.biletul_zilei([vechi], nou)
    verifica(actual["rules"] == bilet.REGULI, "biletul dupa reguli vechi a ramas")
    verifica(vechi.get("inlocuit") is True, "biletul vechi nu e marcat inlocuit")
    # A doua rulare nu trebuie sa mai adauge inca un bilet.
    bilete, _ = bilet.biletul_zilei(bilete, nou)
    verifica(len(bilete) == 2, f"rularile repetate au adaugat bilete: {len(bilete)}")
    verifica(bilet.rezumat(bilete)["total"] == 1,
             "biletul inlocuit a intrat in bilant")


def test_explica_de_ce_nu_iese_bilet() -> None:
    selectii = [sel("A", "home", 0.62, 1.52, zile=0),
                sel("B", "over25", 0.61, 1.51, zile=1),
                sel("C", "home", 0.62, 1.60, zile=5)]
    d = bilet.de_ce_lipseste(selectii, azi=AZI)
    verifica(abs(d["max_odds"] - round(1.52 * 1.51, 2)) < 1e-9,
             f"cota maxima atinsa gresita: {d['max_odds']}")
    verifica(d["legs_available"] == 2, f"picioare disponibile: {d['legs_available']}")
    # Meciul de peste cinci zile intra in fereastra cu doua zile inainte.
    verifica(d["next_possible"] == (AZI + timedelta(days=3)).isoformat(),
             f"ziua de la care se poate: {d['next_possible']}")


def _selectie(cheie, castigat):
    return {"cheie": cheie, "castigat": castigat}


def test_verdictul_biletului() -> None:
    def bilet_nou():
        b = bilet.construieste(destule(), azi=AZI)
        return [dict(b, castigat=None)]

    chei = [f"{p['match_id']}|{p['market']}" for p in bilet_nou()[0]["legs"]]

    b = bilet.rezolva(bilet_nou(), [_selectie(chei[0], True)]
                      + [_selectie(c, None) for c in chei[1:]])
    verifica(b[0]["castigat"] is None, "bilet declarat inainte de ultimul meci")

    b = bilet.rezolva(bilet_nou(), [_selectie(chei[0], False)]
                      + [_selectie(c, None) for c in chei[1:]])
    verifica(b[0]["castigat"] is False, "un picior pierdut nu a pierdut biletul")

    b = bilet.rezolva(bilet_nou(), [_selectie(c, True) for c in chei])
    verifica(b[0]["castigat"] is True, "toate picioarele au iesit, dar biletul nu")


def main() -> int:
    for test in (test_ajunge_la_cota_minima,
                 test_doar_meciuri_din_urmatoarele_trei_zile,
                 test_fara_doua_picioare_din_acelasi_meci,
                 test_cota_prudenta_la_cornere,
                 test_cota_e_marcata_estimata_cand_intra_cornere,
                 test_cel_mult_trei_din_acelasi_tip,
                 test_biletul_zilei_nu_se_rescrie,
                 test_regulile_noi_inlocuiesc_biletul_de_azi,
                 test_explica_de_ce_nu_iese_bilet,
                 test_verdictul_biletului):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru biletul zilei au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Teste pentru fisa de rezultate.

Partea delicata nu e notarea selectiilor, ci verificarea lor: un verdict gresit
ar face bilantul sa arate mai bine (sau mai rau) decat realitatea, adica exact
opusul scopului acestei functii.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

import pandas as pd

import scorecard

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def recomandare(match_id="M1", market="home", eticheta="Victorie Gazda",
                p=0.72, cota=1.40, banda="70-80%", data=None) -> dict:
    return {
        "match_id": match_id, "market": market, "market_label": eticheta,
        "league_name": "Test", "date": data or "2026-09-01",
        "home": "Gazda", "away": "Oaspete",
        "probability": p, "odds": cota, "band": banda,
    }


def istoric(randuri) -> pd.DataFrame:
    return pd.DataFrame([
        {"date": pd.Timestamp(d), "home": h, "away": a, "hg": hg, "ag": ag}
        for d, h, a, hg, ag in randuri
    ])


def test_nu_dubleaza_aceeasi_selectie() -> None:
    sel = scorecard.adauga([], [recomandare()])
    sel = scorecard.adauga(sel, [recomandare()])
    verifica(len(sel) == 1, f"aceeasi selectie a fost notata de {len(sel)} ori")


def test_acelasi_meci_piete_diferite_sunt_separate() -> None:
    sel = scorecard.adauga([], [recomandare(market="home"),
                                recomandare(market="over25", eticheta="Peste 2.5")])
    verifica(len(sel) == 2, "doua piete ale aceluiasi meci au fost contopite")


def test_verdictul_pe_fiecare_piata() -> None:
    cazuri = [
        ("home", 2, 1, True), ("home", 1, 1, False), ("home", 0, 2, False),
        ("draw", 1, 1, True), ("draw", 2, 1, False),
        ("away", 0, 2, True), ("away", 2, 0, False),
        ("over25", 2, 1, True), ("over25", 1, 1, False),
        ("under25", 1, 1, True), ("under25", 2, 1, False),
    ]
    for market, hg, ag, asteptat in cazuri:
        obtinut = scorecard._verdict(market, hg, ag)
        verifica(obtinut == asteptat,
                 f"{market} la {hg}-{ag}: asteptat {asteptat}, obtinut {obtinut}")


def test_rezolva_doar_meciurile_jucate() -> None:
    ieri = (datetime.now() - timedelta(days=1)).date().isoformat()
    maine = (datetime.now() + timedelta(days=1)).date().isoformat()
    sel = scorecard.adauga([], [
        recomandare(match_id="VECHI", data=ieri),
        recomandare(match_id="VIITOR", data=maine),
    ])
    h = istoric([(ieri, "Gazda", "Oaspete", 3, 0), (maine, "Gazda", "Oaspete", 0, 3)])
    sel, noi = scorecard.rezolva(sel, h)

    vechi = next(s for s in sel if s["match_id"] == "VECHI")
    viitor = next(s for s in sel if s["match_id"] == "VIITOR")
    verifica(vechi["castigat"] is True, "meciul jucat nu a fost verificat corect")
    verifica(vechi["scor"] == "3-0", f"scor gresit: {vechi['scor']}")
    verifica(viitor["castigat"] is None,
             "un meci care nu s-a jucat inca a primit verdict")
    verifica(noi == 1, f"asteptam o rezolvare, au fost {noi}")


def test_nu_rescrie_un_verdict_deja_dat() -> None:
    ieri = (datetime.now() - timedelta(days=1)).date().isoformat()
    sel = scorecard.adauga([], [recomandare(data=ieri)])
    sel, _ = scorecard.rezolva(sel, istoric([(ieri, "Gazda", "Oaspete", 2, 0)]))
    # A doua trecere, cu un scor diferit: verdictul initial trebuie sa ramana.
    sel, noi = scorecard.rezolva(sel, istoric([(ieri, "Gazda", "Oaspete", 0, 5)]))
    verifica(sel[0]["castigat"] is True, "verdictul a fost rescris")
    verifica(noi == 0, "a raportat o rezolvare noua pentru ceva deja rezolvat")


def test_bilantul_si_profitul() -> None:
    ieri = (datetime.now() - timedelta(days=1)).date().isoformat()
    sel = scorecard.adauga([], [
        recomandare(match_id="A", data=ieri, cota=1.50),
        recomandare(match_id="B", data=ieri, cota=2.00),
    ])
    # A castiga, B pierde.
    sel[0]["castigat"], sel[0]["scor"] = True, "2-0"
    sel[1]["castigat"], sel[1]["scor"] = False, "0-1"
    r = scorecard.rezumat(sel)

    verifica(r["resolved"] == 2, f"rezolvate: {r['resolved']}")
    verifica(r["hits"] == 1, f"reusite: {r['hits']}")
    verifica(abs(r["hit_rate"] - 0.5) < 1e-9, f"rata: {r['hit_rate']}")
    # (1.50 - 1) pentru castig, -1 pentru pierdere = -0.50
    verifica(abs(r["profit_units"] + 0.50) < 1e-9, f"profit: {r['profit_units']}")


def test_bilant_gol_nu_arunca() -> None:
    r = scorecard.rezumat([])
    verifica(r["resolved"] == 0 and r["hit_rate"] is None,
             "bilantul gol ar trebui sa fie None, nu zero fals")


def test_banda_compara_cu_asteptarea_din_backtest() -> None:
    ieri = (datetime.now() - timedelta(days=1)).date().isoformat()
    sel = scorecard.adauga([], [recomandare(match_id=f"M{i}", data=ieri)
                                for i in range(4)])
    for i, s in enumerate(sel):
        s["castigat"] = i < 3  # 3 din 4
        s["scor"] = "1-0"
    r = scorecard.rezumat(sel)
    banda = r["by_band"][0]
    verifica(banda["band"] == "70-80%", f"banda gresita: {banda['band']}")
    verifica(abs(banda["rate"] - 0.75) < 1e-9, f"rata benzii: {banda['rate']}")
    verifica(banda["expected"] == 0.753, "asteptarea din backtest lipseste")


def main() -> int:
    for test in (test_nu_dubleaza_aceeasi_selectie,
                 test_acelasi_meci_piete_diferite_sunt_separate,
                 test_verdictul_pe_fiecare_piata,
                 test_rezolva_doar_meciurile_jucate,
                 test_nu_rescrie_un_verdict_deja_dat,
                 test_bilantul_si_profitul,
                 test_bilant_gol_nu_arunca,
                 test_banda_compara_cu_asteptarea_din_backtest):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru fisa de rezultate au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

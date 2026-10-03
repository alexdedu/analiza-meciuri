"""Teste pentru selectia automata de pariuri.

Regulile vin din masuratori (backtest_recomandari.py), deci trebuie sa ramana
exact cele masurate. O relaxare tacuta a unui prag ar transforma sectiunea
intr-una care recomanda lucruri pe care nu le-am verificat niciodata.
"""
from __future__ import annotations

import sys

from recomandari import COTA_MINIMA, MAXIM_RECOMANDARI, construieste

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


def test_respinge_cota_prea_mica() -> None:
    """Cazul care a pornit schimbarea: 90% sigur, dar cota 1,08."""
    r = construieste([meci(
        probs={"p_home": 0.90, "p_draw": 0.07, "p_away": 0.03},
        cote={"home": 1.08, "draw": 9.00, "away": 20.0},
    )])
    verifica(not r, f"a recomandat la cota sub {COTA_MINIMA}")


def test_accepta_cand_modelul_e_mai_prudent_decat_piata() -> None:
    """Acolo ratele masurate sunt cele mai bune, deci partea asta ramane larga."""
    # Piata da ~69% dupa scoaterea marjei, modelul spune 62%: dezacord -7pp.
    r = construieste([meci(
        probs={"p_home": 0.62, "p_draw": 0.22, "p_away": 0.16},
        cote={"home": 1.40, "draw": 4.50, "away": 7.00},
    )])
    verifica(not r, "cota 1,40 trebuia oricum respinsa")

    r = construieste([meci(
        probs={"p_home": 0.62, "p_draw": 0.22, "p_away": 0.16},
        cote={"home": 1.50, "draw": 4.20, "away": 6.00},
    )])
    verifica(len(r) == 1, "a respins o selectie in care modelul e sub piata")


def test_respinge_cand_modelul_se_crede_peste_piata() -> None:
    """Cu cat modelul depaseste piata, cu atat greseste mai des: 53,5% peste 5pp."""
    # Piata da ~59%, modelul spune 66%: dezacord +7pp, peste pragul de +2pp.
    r = construieste([meci(
        probs={"p_home": 0.66, "p_draw": 0.20, "p_away": 0.14},
        cote={"home": 1.65, "draw": 3.80, "away": 5.50},
    )])
    verifica(not r, "a recomandat desi modelul se crede peste piata cu 7 puncte")


def test_rata_promisa_urmeaza_nivelul_de_dezacord() -> None:
    """Fiecare selectie poarta rata masurata a nivelului ei, nu o medie comuna."""
    # Model 62%, piata ~66% dupa marja: modelul e sub piata.
    sub = construieste([meci(
        probs={"p_home": 0.62, "p_draw": 0.22, "p_away": 0.16},
        cote={"home": 1.46, "draw": 4.40, "away": 6.20},
    )])
    # Model 66%, piata ~62%: modelul e peste piata cu vreo 4 puncte.
    peste = construieste([meci(
        probs={"p_home": 0.66, "p_draw": 0.20, "p_away": 0.14},
        cote={"home": 1.50, "draw": 4.20, "away": 6.00},
    )])

    verifica(len(sub) == 1 and len(peste) == 1,
             f"asteptam cate o selectie, am primit {len(sub)} si {len(peste)}")
    if sub and peste:
        verifica(sub[0]["band"] == "sub piață", f"nivel gresit: {sub[0]['band']}")
        verifica(peste[0]["band"] == "peste piață", f"nivel gresit: {peste[0]['band']}")
        verifica(sub[0]["historical_hit_rate"] > peste[0]["historical_hit_rate"],
                 "nivelul mai prudent ar trebui sa promita mai mult")


def test_ordonare_si_limita() -> None:
    """Ordinea urmeaza cat platesc selectiile, nu cat de sigure par."""
    meciuri = []
    for i, (p, cota) in enumerate([(0.61, 1.60), (0.64, 1.48), (0.62, 1.85),
                                   (0.63, 1.50), (0.66, 1.46), (0.61, 1.52),
                                   (0.62, 1.70), (0.65, 1.47)]):
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
    castiguri = [x["historical_hit_rate"] * x["odds"] for x in r]
    verifica(castiguri == sorted(castiguri, reverse=True),
             "recomandarile nu sunt ordonate dupa cat platesc")
    if r:
        verifica(r[0]["odds"] >= 1.70,
                 f"prima recomandare ar trebui sa fie cea mai bine platita, "
                 f"are cota {r[0]['odds']}")
    verifica(all(x["odds"] >= COTA_MINIMA for x in r),
             "a trecut o selectie sub cota minima")


def test_gruparea_aduna_pietele_aceluiasi_meci() -> None:
    from recomandari import grupeaza_pe_meci

    cu_cota = [
        {"match_id": "M1", "league_name": "Test", "date": "2026-10-10",
         "time": "17:00", "home": "Gazda", "away": "Oaspete", "market": "home",
         "market_label": "Victorie Gazda", "probability": 0.62, "odds": 1.60,
         "band": "sub piață", "historical_hit_rate": 0.653},
        {"match_id": "M1", "league_name": "Test", "date": "2026-10-10",
         "time": "17:00", "home": "Gazda", "away": "Oaspete", "market": "over25",
         "market_label": "Peste 2.5 goluri", "probability": 0.61, "odds": 1.50,
         "band": "sub piață", "historical_hit_rate": 0.653},
    ]
    contori = [
        {"match_id": "M1", "league_name": "Test", "date": "2026-10-10",
         "time": "17:00", "home": "Gazda", "away": "Oaspete",
         "market": "corners_home_over_4.5",
         "market_label": "Gazda peste 4.5 cornere", "probability": 0.66,
         "fair_odds": 1.52, "historical_hit_rate": 0.642},
    ]

    meciuri = grupeaza_pe_meci(cu_cota, contori)
    verifica(len(meciuri) == 1, f"asteptam un meci, am primit {len(meciuri)}")
    familii = [p["family"] for p in meciuri[0]["picks"]]
    verifica(familii == ["1x2", "goluri", "cornere"],
             f"familiile sau ordinea lor sunt gresite: {familii}")


def test_meciurile_cu_cota_adevarata_sunt_primele() -> None:
    """Cota corecta e calculata din propriul procent; nu intra la intrecere."""
    from recomandari import grupeaza_pe_meci

    doar_cornere = {"match_id": "M2", "league_name": "Test", "date": "2026-10-10",
                    "time": "17:00", "home": "A", "away": "B",
                    "market": "corners_home_over_3.5",
                    "market_label": "A peste 3.5 cornere", "probability": 0.70,
                    "fair_odds": 1.43, "historical_hit_rate": 0.665}
    cu_cota = {"match_id": "M3", "league_name": "Test", "date": "2026-10-10",
               "time": "17:00", "home": "C", "away": "D", "market": "home",
               "market_label": "Victorie C", "probability": 0.60, "odds": 1.55,
               "band": "sub piață", "historical_hit_rate": 0.653}

    meciuri = grupeaza_pe_meci([cu_cota], [doar_cornere])
    verifica(meciuri[0]["match_id"] == "M3",
             f"primul meci ar trebui sa fie cel cu cota: {meciuri[0]['match_id']}")


def main() -> int:
    for test in (test_alege_cand_modelul_e_sigur_si_piata_de_acord,
                 test_respinge_probabilitate_mica,
                 test_respinge_dezacordul_mare,
                 test_respinge_datele_slabe,
                 test_ignora_pietele_fara_cota,
                 test_un_singur_pariu_per_meci,
                 test_respinge_cota_prea_mica,
                 test_accepta_cand_modelul_e_mai_prudent_decat_piata,
                 test_respinge_cand_modelul_se_crede_peste_piata,
                 test_rata_promisa_urmeaza_nivelul_de_dezacord,
                 test_ordonare_si_limita,
                 test_gruparea_aduna_pietele_aceluiasi_meci,
                 test_meciurile_cu_cota_adevarata_sunt_primele):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru recomandari au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

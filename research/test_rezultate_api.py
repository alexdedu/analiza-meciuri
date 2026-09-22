"""Teste pentru scorurile luate de la API-Football.

Aici se decide daca o selectie e trecuta castigata sau pierduta, deci o
potrivire gresita de nume ar falsifica exact cifrele pe care fisa de rezultate
exista ca sa le arate. Testele nu ating reteaua: `fetch` e inlocuit.
"""
from __future__ import annotations

import sys

import rezultate_api

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def fixture(gazda: str, oaspete: str, hg: int, ag: int, status: str = "FT") -> dict:
    return {
        "fixture": {"id": 1, "status": {"short": status}},
        "teams": {"home": {"name": gazda}, "away": {"name": oaspete}},
        "score": {"fulltime": {"home": hg, "away": ag}},
    }


def selectie(match_id="P1_20260919_SpLisbon_Arouca", home="Sp Lisbon",
             away="Arouca", data="2026-09-19") -> dict:
    return {"match_id": match_id, "date": data, "home": home, "away": away}


def test_divizia_din_identificator() -> None:
    verifica(rezultate_api.divizia("P1_20260919_SpLisbon_Arouca") == "P1",
             "divizia simpla nu a fost recunoscuta")
    # "ROU_Superliga_..." incepe si cu prefixe mai scurte; castiga cel mai lung.
    verifica(rezultate_api.divizia("ROU_Superliga_20260919_A_B") == "ROU_Superliga",
             "Superliga nu a fost recunoscuta")
    verifica(rezultate_api.divizia("EU123456") is None,
             "un meci din afara campionatelor acoperite ar trebui sarit")


def test_sezonul_urmeaza_startul_campionatului() -> None:
    verifica(rezultate_api.sezonul("2026-09-19") == 2026, "toamna: sezon gresit")
    verifica(rezultate_api.sezonul("2027-02-10") == 2026, "primavara: sezon gresit")


def test_gaseste_scorul_desi_numele_difera() -> None:
    def fetch(league_id, data):
        verifica(league_id == 94, f"campionat gresit: {league_id}")
        return [fixture("Sporting CP", "Arouca", 3, 1),
                fixture("FC Porto", "Benfica", 0, 0)]

    scor = rezultate_api.rezolvator(fetch=fetch)(selectie())
    verifica(scor == (3, 1), f"scor gresit sau negasit: {scor}")


def test_meciul_neinceput_nu_are_scor() -> None:
    def fetch(league_id, data):
        return [fixture("Sporting CP", "Arouca", None, None, status="NS")]

    verifica(rezultate_api.rezolvator(fetch=fetch)(selectie()) is None,
             "un meci neinceput a primit scor")


def test_prelungirile_nu_schimba_scorul_din_timpul_regulamentar() -> None:
    def fetch(league_id, data):
        # 1-1 dupa 90 de minute, 2-1 dupa prelungiri: pariul e pe primul.
        return [fixture("Sporting CP", "Arouca", 1, 1, status="AET")]

    scor = rezultate_api.rezolvator(fetch=fetch)(selectie())
    verifica(scor == (1, 1), f"a luat scorul de dupa prelungiri: {scor}")


def test_nu_confunda_alt_meci_din_aceeasi_zi() -> None:
    def fetch(league_id, data):
        return [fixture("FC Porto", "Benfica", 2, 0)]

    verifica(rezultate_api.rezolvator(fetch=fetch)(selectie()) is None,
             "a luat scorul altui meci")


def test_inversarea_terenului_nu_trece() -> None:
    def fetch(league_id, data):
        # Acelasi cuplu de echipe, dar returul: scorul nu e al selectiei noastre.
        return [fixture("Arouca", "Sporting CP", 2, 0)]

    verifica(rezultate_api.rezolvator(fetch=fetch)(selectie()) is None,
             "a acceptat meciul invers ca fiind acelasi")


def test_o_singura_cerere_pentru_aceeasi_zi_si_campionat() -> None:
    cereri = []

    def fetch(league_id, data):
        cereri.append((league_id, data))
        return [fixture("Sporting CP", "Arouca", 3, 1),
                fixture("FC Porto", "Benfica", 0, 0)]

    scor = rezultate_api.rezolvator(fetch=fetch)
    scor(selectie())
    scor(selectie(match_id="P1_20260919_Porto_Benfica", home="Porto", away="Benfica"))
    verifica(len(cereri) == 1, f"au fost {len(cereri)} cereri in loc de una")


def test_o_eroare_de_retea_nu_opreste_fisa() -> None:
    def fetch(league_id, data):
        raise RuntimeError("retea cazuta")

    verifica(rezultate_api.rezolvator(fetch=fetch)(selectie()) is None,
             "o eroare ar trebui sa dea None, nu sa arunce")


def test_urmatoarea_etapa_ia_cea_mai_apropiata_zi() -> None:
    zile = {39: "2026-10-10", 140: "2026-10-10", 2: "2026-10-20",
            283: "2026-10-03"}

    def fetch_next(league_id):
        return zile.get(league_id, "2026-11-01")

    etapa = rezultate_api.urmatoarea_etapa(fetch_next=fetch_next)
    verifica(etapa["date"] == "2026-10-03", f"data gresita: {etapa['date']}")
    verifica(etapa["competitions"] == ["Superliga"],
             f"competitii gresite: {etapa['competitions']}")


def test_urmatoarea_etapa_tace_daca_apiul_tace() -> None:
    def fetch_next(league_id):
        raise RuntimeError("fara retea")

    # None inseamna "nu stiu", iar pipeline-ul pastreaza atunci meciurile
    # vechi in loc sa goleasca aplicatia pe baza unei banuieli.
    verifica(rezultate_api.urmatoarea_etapa(fetch_next=fetch_next) is None,
             "fara raspuns de la API ar trebui sa intoarca None")


def test_urmatoarea_etapa_cand_nu_mai_e_nimic_programat() -> None:
    etapa = rezultate_api.urmatoarea_etapa(fetch_next=lambda league_id: None)
    verifica(etapa is not None and etapa["date"] is None,
             "sezon terminat: asteptam un raspuns fara data, nu None")


def main() -> int:
    for test in (test_divizia_din_identificator,
                 test_sezonul_urmeaza_startul_campionatului,
                 test_gaseste_scorul_desi_numele_difera,
                 test_meciul_neinceput_nu_are_scor,
                 test_prelungirile_nu_schimba_scorul_din_timpul_regulamentar,
                 test_nu_confunda_alt_meci_din_aceeasi_zi,
                 test_inversarea_terenului_nu_trece,
                 test_o_singura_cerere_pentru_aceeasi_zi_si_campionat,
                 test_o_eroare_de_retea_nu_opreste_fisa,
                 test_urmatoarea_etapa_ia_cea_mai_apropiata_zi,
                 test_urmatoarea_etapa_tace_daca_apiul_tace,
                 test_urmatoarea_etapa_cand_nu_mai_e_nimic_programat):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru scorurile din API au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

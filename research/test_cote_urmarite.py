"""Teste pentru urmarirea miscarii cotelor."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import cote_urmarite as cu

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def pick(cota, market="home", data="2026-10-09"):
    return {"match_id": "M1", "market": market, "odds": cota, "date": data}


ACUM = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def test_prima_observatie_nu_are_miscare() -> None:
    p = pick(1.60)
    cu.actualizeaza([p], {}, acum=ACUM)
    verifica(p["odds_movement"] == 0.0, f"miscare la prima vedere: {p['odds_movement']}")


def test_cota_care_scade_e_pozitiva() -> None:
    urmarite = cu.actualizeaza([pick(1.70)], {}, acum=ACUM)
    p = pick(1.60)
    cu.actualizeaza([p], urmarite, acum=ACUM)
    verifica(p["odds_movement"] > 0, f"o cota care scade trebuia pozitiva: {p['odds_movement']}")
    verifica(not cu.a_fugit_piata(p), "o cota in scadere a fost scoasa")


def test_cota_care_creste_mult_iese_din_lista() -> None:
    urmarite = cu.actualizeaza([pick(1.50)], {}, acum=ACUM)
    p = pick(1.62)   # +8%
    cu.actualizeaza([p], urmarite, acum=ACUM)
    verifica(cu.a_fugit_piata(p), f"cota crescuta cu 8% a ramas: {p['odds_movement']}")


def test_o_crestere_mica_e_tolerata() -> None:
    urmarite = cu.actualizeaza([pick(1.50)], {}, acum=ACUM)
    p = pick(1.55)   # +3%
    cu.actualizeaza([p], urmarite, acum=ACUM)
    verifica(not cu.a_fugit_piata(p), "o crestere de 3% n-ar trebui sa scoata selectia")


def test_cornerele_fara_cota_nu_se_urmaresc() -> None:
    p = pick(None, market="corners_home_over_3.5")
    urmarite = cu.actualizeaza([p], {}, acum=ACUM)
    verifica(not urmarite and "odds_movement" not in p,
             "o selectie fara cota a intrat in urmarire")


def test_meciurile_vechi_se_curata() -> None:
    vechi = pick(1.60, data=(ACUM - timedelta(days=20)).date().isoformat())
    urmarite = cu.actualizeaza([vechi], {}, acum=ACUM)
    verifica(not urmarite, "un meci de acum 20 de zile a ramas in fisier")


def main() -> int:
    for test in (test_prima_observatie_nu_are_miscare,
                 test_cota_care_scade_e_pozitiva,
                 test_cota_care_creste_mult_iese_din_lista,
                 test_o_crestere_mica_e_tolerata,
                 test_cornerele_fara_cota_nu_se_urmaresc,
                 test_meciurile_vechi_se_curata):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru miscarea cotelor au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

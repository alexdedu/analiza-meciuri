"""Teste pentru colectarea cartonaselor pe reprize.

Colectarea costa mii de cereri si tine zile. Doua lucruri trebuie sa fie sigure:
repriza sa fie atribuita corect (45+3 e tot prima) si rularile urmatoare sa nu
ceara din nou ce s-a adunat deja.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

import pandas as pd

import fetch_card_events as colector

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def card(minut, echipa, detaliu="Yellow Card", extra=None):
    return {"type": "Card", "detail": detaliu,
            "time": {"elapsed": minut, "extra": extra},
            "team": {"name": echipa}}


def test_repriza_dupa_minut() -> None:
    evenimente = [
        card(1, "Gazda"), card(45, "Gazda"), card(45, "Gazda", extra=3),
        card(46, "Oaspete"), card(90, "Oaspete"),
    ]
    c = colector.cartonase_pe_reprize(evenimente, "Gazda")
    verifica(c["hy1"] == 3, f"gazda in prima repriza: {c['hy1']} (asteptat 3)")
    verifica(c["hy2"] == 0, f"gazda in repriza a doua: {c['hy2']}")
    verifica(c["ay2"] == 2, f"oaspete in repriza a doua: {c['ay2']}")
    verifica(c["ay1"] == 0, f"oaspete in prima repriza: {c['ay1']}")


def test_rosu_si_al_doilea_galben() -> None:
    evenimente = [
        card(30, "Gazda", "Red Card"),
        card(70, "Oaspete", "Second Yellow card"),
    ]
    c = colector.cartonase_pe_reprize(evenimente, "Gazda")
    verifica(c["hr1"] == 1 and c["hy1"] == 0, f"rosu direct: {c}")
    # Conventia football-data: al doilea galben intra in ambele coloane.
    verifica(c["ar2"] == 1 and c["ay2"] == 1, f"al doilea galben: {c}")


def test_ignora_ce_nu_e_cartonas() -> None:
    evenimente = [
        {"type": "Goal", "detail": "Normal Goal", "time": {"elapsed": 10},
         "team": {"name": "Gazda"}},
        {"type": "subst", "detail": "Substitution 1", "time": {"elapsed": 60},
         "team": {"name": "Gazda"}},
        card(None, "Gazda"),  # eveniment fara minut
    ]
    c = colector.cartonase_pe_reprize(evenimente, "Gazda")
    verifica(sum(c.values()) == 0, f"au fost numarate evenimente straine: {c}")


def _istoric():
    return pd.DataFrame({
        "div": ["E0", "E0"], "date": pd.to_datetime(["2026-09-01", "2026-09-08"]),
        "home": ["Arsenal", "Chelsea"], "away": ["Chelsea", "Arsenal"],
    })


def _fixture(fid, data="2026-09-20T14:00:00+00:00", status="FT"):
    return {"fixture": {"id": fid, "date": data, "status": {"short": status}},
            "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}}}


def _ruleaza(tmp: Path, buget: int, apeluri: list):
    """Colectare cu API-ul inlocuit; intoarce raportul."""
    def fals(base, headers, cale, **params):
        apeluri.append((cale, params))
        if cale == "fixtures":
            return [_fixture(1001), _fixture(1002), _fixture(1003, status="NS")]
        return [card(20, "Arsenal"), card(60, "Chelsea", "Red Card")]

    with mock.patch.object(colector, "OUT", tmp), \
         mock.patch.object(colector, "_api", fals), \
         mock.patch.object(colector, "load_key", lambda: "cheie"), \
         mock.patch.object(colector, "request_config", lambda k: ("http://x", {})), \
         mock.patch.object(colector, "LIGI", {"E0": 39}), \
         mock.patch.object(colector, "SEZOANE", [2026]), \
         mock.patch.object(colector.time, "sleep", lambda s: None):
        return colector.colecteaza(buget=buget, hist=_istoric())


def test_aduna_si_nu_cere_de_doua_ori() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        apeluri: list = []
        raport = _ruleaza(tmp, buget=50, apeluri=apeluri)

        verifica(raport["meciuri"] == 2,
                 f"asteptam doua meciuri incheiate, am luat {raport['meciuri']}")
        evenimente = [a for a in apeluri if a[0] == "fixtures/events"]
        verifica(len(evenimente) == 2,
                 f"{len(evenimente)} cereri de evenimente in loc de doua")

        # A doua rulare: nimic nou de adunat, deci nicio cerere de evenimente.
        apeluri.clear()
        raport2 = _ruleaza(tmp, buget=50, apeluri=apeluri)
        verifica(raport2["meciuri"] == 0,
                 f"a doua rulare a adunat din nou {raport2['meciuri']} meciuri")
        verifica(not [a for a in apeluri if a[0] == "fixtures/events"],
                 "a cerut evenimente pentru meciuri deja adunate")


def test_bugetul_e_respectat() -> None:
    with tempfile.TemporaryDirectory() as t:
        apeluri: list = []
        # Doua cereri: una pentru lista, una pentru primul meci.
        raport = _ruleaza(Path(t), buget=2, apeluri=apeluri)
        verifica(raport["cereri"] <= 2, f"a cheltuit {raport['cereri']} cereri")
        verifica(raport["meciuri"] == 1,
                 f"cu buget de 2 trebuia un singur meci, nu {raport['meciuri']}")


def test_datele_salvate_se_pot_reciti() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        _ruleaza(tmp, buget=50, apeluri=[])
        with mock.patch.object(colector, "OUT", tmp):
            df = colector.incarca()
        verifica(len(df) == 2, f"citite {len(df)} randuri")
        verifica(set(colector.COLOANE).issubset(df.columns), "lipsesc coloane")
        rand = df.iloc[0]
        verifica(rand["home"] == "Arsenal" and rand["away"] == "Chelsea",
                 f"numele locale nu s-au potrivit: {rand['home']} - {rand['away']}")
        verifica(int(rand["hy1"]) == 1 and int(rand["ar2"]) == 1,
                 f"cartonasele nu s-au salvat corect: {dict(rand)}")


def main() -> int:
    for test in (test_repriza_dupa_minut,
                 test_rosu_si_al_doilea_galben,
                 test_ignora_ce_nu_e_cartonas,
                 test_aduna_si_nu_cere_de_doua_ori,
                 test_bugetul_e_respectat,
                 test_datele_salvate_se_pot_reciti):
        test()
    if esecuri:
        print(f"ESUAT: {len(esecuri)}")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile pentru cartonasele pe reprize au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

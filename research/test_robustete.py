"""Teste pentru comportamentul in caz de pana.

Cele doua reguli pe care se sprijina actualizarea automata:
  1. o descarcare esuata NU distruge datele pe care le avem deja;
  2. o zi fara meciuri NU goleste fisierul de pe care traieste aplicatia.

Amandoua au fost incalcate de versiunea anterioara si au dus la esecul
actualizarii din 17 septembrie 2026.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import download_data
import predict

esecuri: list[str] = []


def verifica(conditie: bool, mesaj: str) -> None:
    if not conditie:
        esecuri.append(f"  {mesaj}")


def test_descarcare_esuata_nu_sterge_datele() -> None:
    """Fisierul existent trebuie sa supravietuiasca unei pene de retea."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        vechi = data / "2627" / "E0.csv"
        vechi.parent.mkdir(parents=True)
        continut = b"x" * 5000
        vechi.write_bytes(continut)

        with mock.patch.object(download_data, "DATA", data), \
             mock.patch.object(download_data, "_descarca", return_value=None):
            rezultat = download_data.fetch("2627", "E0", force=True)

        verifica(rezultat is None, "fetch ar trebui sa semnaleze esecul")
        verifica(vechi.exists(), "fisierul a fost sters desi descarcarea a esuat")
        verifica(vechi.read_bytes() == continut, "fisierul a fost modificat dupa un esec")


def test_descarcare_reusita_inlocuieste() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        dest = data / "2627" / "E0.csv"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"vechi" * 1000)

        with mock.patch.object(download_data, "DATA", data), \
             mock.patch.object(download_data, "_descarca", return_value=b"nou" * 2000), \
             mock.patch.object(download_data.time, "sleep"):
            rezultat = download_data.fetch("2627", "E0", force=True)

        verifica(rezultat is not None, "fetch ar fi trebuit sa reuseasca")
        verifica(dest.read_bytes().startswith(b"nou"), "datele noi nu au fost scrise")


def _ruleaza_fara_meciuri(tmp: str, out: Path, etapa):
    """predict.main() cu zero meciuri si un raspuns dat despre pauza."""
    import pandas as pd

    gol = pd.DataFrame(columns=["div", "Date", "Time", "home", "away",
                                "B365H", "B365D", "B365A", "date"])

    # Istoricul selectiilor e singura copie durabila a bilantului, iar API-ul
    # costa cereri: un test nu are voie sa atinga niciunul. Sursele care ies
    # pe retea (cupe europene, nationale) se inlocuiesc cu liste goale, ca
    # testul sa masoare exact ce vrea: comportarea la zero meciuri.
    import predict_europa
    import predict_national
    import rezultate_api
    import scorecard

    with mock.patch.object(predict, "OUT", out), \
         mock.patch.object(scorecard, "ISTORIC", Path(tmp) / "selectii.json"), \
         mock.patch.object(rezultate_api, "rezolvator", lambda: None), \
         mock.patch.object(rezultate_api, "urmatoarea_etapa", lambda: etapa), \
         mock.patch.object(predict_europa, "construieste_predictii",
                           lambda hist: []), \
         mock.patch.object(predict_national, "construieste_predictii",
                           lambda zile: []), \
         mock.patch.object(predict, "refresh_current_season", return_value=0), \
         mock.patch.object(predict, "get_fixtures", return_value=gol), \
         mock.patch.object(predict, "load_all", return_value=_istoric_minimal()):
        predict.main()


def _fisier_existent(out: Path) -> None:
    out.write_text(json.dumps({
        "generated_at": "2026-09-16T09:00:00+00:00",
        "model": {"name": "test", "backtest": {}},
        "matches": [{"id": "vechi_1"}, {"id": "vechi_2"}],
    }), encoding="utf-8")


def test_zero_meciuri_pastreaza_predictiile_existente() -> None:
    """Cand nu stim de ce nu sunt meciuri, fisierul ramane neatins."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "predictions.json"
        _fisier_existent(out)
        # None = API-ul n-a raspuns, deci nu stim daca e pauza sau pana.
        _ruleaza_fara_meciuri(tmp, out, etapa=None)

        pastrat = json.loads(out.read_text(encoding="utf-8"))
        verifica(len(pastrat.get("matches", [])) == 2,
                 "predictiile existente au fost sterse de o rulare fara meciuri")


def test_pauza_confirmata_inlocuieste_meciurile_vechi() -> None:
    """Pauza competitionala nu trebuie sa arate ca o lista inghetata.

    Daca API-ul confirma ca urmatoarele meciuri sunt peste doua saptamani,
    meciurile de saptamana trecuta nu mai au ce cauta in aplicatie: ar parea
    program viitor. Le inlocuim cu explicatia.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "predictions.json"
        _fisier_existent(out)
        _ruleaza_fara_meciuri(tmp, out, etapa={
            "date": "2026-10-10", "competitions": ["Premier League"]})

        nou = json.loads(out.read_text(encoding="utf-8"))
        verifica(nou.get("matches") == [],
                 "meciurile vechi au ramas desi e pauza confirmata")
        verifica(nou.get("next_round", {}).get("date") == "2026-10-10",
                 "aplicatia nu afla cand se reiau meciurile")


def _istoric_minimal():
    import pandas as pd
    return pd.DataFrame({
        "div": ["E0"], "league_name": ["Premier League"], "date": [pd.Timestamp("2026-09-01")],
        "home": ["Arsenal"], "away": ["Chelsea"], "hg": [1], "ag": [0],
        "hst": [4.0], "ast": [2.0],
    })


def main() -> int:
    test_descarcare_esuata_nu_sterge_datele()
    test_descarcare_reusita_inlocuieste()
    test_zero_meciuri_pastreaza_predictiile_existente()
    test_pauza_confirmata_inlocuieste_meciurile_vechi()

    if esecuri:
        print(f"ESUAT: {len(esecuri)} verificari")
        print("\n".join(esecuri))
        return 1
    print("Toate verificarile de robustete au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

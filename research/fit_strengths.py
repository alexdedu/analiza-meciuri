"""Estimeaza puterea fiecarui campionat si o salveaza pe disc.

Calculul dureaza ~2 minute, iar valorile se schimba foarte incet: ierarhia
campionatelor nu se rastoarna de la o zi la alta. Deci il rulam rar, iar
predictia zilnica doar citeste rezultatul.

Iesire: data/europa/puteri.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from backtest_europa import construieste_tabelul
from data_loader import load_all
from europe_model import EUROPA, fit_puteri, incarca_europa

IESIRE = EUROPA / "puteri.json"
# Peste atatea zile, valorile se considera invechite si se recalculeaza.
VALABILITATE_ZILE = 30


def este_proaspat() -> bool:
    if not IESIRE.exists():
        return False
    try:
        date = json.loads(IESIRE.read_text(encoding="utf-8"))
        generat = datetime.fromisoformat(date["generated_at"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return False
    varsta = (datetime.now(timezone.utc) - generat).days
    return varsta < VALABILITATE_ZILE


def main() -> int:
    t0 = time.time()
    if este_proaspat() and "--force" not in sys.argv:
        date = json.loads(IESIRE.read_text(encoding="utf-8"))
        print(f"Puterile sunt inca proaspete ({date['generated_at'][:10]}). "
              "Foloseste --force ca sa recalculezi.")
        return 0

    print("Incarc datele...")
    hist = load_all()
    eu = incarca_europa(hist)
    tabel = construieste_tabelul(hist, eu)
    if tabel.empty:
        print("Nu am destule meciuri europene utilizabile.")
        return 1

    ligi = sorted(set(tabel["div_home"]) | set(tabel["div_away"]))
    puteri, gamma, rho = fit_puteri(tabel, ligi, pd.Timestamp.now())

    IESIRE.parent.mkdir(parents=True, exist_ok=True)
    IESIRE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meciuri_folosite": len(tabel),
        "avantaj_teren": round(gamma, 4),
        "rho": round(rho, 4),
        "puteri": {k: round(v, 4) for k, v in sorted(puteri.items(), key=lambda x: -x[1])},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(puteri)} campionate, din {len(tabel):,} meciuri europene")
    print(f"Salvat in {IESIRE}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

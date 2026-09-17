"""Descarca CSV-uri istorice de la football-data.co.uk (gratuit, fara cont).

Fiecare fisier = o liga x un sezon, cu rezultate + cote de la case de pariuri.
Datele sunt cache-uite local; rulari repetate nu re-descarca.
"""
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.football-data.co.uk/mmz4281"
DATA = Path(__file__).parent / "data"

# Ligile cu cel mai bun istoric de cote si acoperire consistenta
LEAGUES = {
    "E0": "Premier League",
    "E1": "Championship",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "B1": "Jupiler Pro League",
    "T1": "Super Lig",
    "G1": "Super League Greece",
    "SC0": "Scottish Premiership",
}

# 2014/15 .. 2026/27
SEASONS = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2014, 2027)]

# Campionatele din afara "nucleului" englezesc stau in alt format: un singur
# fisier cumulativ per tara, cu toate sezoanele. Au cote 1X2 de inchidere, dar
# nu au suturi pe poarta si nici cote Over/Under.
# Cheia e codul folosit de site; valorile sunt numele tarii asa cum apare in
# fisier si numele afisat in aplicatie.
EXTRA_LEAGUES = {
    "ARG": ("Argentina", "Argentina"),
    "AUT": ("Austria", "Austria"),
    "BRA": ("Brazil", "Brazilia"),
    "CHN": ("China", "China"),
    "DNK": ("Denmark", "Danemarca"),
    "FIN": ("Finland", "Finlanda"),
    "IRL": ("Ireland", "Irlanda"),
    "JPN": ("Japan", "Japonia"),
    "MEX": ("Mexico", "Mexic"),
    "NOR": ("Norway", "Norvegia"),
    "POL": ("Poland", "Polonia"),
    "ROU": ("Romania", "Romania"),
    "RUS": ("Russia", "Rusia"),
    "SWE": ("Sweden", "Suedia"),
    "SWZ": ("Switzerland", "Elvetia"),
    "USA": ("USA", "SUA"),
}

EXTRA_DIR = DATA / "extra"


def _descarca(url: str, incercari: int = 3) -> bytes | None:
    """Continutul fisierului, sau None. Reincearca: retelele mai si clipesc."""
    for incercare in range(incercari):
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) >= 1000:
                return r.content
        except requests.RequestException:
            pass
        if incercare < incercari - 1:
            time.sleep(1.5 * (incercare + 1))
    return None


def fetch(season: str, code: str, force: bool = False) -> str | None:
    """Descarca un fisier. NU sterge nimic daca descarcarea esueaza.

    `force` re-descarca chiar daca fisierul exista deja (sezonul curent se
    schimba dupa fiecare etapa), dar il inlocuieste doar dupa ce noile date au
    ajuns intregi. Varianta veche stergea intai si descarca dupa, deci o pana
    de retea lasa proiectul fara date.
    """
    dest = DATA / season / f"{code}.csv"
    if not force and dest.exists() and dest.stat().st_size > 1000:
        return "cached"
    dest.parent.mkdir(parents=True, exist_ok=True)

    continut = _descarca(f"{BASE}/{season}/{code}.csv")
    if continut is None:
        return None  # fisierul existent ramane neatins
    dest.write_bytes(continut)
    time.sleep(0.4)  # politicos fata de server
    return f"{len(continut) // 1024} KB"


def fetch_extra(code: str) -> str | None:
    """Fisierele cumulative se re-descarca mereu: contin si meciurile de ieri."""
    dest = EXTRA_DIR / f"{code}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    continut = _descarca(f"https://www.football-data.co.uk/new/{code}.csv")
    if continut is None:
        return None
    dest.write_bytes(continut)
    time.sleep(0.4)
    return f"{len(continut) // 1024} KB"


def main() -> int:
    ok = skipped = 0
    for season in SEASONS:
        line = []
        for code in LEAGUES:
            res = fetch(season, code)
            if res is None:
                skipped += 1
            else:
                ok += 1
                if res != "cached":
                    line.append(code)
        if line:
            print(f"  {season}: descarcat {' '.join(line)}", flush=True)

    extra_ok = []
    for code in EXTRA_LEAGUES:
        if fetch_extra(code):
            extra_ok.append(code)
            ok += 1
        else:
            skipped += 1
    if extra_ok:
        print(f"  campionate suplimentare: {' '.join(extra_ok)}", flush=True)

    print(f"\nGata: {ok} fisiere disponibile, {skipped} indisponibile (sezon/liga inexistenta).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

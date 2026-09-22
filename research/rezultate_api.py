"""Scorurile de ieri, luate de la API-Football in loc sa fie asteptate.

De ce exista fisierul asta: modelul se antreneaza pe arhivele football-data.co.uk,
singurele gratuite care au si cote, si suturi, si zece ani de istoric. Dar acele
fisiere se publica de cateva ori pe saptamana, asa ca un meci de vineri seara
apare acolo abia luni. Pentru fisa de rezultate asta inseamna doua-trei zile in
care aplicatia nu stie daca selectia a iesit sau nu.

API-Football stie scorul la cateva minute dupa fluierul final. Il folosim deci
la verificarea selectiilor, si pastram football-data pentru antrenament, unde
intarzierea nu conteaza (un meci intra in model cu aceeasi greutate si peste o
saptamana).

Cost: o cerere per (campionat, zi) cu selectii nerezolvate, deci sub zece pe
rulare din cele 7.500 zilnice.
"""
from __future__ import annotations

from datetime import datetime

import requests

from api_config import load_key, request_config
from team_matching import build_matcher

# Verificate prin /leagues pe 20 sept 2026.
LIGI = {
    "E0": 39,             # Premier League
    "E1": 40,             # Championship
    "SP1": 140,           # La Liga
    "I1": 135,            # Serie A
    "D1": 78,             # Bundesliga
    "F1": 61,             # Ligue 1
    "N1": 88,             # Eredivisie
    "P1": 94,             # Primeira Liga
    "B1": 144,            # Jupiler Pro League
    "ROU_Superliga": 283,  # Liga I
}

# Doar meciurile incheiate au un scor care conteaza. "AET" si "PEN" sunt
# meciuri prelungite: pentru ele luam scorul din timpul regulamentar, pentru ca
# pe el se face si pariul.
STATUSURI_FINALE = {"FT", "AET", "PEN"}


# Cupele europene nu apar in LIGI (au alt model), dar cand campionatele stau,
# ele sunt de obicei primele care se reiau, deci conteaza la "cand revin meciurile".
COMPETITII_EUROPENE = {2: "Champions League", 3: "Europa League",
                       848: "Conference League"}

NUME_LIGI = {
    "E0": "Premier League", "E1": "Championship", "SP1": "La Liga",
    "I1": "Serie A", "D1": "Bundesliga", "F1": "Ligue 1", "N1": "Eredivisie",
    "P1": "Primeira Liga", "B1": "Jupiler Pro League", "ROU_Superliga": "Superliga",
}


def divizia(match_id: str) -> str | None:
    """Campionatul din identificatorul unui meci, daca il acoperim."""
    # "ROU_Superliga_..." incepe si cu "ROU_", deci potrivirea cea mai lunga
    # castiga; altfel un meci din Romania ar cadea pe o liga inexistenta.
    potriviri = [div for div in LIGI if match_id.startswith(div + "_")]
    return max(potriviri, key=len) if potriviri else None


def sezonul(data: str) -> int:
    """Anul in care a inceput sezonul, asa cum il numeroteaza API-Football."""
    d = datetime.fromisoformat(data)
    return d.year if d.month >= 7 else d.year - 1


def _cere(base: str, headers: dict, league_id: int, data: str) -> list[dict]:
    r = requests.get(f"{base}/fixtures", headers=headers,
                     params={"league": league_id, "season": sezonul(data),
                             "date": data},
                     timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def _scoruri_din_raspuns(raspuns: list[dict]) -> dict[tuple[str, str], tuple[int, int]]:
    """Scorurile finale, pe perechea de nume asa cum le scrie API-ul."""
    out = {}
    for item in raspuns:
        if item["fixture"]["status"]["short"] not in STATUSURI_FINALE:
            continue
        final = item["score"]["fulltime"]
        if final["home"] is None or final["away"] is None:
            continue
        out[(item["teams"]["home"]["name"], item["teams"]["away"]["name"])] = (
            int(final["home"]), int(final["away"]))
    return out


def rezolvator(fetch=None):
    """Functia care afla scorul unei selectii, cu raspunsurile tinute minte.

    Intoarce None daca nu exista cheie: fara ea pipeline-ul merge mai departe
    cu verificarea din fisierele football-data, doar mai incet.

    `fetch(league_id, data) -> list[dict]` se poate inlocui in teste, ca sa nu
    depinda de retea.
    """
    if fetch is None:
        key = load_key()
        if not key:
            return None
        base, headers = request_config(key)

        def fetch(league_id: int, data: str) -> list[dict]:
            return _cere(base, headers, league_id, data)

    memorie: dict[tuple[int, str], dict] = {}

    def scor(sel: dict) -> tuple[int, int] | None:
        div = divizia(sel["match_id"])
        if div is None:
            return None

        cheie = (LIGI[div], sel["date"])
        if cheie not in memorie:
            try:
                memorie[cheie] = _scoruri_din_raspuns(fetch(*cheie))
            except Exception as exc:
                print(f"  (scorurile API pentru {div} {sel['date']}: {str(exc)[:70]})")
                memorie[cheie] = {}

        zi = memorie[cheie]
        if not zi:
            return None

        # Numele difera intre surse ("Sporting CP" la API, "Sp Lisbon" la noi),
        # deci traducem numele API catre al nostru -- directia in care sunt
        # scrise aliasurile. Comparam doar cu cele doua echipe ale selectiei, si
        # doar intre meciurile acelei zile din acel campionat: spatiul e atat de
        # ingust incat confuziile dintre campionate, care ne-au dat batai de cap
        # la cupele europene, nu mai sunt posibile aici.
        e_gazda = build_matcher([sel["home"]])
        e_oaspete = build_matcher([sel["away"]])
        for (gazda_api, oaspete_api), rezultat in zi.items():
            if (e_gazda(gazda_api) == sel["home"]
                    and e_oaspete(oaspete_api) == sel["away"]):
                return rezultat
        return None

    return scor


def _urmatorul(base: str, headers: dict, league_id: int) -> str | None:
    """Data primului meci neinceput dintr-o competitie, format YYYY-MM-DD."""
    r = requests.get(f"{base}/fixtures", headers=headers,
                     params={"league": league_id, "next": 1}, timeout=30)
    r.raise_for_status()
    raspuns = r.json().get("response") or []
    return raspuns[0]["fixture"]["date"][:10] if raspuns else None


def urmatoarea_etapa(fetch_next=None) -> dict | None:
    """Cand se reiau meciurile, cand nu e nimic de prezis in zilele urmatoare.

    Fara asta, o pauza competitionala arata in aplicatie exact ca o defectiune:
    lista ramane inghetata pe ultima zi cu meciuri si nimeni nu stie de ce.

    Intoarce None daca API-ul nu raspunde deloc -- si atunci chiar nu stim daca
    e pauza sau pana, deci nu avem voie sa golim lista din aplicatie.
    """
    if fetch_next is None:
        key = load_key()
        if not key:
            return None
        base, headers = request_config(key)

        def fetch_next(league_id: int) -> str | None:
            return _urmatorul(base, headers, league_id)

    competitii = [(NUME_LIGI.get(div, div), lid) for div, lid in LIGI.items()]
    competitii += [(nume, lid) for lid, nume in COMPETITII_EUROPENE.items()]

    gasite: list[tuple[str, str]] = []
    raspunsuri = 0
    for nume, league_id in competitii:
        try:
            data = fetch_next(league_id)
            raspunsuri += 1
        except Exception:
            continue
        if data:
            gasite.append((data, nume))

    if not raspunsuri:
        return None  # API-ul tace: nu tragem nicio concluzie
    if not gasite:
        return {"date": None, "competitions": []}

    prima = min(data for data, _ in gasite)
    return {
        "date": prima,
        # Cine joaca in prima zi: de obicei una-doua competitii, nu toate.
        "competitions": sorted(nume for data, nume in gasite if data == prima),
    }

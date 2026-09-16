"""Potriveste numele echipelor intre API-Football si football-data.co.uk.

Cele doua surse scriu acelasi club diferit: "Manchester City" vs "Man City",
"Borussia Monchengladbach" vs "M'gladbach", "Athletic Club" vs "Ath Bilbao".
O potrivire naiva pe similaritate de sir rateaza tocmai prescurtarile, care
sunt cazul cel mai frecvent.

Strategia, in ordine:
  1. alias explicit (tabelul de mai jos) -- pentru cazurile care nu se pot ghici;
  2. potrivire pe cuvinte, tratand prescurtarile ca prefixe ("Man" ~ "Manchester");
  3. similaritate clasica de sir, ca plasa de siguranta.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

# Cazuri pe care niciun algoritm nu le poate deduce: prescurtari, nume istorice,
# orase scrise altfel. Cheia e numele din API-Football.
ALIAS = {
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Wolverhampton Wanderers": "Wolves",
    "Sheffield Utd": "Sheffield United",
    "West Bromwich Albion": "West Brom",
    "Queens Park Rangers": "QPR",
    "Athletic Club": "Ath Bilbao",
    "Atletico Madrid": "Ath Madrid",
    "Rayo Vallecano": "Vallecano",
    "Celta Vigo": "Celta",
    "Real Betis": "Betis",
    "Real Sociedad": "Sociedad",
    "Deportivo La Coruna": "La Coruna",
    "Real Valladolid": "Valladolid",
    "Espanyol": "Espanol",
    "Racing Santander": "Santander",
    "Hellas Verona": "Verona",
    "Internazionale": "Inter",
    "AC Milan": "Milan",
    "Borussia Monchengladbach": "M'gladbach",
    "Borussia Dortmund": "Dortmund",
    "Bayern Munchen": "Bayern Munich",
    "FSV Mainz 05": "Mainz",
    "1. FC Koln": "FC Koln",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "Bayer Leverkusen": "Leverkusen",
    "VfB Stuttgart": "Stuttgart",
    "SC Freiburg": "Freiburg",
    "Paris Saint Germain": "Paris SG",
    "Stade Brestois 29": "Brest",
    "Olympique Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "Sporting CP": "Sp Lisbon",
    "Vitoria SC": "Guimaraes",
    "FC Porto": "Porto",
    "Sporting Braga": "Sp Braga",
    "Universitatea Craiova": "Univ. Craiova",
    "Universitatea Cluj": "U. Cluj",
    "FCSB": "FCSB",
    "Petrolul Ploiesti": "Petrolul",
    "Arges Pitesti": "Arges",
    "Otelul Galati": "Otelul",
    "Sepsi OSK": "Sepsi",
    "CFR 1907 Cluj": "CFR Cluj",
    "Rapid Bucuresti": "Rapid",
    "Dinamo Bucuresti": "Dinamo",
    "Ajax": "Ajax",
    "PSV Eindhoven": "PSV Eindhoven",
    "Club Brugge KV": "Club Brugge",
    "Royal Antwerp": "Antwerp",
    "Standard Liege": "Standard",
    "Fenerbahce": "Fenerbahce",
    "Galatasaray": "Galatasaray",
    "Besiktas": "Besiktas",
    "Istanbul Basaksehir": "Buyuksehyr",
    "Olympiakos Piraeus": "Olympiakos",
    "Panathinaikos": "Panathinaikos",
    "PAOK": "PAOK",
    "AEK Athens": "AEK",
    "Celtic": "Celtic",
    "Rangers": "Rangers",
    "Heart Of Midlothian": "Hearts",
}

# Cuvinte care apar la aproape orice club si nu ajuta la distinctie.
ZGOMOT = {
    "fc", "afc", "cf", "sc", "ac", "as", "ss", "ssc", "cd", "ud", "rc", "sv",
    "tsv", "vfb", "vfl", "fsv", "bsc", "fk", "nk", "hnk", "sk", "bk", "if",
    "club", "calcio", "futbol", "football", "de", "of", "the", "1", "05", "04",
    "1899", "1900", "1907", "09", "team", "kv", "sa", "cp", "cs", "acs", "asa",
}


def normalize(name: str) -> list[str]:
    """Numele, redus la cuvintele care chiar disting clubul."""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("'", "").replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    cuvinte = [w for w in text.split() if w and w not in ZGOMOT]
    return cuvinte or text.split()


def _token_score(a: list[str], b: list[str]) -> float:
    """Cat de bine se acopera doua liste de cuvinte, cu prescurtari acceptate."""
    if not a or not b:
        return 0.0
    scurt, lung = (a, b) if len(a) <= len(b) else (b, a)
    total = 0.0
    for cuvant in scurt:
        cel_mai_bun = 0.0
        for altul in lung:
            if cuvant == altul:
                scor = 1.0
            elif len(cuvant) >= 3 and altul.startswith(cuvant):
                scor = 0.92  # "man" din "manchester"
            elif len(altul) >= 3 and cuvant.startswith(altul):
                scor = 0.92
            else:
                scor = difflib.SequenceMatcher(None, cuvant, altul).ratio()
                scor = scor if scor > 0.85 else 0.0
            cel_mai_bun = max(cel_mai_bun, scor)
        total += cel_mai_bun
    # Penalizarea de lungime trebuie sa fie severa. Cu una blanda,
    # "Inter Club d'Escaldes" (Andorra) ajunge sa fie confundata cu Inter
    # Milano, iar o astfel de greseala strica estimarea puterii unui campionat.
    return (total / len(scurt)) * (len(scurt) / len(lung)) ** 0.5


def _fara_diacritice(text: str) -> str:
    plat = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in plat if not unicodedata.combining(c)).lower()


# API-ul scrie acelasi club diferit de la un sezon la altul ("Bayern Munich"
# intr-unul, "Bayern Munchen" in altul), deci aliasurile se cauta fara diacritice.
ALIAS_PLAT = {_fara_diacritice(k): v for k, v in ALIAS.items()}


def build_matcher(nume_locale: list[str]):
    """Intoarce o functie care traduce un nume din API in numele nostru."""
    locale_norm = {n: normalize(n) for n in nume_locale}
    set_local = set(nume_locale)

    def match(nume_api: str) -> str | None:
        alias = ALIAS_PLAT.get(_fara_diacritice(nume_api))
        if alias:
            return alias if alias in set_local else None
        if nume_api in set_local:
            return nume_api

        tokens = normalize(nume_api)
        cel_mai_bun, scor_max = None, 0.0
        for local, t_local in locale_norm.items():
            scor = _token_score(tokens, t_local)
            if scor > scor_max:
                cel_mai_bun, scor_max = local, scor
        return cel_mai_bun if scor_max >= 0.82 else None

    return match

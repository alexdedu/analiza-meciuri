"""Teste pentru potrivirea numelor de echipe.

O potrivire gresita e mai rea decat una lipsa: daca "Inter Club d'Escaldes"
(Andorra) devine Inter Milano, modelul crede ca un club de top a pierdut cu
echipe modeste si strica estimarea pentru tot campionatul italian.
"""
from __future__ import annotations

import sys

from team_matching import build_matcher, normalize

LOCALE = [
    "Bragantino",  # capcana: "Braga" e prefix, dar e alt club, din alta tara
    "Sp Braga",
    "Man City", "Man United", "Ath Bilbao", "Ath Madrid", "M'gladbach",
    "Bayern Munich", "Dortmund", "Paris SG", "Milan", "Inter", "Inter Turku",
    "Inter Miami", "Sp Lisbon", "Porto", "Olympiakos", "Univ. Craiova",
    "FCSB", "CFR Cluj", "Ajax", "Feyenoord", "Celtic", "Arsenal", "Brest",
]

CAZURI_CORECTE = [
    ("Manchester City", "Man City"),
    ("Manchester United", "Man United"),
    ("Athletic Club", "Ath Bilbao"),
    ("Atletico Madrid", "Ath Madrid"),
    ("Borussia Monchengladbach", "M'gladbach"),
    ("Borussia Mönchengladbach", "M'gladbach"),   # cu diacritice
    ("Bayern Munich", "Bayern Munich"),
    ("Bayern München", "Bayern Munich"),          # cealalta scriere din API
    ("Borussia Dortmund", "Dortmund"),
    ("Paris Saint Germain", "Paris SG"),
    ("AC Milan", "Milan"),
    ("Sporting CP", "Sp Lisbon"),
    ("FC Porto", "Porto"),
    ("Olympiakos Piraeus", "Olympiakos"),
    ("Universitatea Craiova", "Univ. Craiova"),
    ("Ajax", "Ajax"),
    ("Feyenoord", "Feyenoord"),
    ("Celtic", "Celtic"),
    ("Arsenal", "Arsenal"),
    ("Stade Brestois 29", "Brest"),
    ("SC Braga", "Sp Braga"),
    ("Sporting Braga", "Sp Braga"),
]

# Echipe din campionate pe care nu le acoperim: raspunsul corect e "nu stiu".
TREBUIE_RESPINSE = [
    "Inter Club d'Escaldes",   # Andorra, nu Inter Milano
    "FK Trakai",               # Lituania
    "Aberystwyth Town",        # Tara Galilor
    "Apoel Nicosia",           # Cipru
    "Ararat-Armenia",          # Armenia
    "AS Jeunesse Esch",        # Luxemburg
]

# Cluburi diferite cu nume asemanator nu trebuie confundate intre ele.
FARA_CONFUZIE = [
    ("Inter", "Inter"),
    ("Inter Turku", "Inter Turku"),
    ("Inter Miami", "Inter Miami"),
]


def main() -> int:
    match = build_matcher(LOCALE)
    esecuri = []

    for api_nume, asteptat in CAZURI_CORECTE:
        obtinut = match(api_nume)
        if obtinut != asteptat:
            esecuri.append(f"  {api_nume!r}: asteptat {asteptat!r}, obtinut {obtinut!r}")

    for api_nume in TREBUIE_RESPINSE:
        obtinut = match(api_nume)
        if obtinut is not None:
            esecuri.append(f"  {api_nume!r}: trebuia respins, dar a dat {obtinut!r}")

    for api_nume, asteptat in FARA_CONFUZIE:
        obtinut = match(api_nume)
        if obtinut != asteptat:
            esecuri.append(f"  {api_nume!r}: asteptat {asteptat!r}, obtinut {obtinut!r}")

    # Normalizarea trebuie sa scoata zgomotul, dar sa nu goleasca numele.
    if normalize("FC") == []:
        esecuri.append("  normalize('FC') a golit complet numele")
    if "manchester" not in normalize("Manchester City"):
        esecuri.append("  normalize a pierdut cuvantul principal")

    total = len(CAZURI_CORECTE) + len(TREBUIE_RESPINSE) + len(FARA_CONFUZIE) + 2
    if esecuri:
        print(f"ESUAT: {len(esecuri)} din {total}")
        print("\n".join(esecuri))
        return 1
    print(f"Toate cele {total} verificari au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

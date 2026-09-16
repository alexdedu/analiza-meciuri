"""Citeste cheia API-Football, fara sa o scrie nicaieri in repo.

Ordinea de cautare:
  1. variabila de mediu APIFOOTBALL_KEY  (asa o primeste GitHub Actions)
  2. fisierul research/.secrets.env      (asa o folosesti local)

Fisierul .secrets.env e in .gitignore. Repo-ul fiind public, o cheie ajunsa
intr-un commit ar trebui considerata compromisa si regenerata imediat.
"""
from __future__ import annotations

import os
from pathlib import Path

SECRETS_FILE = Path(__file__).parent / ".secrets.env"

# API-Football se poate folosi direct sau prin RapidAPI, cu anteturi diferite.
DIRECT_HOST = "v3.football.api-sports.io"
RAPID_HOST = "api-football-v1.p.rapidapi.com"


def load_key() -> str | None:
    """Cheia, sau None daca nu e configurata nicaieri."""
    key = os.environ.get("APIFOOTBALL_KEY", "").strip()
    if key:
        return key

    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "APIFOOTBALL_KEY":
                # Acceptam si ghilimele, ca sa nu se supere nimeni pe format.
                return value.strip().strip('"').strip("'")
    return None


def request_config(key: str) -> tuple[str, dict[str, str]]:
    """Adresa de baza si anteturile, pentru accesul direct."""
    return f"https://{DIRECT_HOST}", {"x-apisports-key": key}


def rapid_config(key: str) -> tuple[str, dict[str, str]]:
    """Varianta prin RapidAPI, daca acolo ai facut abonamentul."""
    return (f"https://{RAPID_HOST}/v3",
            {"x-rapidapi-key": key, "x-rapidapi-host": RAPID_HOST})

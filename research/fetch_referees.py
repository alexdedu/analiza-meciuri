"""Cine a arbitrat fiecare meci, de la API-Football.

Arbitrul nu apare in arhivele football-data decat la campionatele englezesti,
dar API-ul il da la orice meci, in lista de meciuri a sezonului -- o singura
cerere per campionat si sezon. Opt sezoane pe zece campionate costa 80 de
cereri, o data; dupa aceea doar sezonul curent se reimprospateaza.

Numele vin uneori cu tara la coada ("Michael Oliver, England") si cu spatii
diferite de la un sezon la altul. Le aducem la o forma comuna, altfel acelasi
arbitru ar aparea ca doi oameni diferiti si istoricul lui s-ar injumatati.
"""
from __future__ import annotations

import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from api_config import load_key, request_config
from rezultate_api import LIGI, STATUSURI_FINALE
from team_matching import build_matcher

OUT = Path(__file__).parent / "data" / "arbitri"
SEZOANE = range(2019, 2027)
SEZON_CURENT = 2026


def normalizeaza(nume) -> str | None:
    """'Michael  Oliver, England' -> 'michael oliver'."""
    if nume is None or (isinstance(nume, float) and pd.isna(nume)):
        return None
    text = str(nume).split(",")[0]
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z\s\-']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _api(base: str, headers: dict, **params) -> list[dict]:
    r = requests.get(f"{base}/fixtures", headers=headers, params=params, timeout=40)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:120])
    return body.get("response") or []


def randuri(raspuns: list[dict], div: str, season: int, match) -> list[dict]:
    """Meciurile cu arbitru si nume traduse in denumirile noastre."""
    out = []
    for item in raspuns:
        fx = item["fixture"]
        arbitru = normalizeaza(fx.get("referee"))
        gazda = match(item["teams"]["home"]["name"])
        oaspete = match(item["teams"]["away"]["name"])
        out.append({
            "fixture_id": fx["id"],
            "date": fx["date"][:10],
            "div": div,
            "season": season,
            "home": gazda or "",
            "away": oaspete or "",
            "referee": arbitru or "",
            "jucat": fx["status"]["short"] in STATUSURI_FINALE,
        })
    return out


def descarca(hist: pd.DataFrame | None = None) -> int:
    key = load_key()
    if not key:
        print("Cheia API lipseste; nu pot aduce arbitrii.")
        return 0
    base, headers = request_config(key)
    OUT.mkdir(parents=True, exist_ok=True)

    if hist is None:
        from data_loader import load_all
        hist = load_all()

    cereri = 0
    for div, liga_id in LIGI.items():
        liga = hist[hist["div"] == div]
        match = build_matcher(sorted(set(liga["home"]) | set(liga["away"])))
        for season in SEZOANE:
            dest = OUT / f"{div}_{season}.csv"
            # Sezoanele incheiate nu se mai schimba; cel curent se reimprospateaza,
            # ca sa prinda si arbitrii delegati pentru meciurile urmatoare.
            if dest.exists() and season < SEZON_CURENT:
                continue
            try:
                raspuns = _api(base, headers, league=liga_id, season=season)
                cereri += 1
            except Exception as exc:
                print(f"  {div} {season}: {str(exc)[:70]}")
                continue
            pd.DataFrame(randuri(raspuns, div, season, match)).to_csv(dest, index=False)
            time.sleep(0.3)
    return cereri


def incarca() -> pd.DataFrame:
    if not OUT.exists():
        return pd.DataFrame()
    bucati = [pd.read_csv(f) for f in sorted(OUT.glob("*.csv")) if f.stat().st_size > 50]
    if not bucati:
        return pd.DataFrame()
    df = pd.concat(bucati, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df["referee"] = df["referee"].fillna("").astype(str)
    return df.drop_duplicates(subset=["fixture_id"])


def main() -> int:
    cereri = descarca()
    df = incarca()
    if df.empty:
        print("Niciun arbitru adus.")
        return 1
    cu_arbitru = df[df["referee"] != ""]
    print(f"{len(df):,} meciuri, {len(cu_arbitru):,} cu arbitru, "
          f"{cu_arbitru['referee'].nunique()} arbitri ({cereri} cereri noi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

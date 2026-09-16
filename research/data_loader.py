"""Incarca toate CSV-urile descarcate intr-un singur DataFrame curat.

Sursa are doua formate diferite:
  - campionatele "de baza" (Anglia, Spania, Italia...): un fisier per liga si
    sezon, cu statistici de meci, suturi si cote pentru multe piete;
  - campionatele suplimentare (Romania, Polonia, Brazilia...): un singur fisier
    cumulativ per tara, doar cu rezultate si cote 1X2.
Le aducem pe amandoua la aceeasi forma; coloanele care lipsesc raman goale, iar
modelul se descurca fara ele.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from download_data import EXTRA_DIR, EXTRA_LEAGUES, LEAGUES

DATA = Path(__file__).parent / "data"

# cote de inchidere (sufix C) cu rezerva pe cele pre-meci daca lipsesc
ODDS = {
    "psc_h": ["PSCH", "PSH"], "psc_d": ["PSCD", "PSD"], "psc_a": ["PSCA", "PSA"],
    "avg_h": ["AvgCH", "AvgH", "BbAvH"], "avg_d": ["AvgCD", "AvgD", "BbAvD"],
    "avg_a": ["AvgCA", "AvgA", "BbAvA"],
    "max_h": ["MaxCH", "MaxH", "BbMxH"], "max_d": ["MaxCD", "MaxD", "BbMxD"],
    "max_a": ["MaxCA", "MaxA", "BbMxA"],
    "avg_o25": ["AvgC>2.5", "Avg>2.5", "BbAv>2.5"],
    "avg_u25": ["AvgC<2.5", "Avg<2.5", "BbAv<2.5"],
    "max_o25": ["MaxC>2.5", "Max>2.5", "BbMx>2.5"],
    "max_u25": ["MaxC<2.5", "Max<2.5", "BbMx<2.5"],
}

COLUMNS = ["div", "league_name", "season", "date", "home", "away", "hg", "ag",
           "hst", "ast", *ODDS]


def league_slug(name: str) -> str:
    """'Liga Profesional ' si 'Liga Profesional' trebuie sa dea acelasi cod.

    Fisierele sursa contin spatii in plus la capete si intre cuvinte, iar fara
    normalizare aceeasi competitie ar aparea de doua ori, cu istoricul taiat in
    doua si cu echipele impartite intre ele.
    """
    return "".join(word.capitalize() for word in str(name).split())


def _empty(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(index=index)


def _load_core() -> list[pd.DataFrame]:
    frames = []
    for path in sorted(DATA.glob("[0-9]*/*.csv")):
        try:
            df = pd.read_csv(path, encoding="latin-1", on_bad_lines="skip", low_memory=False)
        except Exception:
            continue
        # BOM-ul UTF-8 citit ca latin-1 devine trei caractere; taiem orice
        # nu e alfanumeric de la inceputul numelui de coloana.
        df.columns = [c.strip().lstrip("﻿ï»¿") for c in df.columns]
        if not {"HomeTeam", "AwayTeam", "FTHG", "FTAG", "Date"}.issubset(df.columns):
            continue
        # ATENTIE: indexul trebuie luat de la df. Atribuirea unui scalar pe un
        # DataFrame gol nu creeaza randuri, iar coloana ramane NaN dupa aceea.
        out = _empty(df.index)
        out["div"] = (df["Div"].astype("string").str.strip() if "Div" in df.columns
                      else path.stem)
        out["league_name"] = out["div"].map(lambda d: LEAGUES.get(d, d))
        out["season"] = path.parent.name
        out["date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
        out["home"] = df["HomeTeam"].astype("string").str.strip()
        out["away"] = df["AwayTeam"].astype("string").str.strip()
        out["hg"] = pd.to_numeric(df["FTHG"], errors="coerce")
        out["ag"] = pd.to_numeric(df["FTAG"], errors="coerce")
        # suturi pe poarta: proxy gratuit de xG, prezent doar in acest format
        out["hst"] = pd.to_numeric(df["HST"], errors="coerce") if "HST" in df else None
        out["ast"] = pd.to_numeric(df["AST"], errors="coerce") if "AST" in df else None
        for target, candidates in ODDS.items():
            col = next((c for c in candidates if c in df.columns), None)
            out[target] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA
            out[target] = pd.to_numeric(out[target], errors="coerce")
        frames.append(out[COLUMNS])
    return frames


def _load_extra() -> list[pd.DataFrame]:
    frames = []
    for code, (_, tara) in EXTRA_LEAGUES.items():
        path = EXTRA_DIR / f"{code}.csv"
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip", low_memory=False)
        except Exception:
            continue
        df.columns = [c.strip() for c in df.columns]
        if not {"Home", "Away", "HG", "AG", "Date", "League"}.issubset(df.columns):
            continue

        liga = df["League"].astype("string").str.strip()
        out = _empty(df.index)
        out["div"] = code + "_" + liga.map(league_slug)
        out["league_name"] = tara + " — " + liga
        out["season"] = df["Season"].astype("string") if "Season" in df else ""
        out["date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
        out["home"] = df["Home"].astype("string").str.strip()
        out["away"] = df["Away"].astype("string").str.strip()
        out["hg"] = pd.to_numeric(df["HG"], errors="coerce")
        out["ag"] = pd.to_numeric(df["AG"], errors="coerce")
        # Formatul acesta nu are suturi si nici cote Over/Under.
        out["hst"] = None
        out["ast"] = None
        for target, candidates in ODDS.items():
            col = next((c for c in candidates if c in df.columns), None)
            out[target] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA
            out[target] = pd.to_numeric(out[target], errors="coerce")
        frames.append(out[COLUMNS])
    return frames


def load_all() -> pd.DataFrame:
    frames = _load_core() + _load_extra()
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.dropna(subset=["date", "home", "away", "hg", "ag"])
    all_df = all_df[(all_df["home"] != "") & (all_df["away"] != "")]
    all_df["hg"] = all_df["hg"].astype(int)
    all_df["ag"] = all_df["ag"].astype(int)
    all_df["result"] = 0  # 0 = gazda, 1 = egal, 2 = oaspete
    all_df.loc[all_df["hg"] == all_df["ag"], "result"] = 1
    all_df.loc[all_df["hg"] < all_df["ag"], "result"] = 2
    all_df["over25"] = ((all_df["hg"] + all_df["ag"]) > 2.5).astype(int)
    all_df["btts"] = ((all_df["hg"] >= 1) & (all_df["ag"] >= 1)).astype(int)
    return all_df.sort_values(["date", "div", "home"]).reset_index(drop=True)


if __name__ == "__main__":
    df = load_all()
    print(f"Total meciuri: {len(df):,}")
    print(f"Perioada: {df['date'].min().date()} -> {df['date'].max().date()}")
    print(f"Competitii: {df['div'].nunique()}  |  "
          f"Echipe unice: {pd.concat([df['home'], df['away']]).nunique():,}")
    print(f"Meciuri cu suturi pe poarta: {df['hst'].notna().mean() * 100:.1f}%")
    print("\nCompetitii:")
    rezumat = (df.groupby(["div", "league_name"])
                 .agg(meciuri=("date", "size"), ultima=("date", "max"))
                 .sort_values("meciuri", ascending=False))
    print(rezumat.to_string())

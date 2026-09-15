"""Incarca toate CSV-urile descarcate intr-un singur DataFrame curat."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"

CORE = ["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]

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


def load_all() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("*/*.csv")):
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
        out = pd.DataFrame(index=df.index)
        out["div"] = (df["Div"].astype("string").str.strip() if "Div" in df.columns
                      else path.stem)
        out["season"] = path.parent.name
        out["date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
        out["home"] = df["HomeTeam"].astype("string").str.strip()
        out["away"] = df["AwayTeam"].astype("string").str.strip()
        out["hg"] = pd.to_numeric(df["FTHG"], errors="coerce")
        out["ag"] = pd.to_numeric(df["FTAG"], errors="coerce")
        # suturi pe poarta: proxy gratuit de xG, deja prezent in CSV-uri
        out["hst"] = pd.to_numeric(df["HST"], errors="coerce") if "HST" in df else None
        out["ast"] = pd.to_numeric(df["AST"], errors="coerce") if "AST" in df else None
        for target, candidates in ODDS.items():
            col = next((c for c in candidates if c in df.columns), None)
            out[target] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA
            out[target] = pd.to_numeric(out[target], errors="coerce")
        frames.append(out)

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
    print(f"Ligi: {df['div'].nunique()}  |  Echipe unice: {pd.concat([df['home'], df['away']]).nunique()}")
    print("\nAcoperire cote (% din meciuri):")
    for c in ODDS:
        print(f"  {c:9s} {df[c].notna().mean() * 100:5.1f}%")
    print("\nRezultate:", df["result"].value_counts(normalize=True).sort_index().round(3).to_dict())
    print("Over 2.5:", round(df["over25"].mean(), 3), " BTTS:", round(df["btts"].mean(), 3))

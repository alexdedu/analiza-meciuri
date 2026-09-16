"""Verifica cheia API-Football si raspunde la intrebarile care conteaza.

Nu presupunem nimic despre ce ofera abonamentul: intrebam serverul.
  1. cheia merge? ce plan? cate cereri au ramas?
  2. exista Champions League / Europa League / Conference?
  3. cat istoric au, si ce include acoperirea lor (cote, statistici, formatii)?
  4. exista Superliga Romaniei?

Cotele sunt punctul critic: fara ele pot construi modelul pentru cupele
europene, dar nu pot masura daca e bun -- iar tot proiectul asta se sprijina
pe comparatia cu cotele de inchidere.
"""
from __future__ import annotations

import sys

import requests

from api_config import load_key, rapid_config, request_config

CAUTARI = ["Champions League", "Europa League", "Europa Conference League"]


def get(base: str, headers: dict, path: str, **params):
    r = requests.get(f"{base}/{path}", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        # API-Football raspunde cu 200 chiar si cand refuza cererea.
        raise RuntimeError(body["errors"])
    return body


def detect(key: str) -> tuple[str, dict]:
    """Incearca accesul direct, apoi RapidAPI."""
    for name, cfg in (("direct (api-sports.io)", request_config(key)),
                      ("RapidAPI", rapid_config(key))):
        base, headers = cfg
        try:
            body = get(base, headers, "status")
        except Exception as exc:
            print(f"  {name}: nu raspunde ({str(exc)[:70]})")
            continue
        print(f"  {name}: merge")
        return base, headers, body
    raise SystemExit("Cheia nu functioneaza pe niciuna dintre cele doua cai.")


def main() -> int:
    key = load_key()
    if not key:
        print("Nicio cheie gasita.")
        print("Pune-o in research/.secrets.env, pe o linie:")
        print("  APIFOOTBALL_KEY=cheia_ta")
        return 1
    print(f"Cheie gasita ({len(key)} caractere, se termina in ...{key[-4:]})\n")

    print("Caut calea de acces:")
    base, headers, status = detect(key)

    resp = status["response"]
    sub = resp.get("subscription", {})
    req = resp.get("requests", {})
    print(f"\n  cont:  {resp.get('account', {}).get('email', '?')}")
    print(f"  plan:  {sub.get('plan')}  (activ pana la {sub.get('end')})")
    print(f"  cereri: {req.get('current')} folosite din {req.get('limit_day')} pe zi")

    print("\n" + "=" * 70)
    print("COMPETITII EUROPENE")
    print("=" * 70)
    gasite = 0
    for termen in CAUTARI:
        body = get(base, headers, "leagues", search=termen)
        for item in body["response"]:
            liga = item["league"]
            tara = item["country"]["name"]
            if tara != "World":
                continue  # ne intereseaza cupele UEFA, nu ligile interne omonime
            sezoane = item["seasons"]
            ani = [s["year"] for s in sezoane]
            curent = next((s for s in sezoane if s.get("current")), sezoane[-1])
            cov = curent.get("coverage", {})
            fx = cov.get("fixtures", {})
            gasite += 1
            print(f"\n  {liga['name']}  (id {liga['id']}, {liga['type']})")
            print(f"    sezoane: {len(ani)}  ({min(ani)} - {max(ani)})")
            print(f"    COTE: {'DA' if cov.get('odds') else 'NU'}"
                  f"   predictii: {'da' if cov.get('predictions') else 'nu'}"
                  f"   clasament: {'da' if cov.get('standings') else 'nu'}")
            print(f"    statistici meci: {'da' if fx.get('statistics_fixtures') else 'nu'}"
                  f"   formatii: {'da' if fx.get('lineups') else 'nu'}"
                  f"   evenimente: {'da' if fx.get('events') else 'nu'}")
    if not gasite:
        print("  Nu am gasit nicio competitie UEFA. Planul nu le acopera.")

    print("\n" + "=" * 70)
    print("SUPERLIGA ROMANIEI")
    print("=" * 70)
    body = get(base, headers, "leagues", country="Romania")
    for item in body["response"][:4]:
        liga = item["league"]
        ani = [s["year"] for s in item["seasons"]]
        curent = next((s for s in item["seasons"] if s.get("current")), item["seasons"][-1])
        print(f"  {liga['name']:24s} id {liga['id']:5d}  sezoane {min(ani)}-{max(ani)}"
              f"  cote: {'da' if curent.get('coverage', {}).get('odds') else 'nu'}")

    print(f"\nCereri consumate de verificarea asta: ~{2 + len(CAUTARI)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

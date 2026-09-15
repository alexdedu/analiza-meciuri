# Backtest — rezultate și concluzii

**Date:** 48.935 meciuri, 12 ligi, 2014–2026 (football-data.co.uk, gratuit)
**Predicții evaluate:** 41.959, din care **28.675 pe perioada de test curată** (2019–2026)
**Protocol:** walk-forward, reantrenare săptămânală, fereastră de 3 sezoane.
Niciun meci nu contribuie la propria predicție. `xi` și ponderea goluri/șuturi au fost
alese exclusiv pe 2015–2019 și aplicate neschimbate pe 2019–2026.

> Notă: o primă rulare a folosit din greșeală un subset (32.758 predicții) — un bug în
> loader arunca tăcut fișierele cu BOM. După corectare, concluziile au rămas identice,
> iar semnificația statistică a crescut.

## 1. Modelul vs piață (1X2)

| Model | log-loss | Brier | Acuratețe |
|---|---|---|---|
| Dixon-Coles, doar goluri | 0.99858 | 0.5941 | 51.31% |
| **Dixon-Coles, goluri + șuturi pe poartă** | **0.99155** | **0.5906** | **51.75%** |
| Cote de închidere (piața) | **0.96980** | **0.5768** | **53.12%** |
| Referință: „mereu gazda" | 1.07373 | 0.6499 | 43.26% |

Modelul bate net referința naivă, dar **pierde consistent în fața pieței**.
Șuturile pe poartă (proxy gratuit de xG) au închis ~24% din distanță.

## 2. Testul decisiv: adaugă modelul informație peste piață?

Pool logaritmic model × piață, pondere căutată direct pe test:

| Pondere model | 0% | 5% | 10% | 25% | 40% |
|---|---|---|---|---|---|
| log-loss | **0.96980** | 0.97012 | 0.97052 | 0.97220 | 0.97463 |

**Optimul e 0%.** Orice cantitate de model înrăutățește predicția pieței.
Modelul nu conține informație pe care cotele să nu o aibă deja.

## 3. ROI (miză fixă, cea mai bună cotă de pe piață)

| Prag edge | Pariuri | ROI | t |
|---|---|---|---|
| >0% | 43.101 | −3.71% | −4.00 |
| >5% | 32.807 | −4.97% | −4.43 |
| >10% | 25.183 | −6.14% | −4.57 |
| >20% | 15.137 | −7.67% | −4.00 |

Negativ peste tot, **puternic semnificativ statistic**. Over/Under 2.5: identic, −2.5% … −4.3%.
Pragurile mari înrăutățesc lucrurile: **acolo unde modelul crede că are cel mai mare
avantaj, se înșală cel mai tare.** E semnătura unui model care nu găsește valoare.

## 4. Strategia alternativă: cotă bună vs linia „ascuțită" (Pinnacle)

Fără niciun model, doar comparând cea mai bună cotă de pe piață cu prețul corect Pinnacle:
ROI +1.3% … +6.0%, dar **t ≈ +1.2 — nesemnificativ**. Defalcarea pe ligi (Bundesliga +11%,
Portugalia −11%) e zgomot, nu structură. Plus: „cea mai bună cotă" înseamnă best-of-40-case
la închidere — un cont obișnuit nu obține prețul ăla.

## 5. Ce a ieșit foarte bine: calibrarea

| Interval prezis | n | Prezis | Realizat | Eroare |
|---|---|---|---|---|
| 0–10% | 2.060 | 0.071 | 0.072 | −0.001 |
| 20–30% | 34.490 | 0.255 | 0.255 | +0.000 |
| 40–50% | 10.798 | 0.447 | 0.445 | +0.002 |
| 60–70% | 3.637 | 0.644 | 0.685 | −0.040 |
| 80–90% | 534 | 0.837 | 0.861 | −0.024 |

**Eroare medie de calibrare (ECE): 0.0070.** Când modelul spune 30%, se întâmplă în 25.5%…
mai exact, în banda 20–30% media prezisă 0.255 vs realizat 0.255. Over 2.5: 0.506 prezis vs
0.524 real. BTTS: 0.514 vs 0.531. Singura zonă slabă e peste 90% (doar 60 de cazuri).

## Concluzie

Modelul **nu poate fi folosit ca să bată casele de pariuri** — demonstrat, nu presupus.
Poate fi folosit ca **motor de probabilități onest și bine calibrat**: îți spune corect
cât de probabil e fiecare rezultat, ca punct de plecare pentru propria analiză.

## Cum se poate îmbunătăți (gratuit)

1. **xG real** — football-data.co.uk a început să publice coloanele `HxG`/`AxG` din sezonul
   2026/27. Deocamdată prea puține meciuri pentru antrenare, dar peste 1–2 sezoane devine
   cel mai serios upgrade disponibil, fără scraping și fără costuri.
2. Absențe/accidentări (necesită API-Football, 19 $/lună)
3. Zile de odihnă între meciuri, meciuri europene la mijloc de săptămână
4. Importanța meciului la final de sezon

Distanța de recuperat în log-loss e 0.022. Niciuna dintre îmbunătățiri nu garantează
depășirea pieței.

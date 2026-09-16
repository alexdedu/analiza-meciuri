# Backtest — rezultate și concluzii

**Date:** 112.119 meciuri, 30 de competiții din 28 de țări, 2012–2026
(football-data.co.uk, gratuit)
**Predicții evaluate:** 97.168, din care **60.539 pe perioada de test curată** (2019–2026)
**Protocol:** walk-forward, reantrenare săptămânală, fereastră de 3 sezoane.
Niciun meci nu contribuie la propria predicție. `xi` și ponderea goluri/șuturi au fost
alese exclusiv pe 2015–2019 și aplicate neschimbate pe 2019–2026.

> Notă: datele despre șuturi pe poartă există doar pentru cele 12 competiții „de bază"
> (39,8% din meciuri). Pentru restul — România, Polonia, Brazilia, MLS etc. — modelul
> funcționează doar pe goluri.

## 1. Modelul vs piață (1X2)

| Model | log-loss | Brier | Acuratețe |
|---|---|---|---|
| Dixon-Coles, doar goluri | 1.01981 | 0.6086 | 49.76% |
| **Dixon-Coles, goluri + șuturi pe poartă** | **1.01648** | **0.6069** | **49.97%** |
| Cote de închidere (piața) | **0.98846** | **0.5897** | **51.49%** |

Modelul **pierde consistent în fața pieței**.

Cifrele sunt mai slabe decât pe setul inițial de 12 ligi (era 0.99155 față de 0.96980),
și asta e de așteptat: competițiile adăugate sunt mai imprevizibile, iar pentru ele
lipsesc datele despre șuturi. Concluzia calitativă nu se schimbă cu nimic.

## 2. Testul decisiv: adaugă modelul informație peste piață?

Pool logaritmic model × piață, pondere căutată direct pe test:

| Pondere model | 0% | 5% | 10% | 25% | 40% |
|---|---|---|---|---|---|
| log-loss | **0.98846** | 0.98877 | 0.98920 | 0.99124 | 0.99432 |

**Optimul e 0%.** Orice cantitate de model înrăutățește predicția pieței.

## 3. ROI (miză fixă, cea mai bună cotă de pe piață)

| Prag edge | Pariuri | ROI | t |
|---|---|---|---|
| >0% | 87.186 | −3.84% | −6.30 |
| >5% | 66.972 | −4.77% | −6.60 |
| >10% | 51.264 | −5.73% | −6.66 |
| >20% | 30.443 | −6.41% | −5.26 |

Negativ peste tot. Cu de două ori mai multe date, semnificația statistică a crescut de la
t ≈ −4 la **t ≈ −6.6**: nu mai e loc de îndoială că e sistematic, nu ghinion.

Pragurile mari înrăutățesc lucrurile: **acolo unde modelul crede că are cel mai mare
avantaj, se înșală cel mai tare.**

## 4. Ce a ieșit foarte bine: calibrarea

| Interval prezis | n | Prezis | Realizat | Eroare |
|---|---|---|---|---|
| 10–20% | 21.528 | 0.160 | 0.171 | −0.011 |
| 20–30% | 70.642 | 0.254 | 0.259 | −0.005 |
| 30–40% | 35.817 | 0.344 | 0.336 | +0.008 |
| 40–50% | 22.631 | 0.447 | 0.439 | +0.007 |
| 50–60% | 14.561 | 0.545 | 0.537 | +0.008 |
| 60–70% | 7.819 | 0.644 | 0.639 | +0.005 |
| 80–90% | 1.014 | 0.838 | 0.805 | +0.033 |

**Eroare medie de calibrare (ECE): 0.0080.** Când modelul spune 30%, se întâmplă în ~30%
din cazuri. Peste 90% prezis rămâne zona slabă, dar acolo sunt doar 145 de cazuri.

Over 2.5: 0.495 prezis vs 0.514 real. BTTS: 0.505 vs 0.532.

## Concluzie

Modelul **nu poate fi folosit ca să bată casele de pariuri** — demonstrat pe 60.539 de
meciuri, nu presupus. Poate fi folosit ca **motor de probabilități onest și bine
calibrat**: îți spune corect cât de probabil e fiecare rezultat.

## Ce nu se poate face gratuit

**Cupele europene (Champions League, Europa League) nu există în nicio sursă gratuită.**
Verificat: football-data.co.uk are doar campionate interne; API-ul de meciuri al Club Elo
a fost dezactivat; openfootball are sezonul curent, dar tot doar campionate interne.

Chiar cu meciurile la îndemână, ar mai fi o problemă de fond: modelul e antrenat separat
pe fiecare competiție, iar forțele sunt normalizate în interiorul ei. O echipă de mijlocul
clasamentului din Olanda și una din Spania au amândouă atac ≈ 0. Pentru meciuri între ligi
diferite ar fi nevoie de un rating comparabil între campionate, iar date istorice din
cupele europene, pe care să-l antrenez, nu avem deloc.

## Cum se poate îmbunătăți

1. **xG real** — football-data.co.uk publică `HxG`/`AxG` din sezonul 2026/27. Prea puține
   meciuri acum, dar peste 1–2 sezoane devine cel mai serios upgrade gratuit.
2. Cupe europene + absențe + orizont de 7 zile — necesită API-Football, ~19 $/lună.
3. Zile de odihnă între meciuri, meciuri europene la mijloc de săptămână.
4. Importanța meciului la final de sezon.

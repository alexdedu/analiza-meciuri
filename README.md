# Analiza meciuri de fotbal

Aplicație Android care calculează probabilități pentru meciuri de fotbal (1X2,
Over/Under 2.5, Ambele înscriu), pe baza istoricului și a formei echipelor.

**Cost de operare: 0 €.** Fără chei API, fără server, fără abonamente.

---

## Ce face și ce nu face

**Face:** probabilități bine calibrate pentru **30 de competiții din 28 de țări**,
inclusiv Superliga României, calculate din 112.119 meciuri istorice. Eroarea medie de
calibrare este 0.0080 — când modelul spune 30%, se întâmplă în ~30% din cazuri.

**Nu face:** nu bate casele de pariuri. Testat pe 60.539 de meciuri din perioada
2019–2026, modelul are log-loss 1.0165 față de 0.9885 al cotelor de închidere, iar
pariurile alese după el au dat randament **negativ** (−3.8%, t = −6.3).

**Nu are:** Champions League și Europa League. Nu există în nicio sursă gratuită, iar
modelul oricum nu poate compara echipe din campionate diferite. Detalii în CONCLUZII.md.

Cifrele complete și metodologia sunt în [research/CONCLUZII.md](research/CONCLUZII.md).
Aceleași cifre sunt afișate și în aplicație, pe ecranul „Despre model".

---

## Structura

```
research/          Partea de date și modelare (Python)
  download_data.py   Descarcă CSV-urile istorice de la football-data.co.uk
  data_loader.py     Le încarcă și le curăță într-un singur tabel
  dixon_coles.py     Modelul Dixon-Coles cu gradient analitic
  backtest.py        Validare walk-forward, model pe goluri
  backtest_xg.py     Idem, model dublu goluri + șuturi pe poartă
  evaluate.py        Model vs piață, ROI, calibrare
  evaluate_xg.py     Alege ponderea goluri/șuturi și măsoară pe test
  test_sharp_line.py Testează strategia „cotă bună vs linia Pinnacle"
  predict.py         Pipeline de producție → app/assets/predictions.json

app/               Aplicația Flutter
  lib/               Cod sursă
  lib/config.dart    Adresa de unde se descarca predictiile (vezi mai jos)
  test/              30 de teste
  assets/predictions.json
  assets/icon/       Iconita generata

tools/make_icon.py Genereaza iconita aplicatiei
```

Aspect: albastru-noapte cu accent indigo (`app/lib/theme.dart`).
Iconița: inel împărțit în trei arce, cu lungimile egale cu frecvențele reale din date
(44,1% gazdă / 25,2% egal / 30,6% oaspete), și o minge stilizată în centru.
Regenerare: `python tools/make_icon.py` apoi `dart run flutter_launcher_icons` in `app/`.

## Cum funcționează modelul

Dixon-Coles: fiecare echipă are o forță de atac și una de apărare, estimate prin
maximum likelihood din meciurile anterioare. Golurile urmează o distribuție Poisson,
cu o corecție pentru scorurile mici, unde Poisson simplu subestimează egalurile.

Peste asta, un al doilea model estimează aceleași forțe din **șuturile pe poartă**.
Sunt de ~10 ori mai numeroase decât golurile, deci măsoară mai stabil cât de bine
joacă o echipă — un xG „de om sărac", dar gratuit. Cele două estimări se combină în
părți egale (pondere aleasă pe perioada de validare, nu pe cea de test).

Meciurile vechi contează mai puțin: înjumătățirea importanței la ~230 de zile.

## Cât de departe vede aplicația

Feed-ul de meciuri viitoare al football-data.co.uk publică doar cu **~3 zile înainte**.
Marțea nu conține încă etapa de weekend; aceasta apare de obicei joi. Nu e o limitare a
aplicației, ci a sursei. Cu actualizare zilnică, meciurile intră singure de îndată ce
sunt publicate.

## Cum rămâne aplicația la zi

Sunt două moduri, iar al doilea e cel care scapă de reinstalări.

**A. Doar local.** `update.bat` regenerează `predictions.json`, dar fișierul e inclus
în APK — deci trebuie reconstruită și reinstalată aplicația ca să vezi meciurile noi.

**B. Prin internet (configurat).** Adresa e deja setată în
[`app/lib/config.dart`](app/lib/config.dart), iar repo-ul local e pregătit de trimis.
Pașii rămași sunt în **[GITHUB.md](GITHUB.md)**.

Odată pornit: workflow-ul zilnic rescrie fișierul pe GitHub la 09:30, iar telefonul îl
ia singur la fiecare pornire sau când tragi lista în jos. Fără internet, folosește
ultima descărcare; dacă nici aia nu există, fișierul din aplicație. Bannerul de sus
arată mereu cât de vechi sunt datele și de unde vin.

## Instalare și rulare

**Aplicația.** APK-ul gata construit:
`app/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk` (17.3 MB, pentru orice
telefon Android modern).

**Reîmprospătarea predicțiilor.** Dublu-clic pe `update.bat`, sau:

```bash
cd research
.venv/Scripts/python.exe predict.py
```

Durează ~15 secunde. Descarcă rezultatele noi, reantrenează modelul și rescrie
`app/assets/predictions.json`. Reconstruiește apoi aplicația.

**Automat, zilnic.** `.github/workflows/daily.yml` face asta singur pe GitHub Actions,
gratuit, dacă pui proiectul pe GitHub.

**Refacerea backtest-ului de la zero:**

```bash
cd research
.venv/Scripts/python.exe download_data.py
.venv/Scripts/python.exe backtest_xg.py
.venv/Scripts/python.exe evaluate_xg.py
```

## Sursele de date

Totul de la [football-data.co.uk](https://www.football-data.co.uk/) — CSV-uri gratuite,
fără cont, fără limită de cereri. Sursa are două formate:

- **12 competiții „de bază"** (Anglia, Spania, Italia, Germania, Franța, Olanda, Portugalia,
  Belgia, Turcia, Grecia, Scoția): rezultate, statistici de meci **cu șuturi pe poartă** și
  cote pentru 1X2 și Over/Under, din 2014.
- **18 competiții suplimentare** (România, Polonia, Danemarca, Norvegia, Suedia, Finlanda,
  Austria, Elveția, Irlanda, Rusia, Brazilia, Argentina, Mexic, SUA, Japonia, China): doar
  rezultate și cote 1X2, din 2012. Fără șuturi, deci modelul merge pe varianta doar-goluri.

Meciurile viitoare vin din `fixtures.csv` de pe același site, care folosește exact
aceleași nume de echipe — deci nu e nevoie de nicio potrivire aproximativă de nume.

## Ce ar putea îmbunătăți modelul

1. **xG real** — football-data.co.uk a început să publice coloanele `HxG`/`AxG` din
   sezonul 2026/27. Deocamdată prea puține meciuri pentru antrenare, dar peste 1–2
   sezoane devine cel mai serios upgrade disponibil, tot gratuit.
2. Absențe și echipe probabile — necesită API-Football, ~19 $/lună.
3. Zile de odihnă între meciuri, meciuri europene la mijloc de săptămână.
4. Importanța meciului la final de sezon.

Distanța de recuperat față de piață este 0.022 în log-loss. Niciuna dintre îmbunătățiri
nu garantează depășirea ei.

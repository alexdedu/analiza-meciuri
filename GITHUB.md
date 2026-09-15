# Punerea pe GitHub — 4 pași

Repo-ul local e deja pregătit: inițializat, cu primul commit făcut și cu adresa
`https://github.com/alexdedu/analiza-meciuri` setată ca destinație. Aplicația e deja
construită ca să citească predicțiile de acolo.

Mai rămân patru lucruri, pe care trebuie să le faci tu — la push e nevoie de
autentificarea ta.

---

## 1. Creează repo-ul gol pe GitHub

Intră pe **https://github.com/new** și completează:

| Câmp | Valoare |
|---|---|
| Repository name | `analiza-meciuri` |
| Vizibilitate | **Public** |
| Add a README / .gitignore / license | **lasă nebifate** |

**De ce public:** adresa `raw.githubusercontent.com` de unde își ia telefonul
predicțiile funcționează fără autentificare doar pentru repo-uri publice. La unul
privat ar trebui să bag un token în aplicație, ceea ce nu e o idee bună. În plus,
GitHub Actions are minute nelimitate gratuite doar pe repo-uri publice.

Repo-ul conține doar cod și predicții. Nicio parolă, nicio cheie, niciun fișier personal.

## 2. Trimite codul

```bash
cd C:\Users\Alex\Desktop\Metin\football-predictor && git push -u origin main
```

Git for Windows deschide singur o fereastră de browser pentru autentificare la GitHub.
Nu-ți trebuie token scris de mână.

## 3. Dă-i voie robotului să scrie în repo

Pe pagina repo-ului: **Settings → Actions → General**, derulează la
**Workflow permissions**, alege **Read and write permissions**, apoi **Save**.

Fără asta, actualizarea zilnică rulează dar nu poate salva rezultatul.

## 4. Pornește prima actualizare manual

Pe pagina repo-ului: tab-ul **Actions** → în stânga **Actualizare predicții** →
butonul **Run workflow** → **Run workflow**.

Durează ~2 minute. Când termină cu bifă verde, deschide aplicația pe telefon: bannerul
de sus trebuie să scrie **„actualizat acum · actualizat acum"**, nu „din aplicație".

---

## De aici încolo nu mai faci nimic

- În fiecare zi la **09:30 ora României**, GitHub rulează singur modelul și rescrie predicțiile.
- Aplicația le descarcă la fiecare pornire. Poți forța oricând tragând lista în jos.
- Fără internet, folosește ultima descărcare. Nu rămâi niciodată cu ecranul gol.

Nu mai trebuie să rulezi `update.bat`, nu mai trebuie să reconstruiești aplicația și nu
mai trebuie să-mi scrii. Reconstruiești APK-ul doar dacă schimbăm ceva în aplicație.

## Două lucruri de știut

**Meciurile apar cu ~3 zile înainte.** Sursa (football-data.co.uk) nu publică etapa de
weekend mai devreme de joi. Cu actualizarea zilnică pornită, intră singure când apar.

**Dacă nu atingi repo-ul 60 de zile**, GitHub oprește automat sarcinile programate și îți
trimite un email. Commit-urile zilnice ale robotului ar trebui să țină repo-ul activ, dar
dacă primești mailul acela, intră în tab-ul Actions și apasă **Enable workflow**.

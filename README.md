# kibo-landing

Landing page dei viaggi di gruppo **Kibo Tours**, pubblicate su GitHub Pages
(`go.kibotours.com`). Derivato dal sistema landing KiRun (`kirun-landing`).

⚠️ **Repository PUBBLICO**: mai committare dati personali, costi fornitore, nomi di
fornitori interni o credenziali. I dati commerciali (quote, acconti, penali) sono quelli
destinati al cliente.

## Come nasce una pagina

```
Airtable "Kibo — Partenze di Gruppo" (Viaggi)   ← dati parametrici: date, quote, acconto, posti
contenuti/<slug>.json (questo repo)             ← contenuto editoriale: intro, itinerario, incluso
        ↓
n8n "Kibo — Landing Builder" (o scripts/render.py in locale)
        ↓
viaggi/<slug>/index.html  →  GitHub Pages  →  https://go.kibotours.com/viaggi/<slug>/
        ↓
CTA "Prenota" → form Tally → prenotazione e acconto
```

- **Airtable è la fonte di verità dei numeri**: quote, acconto, penali, posti residui.
- **Il contenuto editoriale vive qui**, in `contenuti/<slug>.json`, versionato in git.
  Nasce dal programma Word convertito in sessione con Claude. Nessun prezzo nei campi
  editoriali: i prezzi arrivano solo da Airtable.
- Stati: `anteprima/<slug>/` per le pagine da verificare, `viaggi/<slug>/` per le pubblicate.

## Struttura

| Percorso | Cosa |
| --- | --- |
| `templates/viaggio.html` | Template unico delle landing (segnaposto `{{...}}`, blocchi `<!--IF:...-->`) |
| `assets/kibo.css` | Stile condiviso: un ritocco qui vale per tutte le pagine |
| `assets/brand/` | Loghi ufficiali Kibo (dal sito; sostituire con i sorgenti hi-res quando disponibili) |
| `assets/hero/<slug>.jpg` | Foto hero per pagina (fallback: gradiente brand) |
| `contenuti/<slug>.json` | Contenuto editoriale per viaggio |
| `scripts/render.py` | Renderer di riferimento — la stessa logica del Code node n8n si sviluppa e testa qui |
| `scripts/render_index.py` | Genera `index.html`, la home indice: legge le pagine già in `viaggi/` e le elenca. **Va rilanciato dopo ogni pubblicazione** |
| `index.html` | Home di go.kibotours.com — GENERATA, non si modifica a mano |
| `scripts/sample-data/` | Dati Airtable normalizzati per i test locali |

## Render locale

```
python3 scripts/render.py scripts/sample-data/nam-2027-06.json \
        contenuti/namibia-2027-06.json anteprima/namibia-2027-06/index.html [--soldout]
```

Fail-loud: un segnaposto senza valore fa fallire il render, mai una pagina mezza vuota.

## Documentazione di progetto

Il progetto è documentato in `KIBO/progetti/landing/` del repository privato
`robertonarzisi/Kibo-Flyness-Agenti`.

## Tracciamento (dal 21/10/2026)

Ogni pagina carica `assets/consenso.js`: un banner cookie che, **solo dopo «Accetta»**, avvia Google Analytics 4
(`G-R4MME0PVZR`, la proprietà di www.kibotours.com: in GA4 le landing si distinguono per host `go.kibotours.com`)
e il Meta Pixel `501692673520339` (lo stesso del sito). Eventi: `page_view`/`PageView`, `view_item`/`ViewContent`
sulle pagine viaggio, `select_content`/`ClickPrenota` sul bottone Prenota. Il modulo di prenotazione è su Tally:
il lead vero non si conta qui. La scelta resta in `localStorage` per 365 giorni e si cambia da `/cookie/`
(informativa cookie). Il tag sta in `templates/viaggio.html` e `templates/indice.html` (il Landing Builder n8n li
legge da GitHub, quindi vale anche per le pagine future) ed è stato inserito nelle pagine già pubblicate.

## Indicizzazione (dal 22/10/2026, decisione di Roberto)

Le landing pubblicate in `viaggi/` sono indicizzabili: `robots.txt` permette tutto tranne `/anteprima/` e dichiara
`sitemap.xml` (generata da `scripts/sitemap.py`, da rilanciare dopo ogni pubblicazione insieme a `render_index.py`).
Ogni landing ha `<link rel="canonical">` su se stessa (template `viaggio.html`); la home indice non è più noindex e ha il
canonical sull'hub «Partenze di gruppo» di kibotours.com (`/partenze-di-gruppo/`, pagina 6491), che elenca le stesse
partenze e le collega. Le anteprime restano noindex (renderer: `landing_status != pubblicata`; il noindex fisso nel Code node
del builder vale solo per le pagine «ritirate»). Search Console: proprietà `https://go.kibotours.com/` da verificare con
il tag HTML (Roberto) e sitemap da inviare.

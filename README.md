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

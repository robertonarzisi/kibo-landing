#!/usr/bin/env python3
"""Genera la home indice di go.kibotours.com a partire dalle pagine gia pubblicate.

    python3 scripts/render_index.py

Legge le pagine in viaggi/<slug>/index.html — SOLO quelle pubblicate, mai le anteprima —
e ne estrae titolo, strillo, date, durata e quota dal markup che il template gia produce
(.fatto > .etichetta/.valore). Nessuna chiamata Airtable, nessuna dipendenza dal Landing
Builder: la home si rigenera da sola dopo ogni pubblicazione e non aggiunge un secondo
posto in cui i numeri possono divergere.

Ordina per data di partenza (dal campo "Date" della pagina), le sold out in fondo.
Se non c'e' nessun viaggio pubblicato produce comunque una home dignitosa che rimanda a
kibotours.com, invece del 404 di GitHub Pages.
"""

import html
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "index.html"

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def testo(frammento):
    """Ripulisce un frammento di HTML riducendolo al suo testo."""
    return html.unescape(re.sub(r"<[^>]+>", "", frammento)).strip()


def fatti(pagina):
    """Estrae le coppie etichetta -> valore dalla fascia "in breve" della pagina."""
    trovati = {}
    for blocco in re.findall(r'<div class="fatto[^"]*">(.*?)</div>', pagina, re.S):
        et = re.search(r'<span class="etichetta">(.*?)</span>', blocco, re.S)
        va = re.search(r'<span class="valore">(.*?)</span>', blocco, re.S)
        if et and va:
            trovati[testo(et.group(1))] = testo(va.group(1))
    return trovati


def ordinamento(date_label):
    """Chiave di ordinamento dal testo delle date, es. "5-22 marzo 2027" -> (2027, 3, 5).

    Il formato lo produce trip_dates() in render.py. Se cambia, il peggio che succede e'
    che l'ordine diventa alfabetico: la home resta valida, non si rompe niente.
    """
    if not date_label:
        return (9999, 99, 99)
    testo_basso = date_label.lower()
    anno = re.search(r"\b(20\d{2})\b", date_label)
    # Il mese va preso nell'ordine del TESTO, non del dizionario: su una partenza a
    # cavallo d'anno ("28 dicembre 2026 - 8 gennaio 2027") conta dicembre, non gennaio.
    presenti = [(testo_basso.index(nome), n) for nome, n in MESI.items() if nome in testo_basso]
    mese = min(presenti)[1] if presenti else 99
    giorno = re.match(r"\s*(\d{1,2})", date_label)
    return (
        int(anno.group(1)) if anno else 9999,
        mese,
        int(giorno.group(1)) if giorno else 99,
    )


def raccogli():
    viaggi = []
    for indice in sorted((RADICE / "viaggi").glob("*/index.html")):
        pagina = indice.read_text(encoding="utf-8")
        slug = indice.parent.name
        titolo = re.search(r"<h1>(.*?)</h1>", pagina, re.S)
        strillo = re.search(r'<p class="strillo">(.*?)</p>', pagina, re.S)
        f = fatti(pagina)
        viaggi.append({
            "slug": slug,
            "titolo": testo(titolo.group(1)) if titolo else slug,
            "strillo": testo(strillo.group(1)) if strillo else "",
            "date": f.get("Date", ""),
            "durata": f.get("Durata", ""),
            "quota": f.get("Quota a persona", ""),
            "sold_out": 'class="badge-soldout"' in pagina,
        })
    viaggi.sort(key=lambda v: (v["sold_out"], ordinamento(v["date"])))
    return viaggi


def scheda(v):
    e = html.escape
    righe = []
    for etichetta, valore in (("Date", v["date"]), ("Durata", v["durata"])):
        if valore:
            righe.append(
                f'<div class="fatto"><span class="etichetta">{etichetta}</span>'
                f'<span class="valore">{e(valore)}</span></div>'
            )
    quota = (
        f'<div class="fatto quota"><span class="etichetta">Quota a persona</span>'
        f'<span class="valore">{e(v["quota"])}</span></div>' if v["quota"] else ""
    )
    badge = '<span class="badge-soldout">Sold out</span>' if v["sold_out"] else ""
    strillo = f'<p class="scheda-strillo">{e(v["strillo"])}</p>' if v["strillo"] else ""
    return f"""    <a class="scheda-viaggio" href="/viaggi/{e(v['slug'])}/">
      <div class="scheda-foto" style="--foto: url('/assets/hero/{e(v['slug'])}.jpg')">{badge}</div>
      <div class="scheda-corpo">
        <h2>{e(v['titolo'])}</h2>
        {strillo}
        <div class="scheda-fatti">{''.join(righe)}{quota}</div>
        <span class="scheda-vai">Scopri il viaggio</span>
      </div>
    </a>"""


def render(viaggi):
    if viaggi:
        corpo = (
            '  <div class="griglia-viaggi">\n'
            + "\n".join(scheda(v) for v in viaggi)
            + "\n  </div>"
        )
        occhiello = (
            "Una partenza in programma"
            if len(viaggi) == 1
            else f"{len(viaggi)} partenze in programma"
        )
    else:
        corpo = """  <div class="nessun-viaggio">
    <p>Le prossime partenze di gruppo sono in preparazione.</p>
    <a class="cta" href="https://www.kibotours.com">Vai a kibotours.com</a>
  </div>"""
        occhiello = "Partenze in preparazione"

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Come le landing: fase 1 serve la conversione da email e social, non l'organico. -->
<meta name="robots" content="noindex,nofollow">
<title>Partenze di gruppo &middot; Kibo</title>
<meta name="description" content="Le partenze di gruppo Kibo Tours in programma: date, durata e quote.">
<link rel="icon" type="image/png" href="/assets/brand/logo-kibo-colore.png">
<link rel="stylesheet" href="/assets/kibo.css">
</head>
<body class="pagina-indice">

<header class="testata-indice">
  <div class="marchio">
    <img class="logo-hero" src="/assets/brand/logo-kibo-bianco.png" alt="Kibo">
    <span class="sotto-marchio">Where dreams come tours</span>
  </div>
  <div class="hero-testo">
    <span class="eyebrow">{occhiello}</span>
    <h1>Partenze di gruppo</h1>
    <p class="strillo">Piccoli gruppi accompagnati, voli inclusi e un itinerario
    costruito nel dettaglio. Scegli la partenza e scopri il programma completo.</p>
  </div>
</header>

<main class="indice">
{corpo}
</main>

<footer>
  <div class="footer-inner">
    <img class="logo-footer" src="/assets/brand/logo-kibo-bianco.png" alt="Kibo">
    <span>Kibo Tours &middot; <a href="https://www.kibotours.com">kibotours.com</a></span>
    <span>Quote e disponibilit&agrave; sono indicative: fanno fede quelle della pagina del
    singolo viaggio e il contratto inviato prima della conferma.</span>
  </div>
</footer>

</body>
</html>
"""


def main():
    viaggi = raccogli()
    USCITA.write_text(render(viaggi), encoding="utf-8")
    if not viaggi:
        print(
            "WARNING: nessuna pagina in viaggi/ — home generata con lo stato "
            "'partenze in preparazione'",
            file=sys.stderr,
        )
    for v in viaggi:
        mancanti = [k for k in ("date", "durata", "quota") if not v[k]]
        if mancanti:
            print(f"WARNING: {v['slug']} senza {', '.join(mancanti)}", file=sys.stderr)
    print(f"OK: {USCITA} ({len(viaggi)} viaggi)")


if __name__ == "__main__":
    main()

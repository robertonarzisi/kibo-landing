#!/usr/bin/env python3
"""Renderer di riferimento della home indice di go.kibotours.com.

    python3 scripts/render_index.py

**In produzione la home la rigenera il Landing Builder n8n** ("Indice" in coda al
workflow), non questo script: qui si sviluppa e si testa la logica, come render.py sta al
nodo "Renderizza Landing". Questo script serve per provare il layout in locale e per
rimettere a posto la home a mano se il builder e' fermo.

ATTENZIONE, stesso patto di render.py: `templates/indice.html` e il nodo "Renderizza
Indice" condividono il contratto dei segnaposto. Un `{{nuovo}}` nel template richiede la
chiave corrispondente in ENTRAMBI i renderer, altrimenti il build fallisce (fail-loud).

Differenza di input, deliberata: qui i viaggi si leggono dalle pagine gia' in `viaggi/`
(nessuna credenziale Airtable in locale), nel builder si leggono da Airtable filtrando
`landing_status='pubblicata'` e `landing_url` non vuoto. L'HTML prodotto e' lo stesso.
"""

import html
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "index.html"
TEMPLATE = RADICE / "templates" / "indice.html"

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
    """Legge i viaggi dalle pagine PUBBLICATE. Le anteprima non entrano mai in home.

    ATTENZIONE: in `viaggi/` non ci sono solo i viaggi in vendita. Un viaggio portato a
    `ritirata` lascia li' la sua pagina di cortesia ("Questa pagina non e' piu' attiva"),
    che non deve comparire in home. La si riconosce dal fatto che NON ha la fascia
    "in breve" — controllo strutturale, non sul testo del titolo.
    Nel builder n8n il filtro e' piu' forte: lo fa Airtable con landing_status.
    """
    viaggi = []
    for indice in sorted((RADICE / "viaggi").glob("*/index.html")):
        pagina = indice.read_text(encoding="utf-8")
        if 'class="in-breve"' not in pagina:
            continue
        titolo = re.search(r"<h1>(.*?)</h1>", pagina, re.S)
        strillo = re.search(r'<p class="strillo">(.*?)</p>', pagina, re.S)
        f = fatti(pagina)
        viaggi.append({
            "slug": indice.parent.name,
            "titolo": testo(titolo.group(1)) if titolo else indice.parent.name,
            "strillo": testo(strillo.group(1)) if strillo else "",
            "date": f.get("Date", ""),
            "durata": f.get("Durata", ""),
            "quota": f.get("Quota a persona", ""),
            "sold_out": 'class="badge-soldout"' in pagina,
        })
    return ordina(viaggi)


def ordina(viaggi):
    """Per data di partenza, sold out in fondo. Stessa regola nel nodo n8n."""
    return sorted(viaggi, key=lambda v: (v["sold_out"], ordinamento(v["date"])))


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


def corpo_e_occhiello(viaggi):
    """Le due parti variabili della home. Stessa logica nel nodo "Renderizza Indice"."""
    if not viaggi:
        # Con zero viaggi pubblicati la home resta dignitosa invece del 404 di Pages.
        return ("""  <div class="nessun-viaggio">
    <p>Le prossime partenze di gruppo sono in preparazione.</p>
    <a class="cta" href="https://www.kibotours.com">Vai a kibotours.com</a>
  </div>""", "Partenze in preparazione")
    corpo = ('  <div class="griglia-viaggi">\n'
             + "\n".join(scheda(v) for v in viaggi)
             + "\n  </div>")
    occhiello = ("Una partenza in programma" if len(viaggi) == 1
                 else f"{len(viaggi)} partenze in programma")
    return corpo, occhiello


def render(viaggi, template):
    corpo, occhiello = corpo_e_occhiello(viaggi)
    out = template.replace("{{occhiello}}", occhiello).replace("{{schede_html}}", corpo)
    residui = re.findall(r"{{\w+}}", out)
    if residui:
        raise SystemExit(f"segnaposto non sostituiti: {residui}")
    return out


def main():
    viaggi = raccogli()
    USCITA.write_text(render(viaggi, TEMPLATE.read_text(encoding="utf-8")), encoding="utf-8")
    if not viaggi:
        print("WARNING: nessuna pagina in viaggi/ — home con lo stato "
              "'partenze in preparazione'", file=sys.stderr)
    for v in viaggi:
        mancanti = [k for k in ("date", "durata", "quota") if not v[k]]
        if mancanti:
            print(f"WARNING: {v['slug']} senza {', '.join(mancanti)}", file=sys.stderr)
    print(f"OK: {USCITA} ({len(viaggi)} viaggi)")


if __name__ == "__main__":
    main()

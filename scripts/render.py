#!/usr/bin/env python3
"""Renderer di riferimento delle landing viaggio Kibo.

La STESSA logica va portata nel Code node del workflow n8n "Kibo — Landing Builder":
questo file esiste per poterla sviluppare, testare e rivedere fuori da n8n.

Uso:
    python3 scripts/render.py <dati-viaggio.json> <contenuto.json> <output.html> [--soldout]

Due ingressi, per scelta di architettura:
  - <dati-viaggio.json>: i dati PARAMETRICI del record Viaggi di Airtable, normalizzati
    (vedi scripts/sample-data/). Airtable resta la fonte di verità di date, quote,
    acconto, posti e penali.
  - <contenuto.json>: il contenuto EDITORIALE (intro, itinerario, incluso/non incluso),
    che vive in contenuti/<slug>.json in questo repository, versionato in git.
    Nasce dal programma Word convertito in sessione; non sta in Airtable.

Regola non negoziabile: nessun prezzo nei campi editoriali — i prezzi vivono solo
nei dati parametrici. Il renderer avvisa se ne trova.
"""

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

RE_PREZZO_NEL_TESTO = re.compile(r"€|EUR\b|\b\d+[.,]?\d*\s*euro\b", re.IGNORECASE)


def esc(s):
    return html.escape(str(s or ""), quote=True)


def euro(n):
    """Formato italiano: € 3.490 oppure € 390,50."""
    if n == int(n):
        intero = f"{int(n):,}".replace(",", ".")
        return f"€ {intero}"
    return "€ " + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def data_it(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} {MESI[m]} {y}"


def trip_dates(inizio, fine):
    yi, mi, di = (int(x) for x in inizio.split("-"))
    yf, mf, df = (int(x) for x in fine.split("-"))
    if (yi, mi) == (yf, mf):
        return f"{di}–{df} {MESI[mf]} {yf}"
    if yi == yf:
        return f"{di} {MESI[mi]} – {df} {MESI[mf]} {yf}"
    return f"{data_it(inizio)} – {data_it(fine)}"


def durata_giorni(inizio, fine):
    yi, mi, di = (int(x) for x in inizio.split("-"))
    yf, mf, df = (int(x) for x in fine.split("-"))
    return (date(yf, mf, df) - date(yi, mi, di)).days + 1


def paragrafi_html(voci):
    """Lista di paragrafi (o stringa multiriga) → <p>."""
    if isinstance(voci, str):
        voci = [r.strip() for r in voci.splitlines() if r.strip()]
    return "".join(f"<p>{esc(v)}</p>" for v in (voci or []))


def build(dati, contenuto, forza_soldout=False):
    """(dati Airtable, contenuto editoriale) → (render model, warnings).
    Nessun dato inventato: le sezioni senza contenuto non compaiono."""
    vg = dati["viaggio"]
    oggi = dati.get("oggi") or date.today().isoformat()
    warnings = []

    # --- prezzi nei campi editoriali: mai ---
    campi_testo = [("strillo", contenuto.get("strillo")),
                   ("intro_titolo", contenuto.get("intro_titolo")),
                   ("intro", " ".join(contenuto.get("intro") or [])),
                   ("sistemazione", " ".join(contenuto.get("sistemazione") or []))]
    campi_testo += [(f"giorni[{i}]", (g.get("titolo") or "") + " " + (g.get("testo") or ""))
                    for i, g in enumerate(contenuto.get("giorni") or [])]
    for nome, testo in campi_testo:
        if RE_PREZZO_NEL_TESTO.search(testo or ""):
            warnings.append(f"possibile prezzo nel campo editoriale '{nome}': "
                            "i prezzi vivono solo nei dati parametrici")

    posti_residui = vg.get("posti_residui")
    sold_out = forza_soldout or (posti_residui is not None and posti_residui <= 0)

    # --- listino nella card: quota + supplementi, dai soli dati parametrici ---
    price_rows = []
    if vg.get("quota_base"):
        price_rows.append({"nome": "Quota di partecipazione",
                           "unita": "a persona in camera doppia",
                           "prezzo": vg["quota_base"], "quota": True})
    else:
        warnings.append("quota_base assente: pagina senza prezzo — verificare il record Viaggi")
    if vg.get("supplemento_singola"):
        price_rows.append({"nome": "Supplemento singola",
                           "unita": "per tutta la durata",
                           "prezzo": vg["supplemento_singola"], "quota": False})
    if vg.get("premio_annullamento"):
        price_rows.append({"nome": "Assicurazione annullamento (facoltativa)",
                           "unita": "a persona",
                           "prezzo": vg["premio_annullamento"], "quota": False})

    # --- fascia "in breve": coppie etichetta/valore, solo dati presenti; la durata è
    #     sovrascrivibile dal contenuto (es. "13 giorni di tour" quando i giorni di
    #     viaggio non coincidono con le date dall'Italia) ---
    fatti = []
    fatti.append(("Durata", contenuto.get("durata_label")
                  or f"{durata_giorni(vg['data_partenza'], vg['data_rientro'])} giorni"))
    if vg.get("aeroporto_partenza"):
        fatti.append(("Voli", f"da {vg['aeroporto_partenza']}"))
    if vg.get("posti_totali"):
        fatti.append(("Gruppo", f"max {vg['posti_totali']} partecipanti"))
    for f in contenuto.get("fatti_extra") or []:
        fatti.append((f.get("etichetta") or "In breve", f.get("valore") or ""))

    # --- condizioni: parametriche + editoriali ---
    condizioni = []
    def cond(titolo, corpo):
        if corpo and str(corpo).strip():
            condizioni.append((titolo, str(corpo).strip()))

    # Struttura pagamenti (dalla scheda Viaggi): acconto fisso uguale per tutti;
    # il premio assicurativo per intero alla conferma; il supplemento singola nel saldo.
    acconto = vg.get("acconto_per_persona")
    if acconto:
        testo = f"Alla conferma si versa un acconto di {euro(acconto)} a persona."
        if vg.get("premio_annullamento"):
            testo += ("\nIl premio dell'assicurazione annullamento, se sottoscritta, "
                      "si versa per intero alla conferma.")
        if vg.get("data_saldo"):
            saldo = f"\nSaldo entro il {data_it(vg['data_saldo'])}"
            if vg.get("supplemento_singola"):
                saldo += ", incluso l'eventuale supplemento singola"
            testo += saldo + "."
        cond("Acconto e saldo", testo)
    cond("Penali di annullamento", vg.get("scala_penali"))
    if vg.get("minimo_partecipanti"):
        testo = (f"Il viaggio si effettua con un minimo di {vg['minimo_partecipanti']} "
                 "partecipanti.")
        if vg.get("data_riconferma"):
            testo += (f"\nLa conferma definitiva della partenza viene comunicata entro il "
                      f"{data_it(vg['data_riconferma'])}.")
        cond("Numero minimo di partecipanti", testo)
    cond("Assicurazione annullamento", contenuto.get("assicurazione_testo"))
    cond("Documenti richiesti", contenuto.get("documenti_testo"))
    for extra in contenuto.get("condizioni_extra") or []:
        cond(extra.get("titolo"), extra.get("testo"))

    titolo = contenuto.get("titolo") or vg["nome_commerciale"]
    slug = (contenuto.get("slug") or "").strip()
    if not slug:
        raise SystemExit("contenuto.json senza slug")

    giorni = contenuto.get("giorni") or []

    model = {
        "slug": slug,
        "page_url": f"https://go.kibotours.com/viaggi/{slug}/",
        "titolo": titolo,
        "eyebrow": contenuto.get("eyebrow") or "Partenza di gruppo Kibo",
        "strillo": contenuto.get("strillo") or "",
        "trip_dates": trip_dates(vg["data_partenza"], vg["data_rientro"]),
        "fatti": fatti,
        "area": (contenuto.get("area") or "").strip(),
        "sold_out": sold_out,
        "quota_da": euro(vg["quota_base"]) if vg.get("quota_base") else "",
        "acconto": euro(acconto) if acconto else "",
        "saldo_testo": f", saldo entro il {data_it(vg['data_saldo'])}" if vg.get("data_saldo") else "",
        "intro_titolo": contenuto.get("intro_titolo") or titolo,
        "intro": contenuto.get("intro") or [],
        "giorni": giorni,
        "price_rows": price_rows,
        "included": contenuto.get("incluso") or [],
        "excluded": contenuto.get("non_incluso") or [],
        "sistemazione_titolo": contenuto.get("sistemazione_titolo") or "",
        "sistemazione": contenuto.get("sistemazione") or [],
        "conditions": condizioni,
        "cta_url": dati.get("cta_url") or "",
        "contact_url": dati.get("contact_url") or "https://www.kibotours.com",
        "meta_description": contenuto.get("meta_description")
            or f"{titolo} con Kibo: partenza di gruppo, voli e assistenza dall'Italia.",
        "updated_at": data_it(oggi),
    }

    if not model["intro"]:
        warnings.append("contenuto senza intro: la sezione 'Il viaggio' esce vuota")
    if not model["included"] or not model["excluded"]:
        warnings.append("incluso/non incluso incompleti: da completare prima di pubblicare")
    return model, warnings


def render(model):
    # Un template per macro-area (viaggio-oriente.html, viaggio-oceano-indiano.html,
    # viaggio-americhe.html): finché non esiste, si usa il layout base.
    area = model.get("area") or ""
    tpl_area = REPO / "templates" / f"viaggio-{area}.html"
    tpl_file = tpl_area if area and tpl_area.exists() else REPO / "templates" / "viaggio.html"
    tpl = tpl_file.read_text(encoding="utf-8")

    if model["sold_out"]:
        cta_url, cta_label = model["contact_url"], "Sold out — contattaci"
        chiusura_titolo = "Questo viaggio è sold out"
        chiusura_testo = ("I posti disponibili sono finiti. Scrivici per la lista d'attesa "
                          "o per la prossima partenza.")
    else:
        cta_url, cta_label = model["cta_url"], "Prenota"
        chiusura_titolo = "Pronto a partire?"
        chiusura_testo = "La prenotazione si completa online in pochi minuti."

    rows = []
    for r in model["price_rows"]:
        classe = "riga-prezzo quota" if r["quota"] else "riga-prezzo"
        unita_html = f'<span class="unita">{esc(r["unita"])}</span>' if r["unita"] else ""
        rows.append(f'<div class="{classe}"><span class="nome">{esc(r["nome"])}{unita_html}</span>'
                    f'<span class="importo">{esc(euro(r["prezzo"]))}</span></div>')

    tappe = []
    for g in model["giorni"]:
        etichetta = f"Giorno {g['giorno']}" if g.get("giorno") else ""
        tappe.append(f'<li><span class="punto"></span><span class="giorno">{esc(etichetta)}</span>'
                     f'<h3>{esc(g.get("titolo") or "")}</h3><p>{esc(g.get("testo") or "")}</p></li>')

    conds = "".join(
        f"<details><summary>{esc(t)}</summary><p>{esc(c)}</p></details>"
        for t, c in model["conditions"])

    valori = {
        "slug": model["slug"],
        "page_url": model["page_url"],
        "page_title": f"{model['titolo']} · Kibo",
        "meta_description": model["meta_description"],
        "eyebrow": model["eyebrow"],
        "titolo": model["titolo"],
        "strillo": model["strillo"],
        "trip_dates": model["trip_dates"],
        "facts_html": "".join(
            f'<div class="fatto"><span class="etichetta">{esc(et)}</span>'
            f'<span class="valore">{esc(va)}</span></div>' for et, va in model["fatti"]),
        "area_class": f"area-{model['area']}" if model.get("area") else "",
        "quota_da": model["quota_da"],
        "acconto": model["acconto"],
        "saldo_testo": model["saldo_testo"],
        "cta_url": cta_url,
        "cta_label": cta_label,
        "intro_titolo": model["intro_titolo"],
        "intro_html": paragrafi_html(model["intro"]),
        "itinerario_html": "".join(tappe),
        "price_rows_html": "".join(rows),
        "included_html": "".join(f"<li>{esc(v)}</li>" for v in model["included"]),
        "excluded_html": "".join(f"<li>{esc(v)}</li>" for v in model["excluded"]),
        "sistemazione_titolo": model["sistemazione_titolo"],
        "sistemazione_html": paragrafi_html(model["sistemazione"]),
        "conditions_html": conds,
        "chiusura_titolo": chiusura_titolo,
        "chiusura_testo": chiusura_testo,
        "updated_at": model["updated_at"],
    }

    blocchi = {
        "sold_out": model["sold_out"],
        "strillo": bool(model["strillo"]),
        "quota_da": bool(model["quota_da"]) and not model["sold_out"],
        "acconto": bool(model["acconto"]) and not model["sold_out"],
        "itinerario": bool(model["giorni"]),
        "sistemazione": bool(model["sistemazione_titolo"]) and bool(model["sistemazione"]),
        "condizioni": bool(model["conditions"]),
    }
    for nome, attivo in blocchi.items():
        pattern = re.compile(rf"<!--IF:{nome}-->(.*?)<!--ENDIF:{nome}-->", re.DOTALL)
        tpl = pattern.sub(r"\1" if attivo else "", tpl)

    for chiave, valore in valori.items():
        tpl = tpl.replace("{{" + chiave + "}}", valore)

    residui = re.findall(r"{{\w+}}", tpl)
    if residui:
        raise SystemExit(f"segnaposto non sostituiti: {residui}")
    return tpl


def main():
    argv = [a for a in sys.argv[1:] if a != "--soldout"]
    forza_soldout = "--soldout" in sys.argv
    dati = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    contenuto = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    model, warnings = build(dati, contenuto, forza_soldout)
    out = Path(argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(model), encoding="utf-8")
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    print(f"OK: {out}")


if __name__ == "__main__":
    main()

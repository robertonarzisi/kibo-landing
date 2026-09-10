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


def mese_anno(iso):
    y, m, _ = (int(x) for x in iso.split("-"))
    return f"{MESI[m]} {y}"


def periodo_partenze(prima, ultima):
    if prima[:7] == ultima[:7]:
        return mese_anno(prima)
    return f"{mese_anno(prima)} – {mese_anno(ultima)}"


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

    # --- viaggi da CATALOGO (tour a partenze multiple, es. sincronizzati da Travel
    #     Compositor): niente data unica, niente acconto/penali; quota "a partire da"
    #     calcolata sulla partenza futura più economica, elenco delle prossime date,
    #     CTA = richiesta di informazioni a booking@. Le partenze e le quote vivono
    #     nei dati parametrici (sample-data), mai nel contenuto editoriale. ---
    if (vg.get("tipo") or "gruppo") == "catalogo":
        return build_catalogo(dati, contenuto, oggi, warnings)

    # --- listino nella card: quota + supplementi, dai soli dati parametrici ---
    price_rows = []
    if vg.get("quota_base"):
        price_rows.append({"nome": "Quota di partecipazione",
                           "unita": "a persona in camera doppia",
                           "prezzo": vg["quota_base"], "quota": True})
    else:
        warnings.append("quota_base assente: pagina senza prezzo — verificare il record Viaggi")
    if vg.get("tasse_assicurazioni"):
        price_rows.append({"nome": "Tasse aeroportuali e assicurazioni (medico, bagaglio, annullamento)",
                           "unita": "a persona",
                           "prezzo": vg["tasse_assicurazioni"], "quota": False})
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
    # REGOLA (Roberto, 19/08/2026, vale per OGNI landing): in pagina mai la dicitura
    # "PENALI IN DEROGA" — si mostra "PENALI APPLICATE IN CASO DI CANCELLAZIONE".
    # Il testo contrattuale in Airtable resta com'e': la sostituzione e' solo di presentazione.
    penali = vg.get("scala_penali") or ""
    penali = penali.replace("SCALA PENALI IN DEROGA", "PENALI APPLICATE IN CASO DI CANCELLAZIONE")
    penali = penali.replace("PENALI IN DEROGA", "PENALI APPLICATE IN CASO DI CANCELLAZIONE")
    cond("Penali applicate in caso di cancellazione", penali)
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
        "totale_persona": euro(vg["quota_base"] + vg["tasse_assicurazioni"])
            if vg.get("quota_base") and vg.get("tasse_assicurazioni") else "",
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


def build_catalogo(dati, contenuto, oggi, warnings):
    vg = dati["viaggio"]
    partenze = sorted((p for p in (vg.get("partenze") or []) if p.get("data")),
                      key=lambda p: p["data"])
    future = [p for p in partenze if p["data"] >= oggi]
    if not future:
        warnings.append("nessuna partenza futura nei dati parametrici: pagina senza date")
    prezzi = [p["prezzo"] for p in future if p.get("prezzo")]
    quota_da = min(prezzi) if prezzi else vg.get("quota_da")
    if not quota_da:
        warnings.append("quota_da assente: pagina senza prezzo (quota su richiesta)")

    price_rows = []
    voli_inclusi = bool(vg.get("voli_inclusi"))
    if quota_da:
        price_rows.append({"nome": ("Quota a persona" if len(future) == 1 else "Quota a partire da") + (", voli inclusi" if voli_inclusi else ""),
                           "unita": ("a persona in camera doppia, voli dall'Italia, tasse aeroportuali e "
                                     "servizi a terra inclusi" if voli_inclusi else
                                     "a persona in camera doppia, partenza più economica"),
                           "prezzo": quota_da, "quota": True})
    if vg.get("supplemento_singola"):
        unita = "per tutta la durata"
        if vg.get("supplemento_singola_nota"):
            unita += f" ({vg['supplemento_singola_nota']})"
        price_rows.append({"nome": "Supplemento singola", "unita": unita,
                           "prezzo": vg["supplemento_singola"], "quota": False})
    MAX_DATE = 8
    if vg.get("assicurazione"):
        price_rows.append({"nome": "Assicurazione medico, bagaglio e annullamento (facoltativa)",
                           "unita": "a persona", "prezzo": vg["assicurazione"], "quota": False})
    for p in future[:MAX_DATE]:
        price_rows.append({"nome": f"Partenza {data_it(p['data'])}", "unita": p.get("nota") or "",
                           "prezzo": p.get("prezzo"), "quota": False,
                           "senza_prezzo": not p.get("prezzo")})
    altre = len(future) - min(len(future), MAX_DATE)
    partenze_nota = ""
    if altre > 0:
        partenze_nota = (f"E altre {altre} partenze fino al {data_it(future[-1]['data'])}: "
                         "chiedici la data che preferisci.")

    fatti = [("Durata", contenuto.get("durata_label") or "")]
    if vg.get("partenze_note"):
        fatti.append(("Partenze", vg["partenze_note"]))
    elif future:
        fatti.append(("Partenze", f"{len(future)} date in calendario"))
    for f in contenuto.get("fatti_extra") or []:
        fatti.append((f.get("etichetta") or "In breve", f.get("valore") or ""))

    condizioni = []
    def cond(titolo, corpo):
        if corpo and str(corpo).strip():
            condizioni.append((titolo, str(corpo).strip()))
    cond("Quote e disponibilità",
         "Le quote sono indicative, riferite alla sistemazione in camera doppia e alla "
         "data di partenza indicata; variano con la stagione e con la categoria degli "
         "alberghi scelta. Disponibilità e quota definitiva vengono confermate per "
         "iscritto al momento della richiesta, prima di qualsiasi impegno.")
    cambio = vg.get("cambio") or {}
    if cambio.get("valuta") and cambio.get("tasso") and cambio.get("data"):
        toll = cambio.get("tolleranza_pct", 5)
        cond("Cambio valutario",
             f"I servizi a terra di questo viaggio sono in {cambio['valuta']}. Le quote sono "
             f"calcolate al cambio del {data_it(cambio['data'])} (1 EUR = {str(cambio['tasso']).replace(".", ",")} "
             f"{cambio['valuta']}) e possono essere adeguate, in più o in meno, se alla "
             f"conferma il cambio varia oltre il {toll}%.")
    cond("Voli dall'Italia", vg.get("voli_testo") or contenuto.get("voli_testo"))
    if voli_inclusi:
        # regola di Roberto (10/09/2026): mai la data di emissione della tariffa, senza blocco
        # dei posti non è attendibile; sempre e comunque la formula standard.
        cond("Tariffa aerea", vg.get("validita_testo") or
             "La tariffa aerea compresa nella quota è soggetta a variazione ed è da verificare al "
             "momento della prenotazione. La quota è calcolata su base 2 persone e non si applica "
             "ai gruppi.")
    cond("Documenti richiesti", contenuto.get("documenti_testo"))
    for extra in contenuto.get("condizioni_extra") or []:
        cond(extra.get("titolo"), extra.get("testo"))

    titolo = contenuto.get("titolo") or vg["nome_commerciale"]
    slug = (contenuto.get("slug") or "").strip()
    if not slug:
        raise SystemExit("contenuto.json senza slug")

    model = {
        "tipo": "catalogo",
        "slug": slug,
        "page_url": f"https://go.kibotours.com/viaggi/{slug}/",
        "titolo": titolo,
        "eyebrow": contenuto.get("eyebrow") or "Viaggio Kibo con partenze garantite",
        "strillo": contenuto.get("strillo") or "",
        "trip_dates": periodo_partenze(future[0]["data"], future[-1]["data"]) if future
                      else "date su richiesta",
        "fatti": fatti,
        "area": (contenuto.get("area") or "").strip(),
        "sold_out": False,
        "quota_da": euro(quota_da) if quota_da else "",
        "totale_persona": "",
        "acconto": "",
        "saldo_testo": "",
        "intro_titolo": contenuto.get("intro_titolo") or titolo,
        "intro": contenuto.get("intro") or [],
        "giorni": contenuto.get("giorni") or [],
        "price_rows": price_rows,
        "partenze_nota": partenze_nota,
        "included": contenuto.get("incluso") or [],
        "excluded": contenuto.get("non_incluso") or [],
        "sistemazione_titolo": contenuto.get("sistemazione_titolo") or "",
        "sistemazione": contenuto.get("sistemazione") or [],
        "conditions": condizioni,
        "cta_url": dati.get("cta_url") or "",
        "cta_label": dati.get("cta_label") or "Richiedi informazioni",
        "chiusura_titolo": "Ti interessa questo viaggio?",
        "chiusura_testo": ("Scrivici indicando la data che preferisci e in quanti siete: "
                           "ti rispondiamo con disponibilità e quota confermata, senza impegno."),
        "contact_url": dati.get("contact_url") or "https://www.kibotours.com",
        "meta_description": contenuto.get("meta_description")
            or f"{titolo} con Kibo: tour con partenze garantite, guida in italiano e assistenza dall'Italia.",
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
        cta_url, cta_label = model["cta_url"], model.get("cta_label") or "Prenota"
        chiusura_titolo = model.get("chiusura_titolo") or "Pronto a partire?"
        chiusura_testo = (model.get("chiusura_testo")
                          or "La prenotazione si completa online in pochi minuti.")

    rows = []
    for r in model["price_rows"]:
        classe = "riga-prezzo quota" if r["quota"] else "riga-prezzo"
        unita_html = f'<span class="unita">{esc(r["unita"])}</span>' if r["unita"] else ""
        importo = "su richiesta" if r.get("senza_prezzo") else euro(r["prezzo"])
        rows.append(f'<div class="{classe}"><span class="nome">{esc(r["nome"])}{unita_html}</span>'
                    f'<span class="importo">{esc(importo)}</span></div>')
    if model.get("partenze_nota"):
        rows.append(f'<p class="nota-listino">{esc(model["partenze_nota"])}</p>')

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
        "totale_persona": model["totale_persona"],
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
        "totale_persona": bool(model["totale_persona"]),
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

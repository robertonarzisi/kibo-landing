#!/usr/bin/env python3
"""GEO delle landing: JSON-LD (TouristTrip + Offer + TravelAgency + BreadcrumbList) e paragrafo «In breve».

Tutto è ricavato dalla pagina già generata: titolo, description, fatti della card (date, durata, percorso,
gruppo…), quota «da € X», giorni dell'itinerario. Niente dati nuovi, niente prezzi fuori dai dati parametrici:
se un fatto non è in pagina, non va nel JSON-LD. Idempotente: rieseguirlo sostituisce i blocchi precedenti.

Uso:
    python3 scripts/geo.py viaggi/*/index.html      # pagine già pubblicate
    python3 scripts/geo.py --llms llms.txt viaggi/*/index.html   # elenco per gli assistenti AI
render.py lo applica da solo alle pagine nuove (funzione arricchisci).
Audit e motivazioni: repo agenti, KIBO/progetti/sito-web/audit-geo-2026-11.md (03/11/2026).
"""
import html
import json
import re
import sys
from pathlib import Path

KIBO = {
    "@type": "TravelAgency",
    "@id": "https://www.kibotours.com/#organization",
    "name": "Kibo Tours",
    "legalName": "Kibo Tours S.r.l.",
    "url": "https://www.kibotours.com/",
    "logo": "https://www.kibotours.com/wp-content/uploads/2023/04/logo_kibo_new._small.png",
    "telephone": "+39 015 252 2999",
    "vatID": "IT02235470024",
    "address": {"@type": "PostalAddress", "streetAddress": "Piazza Martiri della Libertà 3", "postalCode": "13900",
                "addressLocality": "Biella", "addressRegion": "BI", "addressCountry": "IT"},
    "sameAs": ["https://www.linkedin.com/company/kibotours"],
    "subOrganization": {"@type": "TravelAgency", "@id": "https://ki-run.it/#organization", "name": "KiRun", "url": "https://ki-run.it/"},
}
MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                   "settembre", "ottobre", "novembre", "dicembre"], 1)}
RE_LD = re.compile(r'\n?<script type="application/ld\+json" id="kibo-geo">.*?</script>\n?', re.S)
RE_BREVE = re.compile(r'<p class="kibo-sintesi">.*?</p>', re.S)


def testo(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def data_iso(s):
    """«29 dicembre 2026» → 2026-12-29; senza giorno → None."""
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", s.strip().lower())
    if not m or m.group(2) not in MESI:
        return None
    return f"{m.group(3)}-{MESI[m.group(2)]:02d}-{int(m.group(1)):02d}"


def leggi(pagina):
    """I fatti della pagina, solo quelli presenti nel markup del template viaggio.html."""
    f = {}
    m = re.search(r"<h1>(.*?)</h1>", pagina, re.S)
    f["titolo"] = testo(m.group(1)) if m else ""
    m = re.search(r'<meta name="description" content="([^"]*)"', pagina)
    f["description"] = html.unescape(m.group(1)) if m else ""
    m = re.search(r'<link rel="canonical" href="([^"]+)"', pagina)
    f["url"] = m.group(1) if m else ""
    m = re.search(r'<meta property="og:image" content="([^"]+)"', pagina)
    f["image"] = m.group(1) if m else ""
    f["fatti"] = {testo(e): testo(v) for e, v in re.findall(
        r'<div class="fatto[^"]*"><span class="etichetta">(.*?)</span><span class="valore">(.*?)</span>', pagina, re.S)}
    q = f["fatti"].get("Quota a persona", "")
    m = re.search(r"€\s*([\d.]+)", q)
    f["prezzo"] = int(m.group(1).replace(".", "")) if m else None
    f["sold_out"] = bool(re.search(r'<a class="cta"[^>]*>\s*Sold out', pagina))
    f["giorni"] = [(testo(h), testo(p)) for h, p in re.findall(
        r'<li><span class="punto"></span><span class="giorno">[^<]*</span><h3>(.*?)</h3><p>(.*?)</p>(?:<figure class="foto-tappa">.*?</figure>)?</li>', pagina, re.S)]
    return f


def jsonld(f):
    trip = {
        "@type": "TouristTrip",
        "@id": f["url"] + "#viaggio",
        "name": f["titolo"],
        "description": f["description"],
        "url": f["url"],
        "inLanguage": "it",
        "provider": {"@id": KIBO["@id"]},
    }
    if f["image"]:
        trip["image"] = f["image"]
    date = f["fatti"].get("Date", "")
    parti = [p.strip() for p in re.split(r"\s+[–-]\s+", date)]
    if len(parti) == 2 and data_iso(parti[0]) and data_iso(parti[1]):
        trip["departureTime"], trip["arrivalTime"] = data_iso(parti[0]), data_iso(parti[1])
    if f["giorni"]:
        trip["itinerary"] = {"@type": "ItemList", "numberOfItems": len(f["giorni"]), "itemListElement": [
            {"@type": "ListItem", "position": i, "name": t, "description": d}
            for i, (t, d) in enumerate(f["giorni"], 1)]}
    if f["prezzo"]:
        trip["offers"] = {"@type": "Offer", "price": f["prezzo"], "priceCurrency": "EUR", "url": f["url"],
                          "availability": "https://schema.org/SoldOut" if f["sold_out"] else "https://schema.org/InStock",
                          "seller": {"@id": KIBO["@id"]}}
    briciole = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Kibo Tours", "item": "https://www.kibotours.com/"},
        {"@type": "ListItem", "position": 2, "name": "Partenze di gruppo", "item": "https://go.kibotours.com/"},
        {"@type": "ListItem", "position": 3, "name": f["titolo"], "item": f["url"]}]}
    return {"@context": "https://schema.org", "@graph": [trip, KIBO, briciole]}


def in_breve(f):
    """Due o tre frasi citabili, costruite solo con i fatti della card."""
    fa = f["fatti"]
    frasi = [f["titolo"].rstrip(".") + "."]
    durata = []
    if fa.get("Durata"):
        durata.append(f"Durata: {fa['Durata']}")
    if fa.get("Percorso"):
        durata.append(f"percorso: {fa['Percorso'].replace(' → ', ', ')}")
    if durata:
        frasi.append("; ".join(durata) + ".")
    if fa.get("Date"):
        frasi.append(f"Date: {fa['Date']}" + (f"; {fa['Partenze'][0].lower() + fa['Partenze'][1:]}" if fa.get("Partenze") else "") + ".")
    altro = [v for k, v in fa.items() if k in ("Formula", "Voli", "Gruppo", "Accompagnamento", "Guida", "Trattamento")]
    if altro:
        frasi.append(altro[0][0].upper() + altro[0][1:] + "".join(f"; {v}" for v in altro[1:]) + ".")
    if f["prezzo"] and not f["sold_out"]:
        frasi.append(f"Quota a persona da € {f['prezzo']:,}".replace(",", ".") + ", viaggio organizzato da Kibo Tours, tour operator di Biella.")
    elif f["sold_out"]:
        frasi.append("Questo viaggio è sold out.")
    return '<p class="kibo-sintesi"><strong>In breve:</strong> ' + html.escape(" ".join(frasi), quote=False) + "</p>"


def arricchisci(pagina):
    f = leggi(pagina)
    if not f["titolo"] or not f["url"]:
        return pagina
    blocco = ('\n<script type="application/ld+json" id="kibo-geo">'
              + json.dumps(jsonld(f), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>")
    pagina = RE_LD.sub("", pagina).replace("</head>", blocco + "\n</head>", 1)
    pagina = RE_BREVE.sub("", pagina)
    # primo blocco di testo dopo l'intro: è il paragrafo che un assistente AI cita
    return re.sub(r'(<div class="testo">)', r"\1" + in_breve(f).replace("\\", "\\\\"), pagina, count=1)


def llms(percorsi, destinazione):
    """llms.txt di go.kibotours.com: chi è Kibo e l'elenco dei viaggi pubblicati, dalle pagine stesse."""
    righe = ["# Kibo Tours · Partenze di gruppo", "",
             "> Kibo Tours (kibotours.com) è un tour operator di Biella: viaggi di gruppo con guida o accompagnamento in "
             "italiano, tour a date garantite e viaggi su misura, soprattutto in Oriente, Americhe, Medio Oriente e Africa. "
             "Su go.kibotours.com ci sono le schede dei viaggi in vendita, con itinerario, cosa è incluso e quote.", "",
             "## Viaggi in vendita", ""]
    for p in sorted(map(Path, percorsi)):
        pagina = p.read_text(encoding="utf-8")
        if 'name="robots" content="noindex' in pagina:
            continue
        f = leggi(pagina)
        if not f["titolo"]:
            continue
        info = [x for x in (f["fatti"].get("Durata"), f["fatti"].get("Date"),
                            f"da € {f['prezzo']:,}".replace(",", ".") + " a persona" if f["prezzo"] and not f["sold_out"] else
                            ("sold out" if f["sold_out"] else None)) if x]
        righe.append(f"- [{f['titolo']}]({f['url']}): " + ", ".join(info))
    righe += ["", "## Kibo Tours", "",
              "- [Sito Kibo Tours](https://www.kibotours.com/)",
              "- [Partenze di gruppo](https://www.kibotours.com/partenze-di-gruppo/)",
              "- [Contatti](https://www.kibotours.com/contatti/): +39 015 252 2999, Piazza Martiri della Libertà 3, 13900 Biella",
              "- [KiRun, viaggi per maratone dello stesso gruppo](https://ki-run.it/)", ""]
    Path(destinazione).write_text("\n".join(righe), encoding="utf-8")
    print(f"scritto {destinazione}")


def main(percorsi):
    if percorsi and percorsi[0] == "--llms":
        return llms(percorsi[2:], percorsi[1])
    for p in map(Path, percorsi):
        prima = p.read_text(encoding="utf-8")
        dopo = arricchisci(prima)
        if dopo != prima:
            p.write_text(dopo, encoding="utf-8")
        print(("aggiornata " if dopo != prima else "invariata  ") + str(p))


if __name__ == "__main__":
    main(sys.argv[1:])

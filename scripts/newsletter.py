#!/usr/bin/env python3
"""Genera la pagina newsletter/<data>/index.html (+ le due immagini 600×750) da una specifica JSON.

Uso: python3 scripts/newsletter.py <spec.json>
Specifica:
{
  "data": "2026-10-13",
  "titolo": "Kibo · ...",                      # <title> della pagina (diventa l'oggetto in MailUp)
  "intro": "Due proposte per i tuoi clienti: ...",
  "blocchi": [
    {"slug": "thailandia-gemme-del-siam", "img": "thailandia.jpg", "alt": "...",
     "titolo": "Le gemme del Siam", "testo": "... Da 1.005 € a persona.",
     "subject": "Richiesta quota - Thailandia Gemme del Siam"},
    {...}
  ]
}
Le immagini si ricavano da assets/social/<slug>-post.jpg (1080×1350 → 600×750). Il layout è quello
delle newsletter dal 22/09/2026 (tabella 600 px, pulsanti «VEDI IL PROGRAMMA COMPLETO» + «RICHIEDI LA
QUOTA», piè Kibo). Nessun prezzo viene calcolato qui: i testi arrivano già pronti dal kit social."""
import html, json, sys, urllib.parse
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
BTN1 = 'display:inline-block;background:#0f4c5c;color:#ffffff;font-family:Montserrat,Arial,sans-serif;font-size:14px;font-weight:600;letter-spacing:.5px;text-decoration:none;padding:13px 26px;border-radius:4px;'
BTN2 = 'display:inline-block;background:#ffffff;color:#0f4c5c;border:2px solid #0f4c5c;font-family:Montserrat,Arial,sans-serif;font-size:14px;font-weight:600;letter-spacing:.5px;text-decoration:none;padding:11px 24px;border-radius:4px;'
TXT = 'padding:10px 36px 0 36px;font-family:Montserrat,Arial,sans-serif;font-size:14px;line-height:1.6;color:#22333b;text-align:center;'


def blocco(data, b):
    url = f"https://go.kibotours.com/viaggi/{b['slug']}/"
    img = f"https://go.kibotours.com/newsletter/{data}/{b['img']}"
    mailto = "mailto:booking@kibotours.com?subject=" + urllib.parse.quote(b['subject'])
    return f"""
<tr><td align="center" style="padding:28px 0 8px 0;">
  <a href="{url}" target="_blank"><img src="{img}" width="600" alt="{html.escape(b['alt'], quote=True)}" style="display:block;width:600px;max-width:100%;height:auto;border:0;"></a>
</td></tr>
<tr><td style="{TXT}">
<strong>{html.escape(b['titolo'])}</strong> · {html.escape(b['testo'])}
</td></tr>
<tr><td align="center" style="padding:14px 0 22px 0;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="padding:0 8px;"><a href="{url}" target="_blank" style="{BTN1}">VEDI IL PROGRAMMA COMPLETO</a></td>
    <td style="padding:0 8px;"><a href="{mailto}" style="{BTN2}">RICHIEDI LA QUOTA</a></td>
  </tr></table>
</td></tr>
"""


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    data = spec["data"]; out = REPO / "newsletter" / data; out.mkdir(parents=True, exist_ok=True)
    for b in spec["blocchi"]:
        src = REPO / "assets" / "social" / f"{b['slug']}-post.jpg"
        Image.open(src).convert("RGB").resize((600, 750), Image.LANCZOS).save(out / b["img"], quality=82, optimize=True)
    corpo = "".join(blocco(data, b) for b in spec["blocchi"])
    pagina = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(spec['titolo'])}</title></head>
<body style="margin:0;padding:0;background:#f3f5f6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f5f6;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:100%;background:#ffffff;">
<tr><td style="padding:28px 36px 6px 36px;font-family:Montserrat,Arial,sans-serif;font-size:14px;line-height:1.6;color:#22333b;text-align:center;">
{html.escape(spec['intro'])}
</td></tr>
{corpo}<tr><td style="padding:22px 36px;background:#0f4c5c;color:#ffffff;font-family:Montserrat,Arial,sans-serif;font-size:13px;line-height:1.7;text-align:center;">
<strong>Kibo</strong> where dreams come tours<br>
<a href="mailto:booking@kibotours.com" style="color:#ffffff;">booking@kibotours.com</a> · <a href="https://www.kibotours.com" style="color:#ffffff;">www.kibotours.com</a><br>
tel. (+39) 015.252.2999
</td></tr>
</table>
</td></tr></table>
</body></html>
"""
    (out / "index.html").write_text(pagina)
    print(f"OK: newsletter/{data}/index.html + {', '.join(b['img'] for b in spec['blocchi'])}")


if __name__ == "__main__":
    main()

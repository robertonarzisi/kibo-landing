#!/usr/bin/env python3
"""Genera sitemap.xml di go.kibotours.com: home e le pagine di viaggi/ (e /cookie/) che NON hanno il tag noindex (lastmod = ultimo commit git del file).
Uso: python3 scripts/sitemap.py   (da rilanciare dopo ogni pubblicazione, insieme a render_index.py)"""
import glob, subprocess, datetime, pathlib
REPO = pathlib.Path(__file__).resolve().parent.parent
def lastmod(path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], cwd=REPO, capture_output=True, text=True).stdout.strip()
        return out or datetime.date.today().isoformat()
    except Exception:
        return datetime.date.today().isoformat()
urls = [("https://go.kibotours.com/", lastmod("index.html"), "weekly", "0.6"), ("https://go.kibotours.com/cookie/", lastmod("cookie/index.html"), "yearly", "0.1")]
def indicizzabile(path):
    # Dentro solo le pagine senza <meta name="robots" ... noindex>: una pagina noindex in sitemap
    # fa scattare in Search Console «Esclusa in base al tag noindex» (visto il 28/10/2026).
    return "noindex" not in pathlib.Path(path).read_text(encoding="utf-8").split("</head>", 1)[0]
urls = [u for u in urls if indicizzabile(REPO / u[0].replace("https://go.kibotours.com/", "").rstrip("/") / "index.html") or u[0].endswith("kibotours.com/")]
saltate = []
for p in sorted(glob.glob(str(REPO / "viaggi" / "*" / "index.html"))):
    slug = pathlib.Path(p).parent.name
    if not indicizzabile(p):
        saltate.append(slug); continue
    urls.append((f"https://go.kibotours.com/viaggi/{slug}/", lastmod(f"viaggi/{slug}/index.html"), "weekly", "0.8"))
xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, d, f, pr in urls:
    xml.append(f"  <url><loc>{u}</loc><lastmod>{d}</lastmod><changefreq>{f}</changefreq><priority>{pr}</priority></url>")
xml.append("</urlset>")
(REPO / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
print(f"sitemap.xml: {len(urls)} URL; saltate perché noindex: {len(saltate)} ({', '.join(saltate)})")

#!/usr/bin/env python3
"""Grafiche social Kibo (Cora / Kibo) — genera assets/social/<slug>-{post,story}.jpg.
Uso: python3 scripts/social.py  (rigenera tutti i viaggi in VIAGGI)
Font: scarica Montserrat e Fraunces variabili in scripts/fonts/ al primo run (licenza OFL).

Derivato dal motore social di Cora KiRun, con tema Kibo (kibo.css della landing):
teal #265A63 · blu #027ABB · Montserrat per i testi, Fraunces per il titolo.
Post 1080x1350 e story 1080x1920, parametriche per viaggio.
Regole: CTA solo "Prenota"; nel nastro solo fatti reali (mai claim inventati);
niente prezzi fuori listino."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # radice repo
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
BRAND = os.path.join(BASE, "assets", "brand")
HERO_DIR = os.path.join(BASE, "assets", "hero")

BLU = (2, 122, 187)
BLU2 = (38, 155, 209)
TEAL = (38, 90, 99)
TEAL_NOTTE = (20, 46, 51)
AZZURRO = (157, 186, 196)
CARTA = (237, 244, 243)
BIANCO = (255, 255, 255)

VIAGGI = {
    "vietnam-2027-03": {
        "kicker": "PARTENZA DI GRUPPO · 5–22 MARZO 2027",
        "title": ["Vietnam", "autentico"],
        "info1": "16 giorni da Hanoi al Delta del Mekong",
        "info2": "Voli di linea da Milano Malpensa inclusi",
        "ribbon": "SOLO 18 POSTI",
        "ribbon_style": "evidenza",
        "cta": "Prenota",
    },
}

FONT_URLS = {
    "Montserrat": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Fraunces": "https://github.com/google/fonts/raw/main/ofl/fraunces/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf",
}

def ensure_fonts():
    os.makedirs(FONTS, exist_ok=True)
    import urllib.request
    for name, url in FONT_URLS.items():
        dest = os.path.join(FONTS, f"{name}.ttf")
        if not os.path.exists(dest):
            urllib.request.urlretrieve(url, dest)

def F(family, size, weight):
    """Font variabile con peso richiesto (e optical size al massimo utile per Fraunces)."""
    f = ImageFont.truetype(os.path.join(FONTS, f"{family}.ttf"), size)
    axes = f.get_variation_axes()
    vals = []
    for a in axes:
        nome = (a["name"] if isinstance(a["name"], str) else a["name"].decode()).lower()
        if "weight" in nome:
            vals.append(weight)
        elif "optical" in nome:
            vals.append(min(a["maximum"], max(a["minimum"], size)))
        else:
            vals.append(a["default"])
    if vals:
        f.set_variation_by_axes(vals)
    return f

def tracked(draw, xy, text, font, fill, tracking=0, shadow=None):
    x, y = xy
    if shadow:
        for ch in text:
            draw.text((x + 2, y + 3), ch, font=font, fill=shadow)
            x += font.getlength(ch) + tracking
        x = xy[0]
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking
    return x

def tracked_len(text, font, tracking=0):
    return sum(font.getlength(c) + tracking for c in text) - (tracking if text else 0)

def crop_cover(img, w, h, focus_y=0.55):
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = int(sw * scale + 0.5), int(sh * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = int((nh - h) * focus_y)
    top = max(0, min(top, nh - h))
    return img.crop((left, top, left + w, top + h))

def gradient_overlay(size, color, y_start_frac, max_alpha):
    w, h = size
    mask = Image.new("L", (1, h), 0)
    y0 = int(h * y_start_frac)
    for y in range(y0, h):
        t = (y - y0) / max(1, h - y0)
        mask.putpixel((0, y), int(max_alpha * (t ** 1.25)))
    mask = mask.resize((w, h))
    layer = Image.new("RGBA", (w, h), color + (255,))
    layer.putalpha(mask)
    return layer

def paste_logo(canvas, path, x, y, width):
    logo = Image.open(path).convert("RGBA")
    ratio = width / logo.width
    logo = logo.resize((width, int(logo.height * ratio)), Image.LANCZOS)
    alpha = logo.split()[3].point(lambda a: int(a * 0.45))
    black = Image.new("RGBA", logo.size, (8, 22, 26, 255))
    black.putalpha(alpha)
    sh = black.filter(ImageFilter.GaussianBlur(6))
    canvas.alpha_composite(sh, (x + 2, y + 4))
    canvas.alpha_composite(logo, (x, y))
    return logo.size

def cta_pill(canvas, draw, x, y, text, font, pad_x=64, pad_y=24):
    tw = tracked_len(text, font)
    w, h = int(tw + pad_x * 2), int(font.size + pad_y * 2)
    pill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=BLU + (255,))
    canvas.alpha_composite(pill, (x, y))
    ImageDraw.Draw(canvas).text((x + pad_x, y + pad_y - 4), text, font=font, fill=BIANCO)
    return h

def ribbon_tag(canvas, x, y, text, style):
    """Nastro a parallelogramma: evidenza = bianco con bordo blu, sold_out = blu pieno."""
    font = F("Montserrat", 31, 600)
    tr = 3
    tw = tracked_len(text, font, tr)
    pad_x, h, skew = 36, 62, 14
    w = int(tw + pad_x * 2 + skew)
    tag = Image.new("RGBA", (w + 8, h + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(tag)
    pts = [(skew, 0), (w, 0), (w - skew, h), (0, h)]
    if style == "sold_out":
        d.polygon(pts, fill=BLU + (255,))
        fg = BIANCO
    else:
        d.polygon(pts, fill=BIANCO + (247,))
        d.polygon([(skew, 0), (skew + 10, 0), (10, h), (0, h)], fill=BLU + (255,))
        fg = TEAL
    mask = Image.new("L", tag.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=120)
    dark = Image.new("RGBA", tag.size, (8, 22, 26, 255))
    dark.putalpha(mask)
    canvas.alpha_composite(dark.filter(ImageFilter.GaussianBlur(7)), (x + 2, y + 5))
    canvas.alpha_composite(tag, (x, y))
    tracked(ImageDraw.Draw(canvas), (x + skew + pad_x - 4, y + (h - font.size) // 2 - 4), text, font, fg, tracking=tr)
    return h

def compose(slug, fmt):
    vg = VIAGGI[slug]
    W, H = (1080, 1350) if fmt == "post" else (1080, 1920)
    M = 72
    hero = Image.open(os.path.join(HERO_DIR, f"{slug}.jpg")).convert("RGB")

    if fmt == "post":
        canvas = Image.new("RGBA", (W, H))
        canvas.paste(crop_cover(hero, W, H).convert("RGBA"), (0, 0))
        canvas.alpha_composite(gradient_overlay((W, H), TEAL_NOTTE, 0.30, 250))
        photo_bottom = H
    else:
        ph = 1150
        canvas = Image.new("RGBA", (W, H), TEAL_NOTTE + (255,))
        canvas.paste(crop_cover(hero, W, ph).convert("RGBA"), (0, 0))
        canvas.alpha_composite(gradient_overlay((W, ph), TEAL_NOTTE, 0.55, 255))
        photo_bottom = ph

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 10], fill=BLU)

    paste_logo(canvas, f"{BRAND}/logo-kibo-bianco.png", M, M - 8, 250)

    shadow = (8, 22, 26, 160)
    kicker_f = F("Montserrat", 33, 500)
    head_f = F("Fraunces", 108, 520)
    info_f = F("Montserrat", 37, 400)
    cta_f = F("Montserrat", 34, 600)

    block = 62 + 122 * len(vg["title"]) + 18 + 56
    block += 76 + 82 if vg["cta"] else 56
    if vg["ribbon"]:
        block += 62 + 26

    if fmt == "post":
        y = H - block - 62
    else:
        y = photo_bottom + max(56, (H - photo_bottom - block) // 3)

    if vg["ribbon"]:
        ribbon_tag(canvas, M, y, vg["ribbon"], vg["ribbon_style"])
        y += 62 + 26

    tracked(draw, (M, y), vg["kicker"], kicker_f, BLU2, tracking=4, shadow=shadow)
    y += 62
    for line in vg["title"]:
        tracked(draw, (M - 4, y), line, head_f, BIANCO, shadow=shadow)
        y += 122

    y += 18
    tracked(draw, (M, y), vg["info1"], info_f, CARTA, shadow=shadow)
    y += 56
    tracked(draw, (M, y), vg["info2"], info_f, AZZURRO, shadow=shadow)

    if vg["cta"]:
        y += 76
        cta_pill(canvas, draw, M, y, vg["cta"], cta_f)

    out = os.path.join(BASE, "assets", "social", f"{slug}-{fmt}.jpg")
    canvas.convert("RGB").save(out, quality=92, optimize=True)
    print(out)

if __name__ == "__main__":
    ensure_fonts()
    for slug in VIAGGI:
        for fmt in ("post", "story"):
            compose(slug, fmt)

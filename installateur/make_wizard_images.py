"""Génère les images de l'assistant d'installation (thème sombre + accent vert, comme l'appli)."""
from PIL import Image, ImageDraw, ImageFont
BG, ACC, TXT, SUB = (9, 13, 22), (16, 185, 129), (236, 241, 250), (140, 152, 175)

def font(sz, bold=False):
    for n in (("segoeuib.ttf" if bold else "segoeui.ttf"), "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        try: return ImageFont.truetype(n, sz)
        except OSError: pass
    return ImageFont.load_default()

def shield(d, cx, cy, s):
    pts = [(cx, cy - s), (cx + s * .85, cy - s * .55), (cx + s * .85, cy + s * .1), (cx, cy + s), (cx - s * .85, cy + s * .1), (cx - s * .85, cy - s * .55)]
    d.polygon(pts, fill=ACC)
    inner = [(cx, cy - s * .72), (cx + s * .6, cy - s * .4), (cx + s * .6, cy + s * .05), (cx, cy + s * .7), (cx - s * .6, cy + s * .05), (cx - s * .6, cy - s * .4)]
    d.polygon(inner, fill=BG)
    d.line([(cx - s * .3, cy), (cx - s * .05, cy + s * .27), (cx + s * .35, cy - s * .22)], fill=ACC, width=max(2, int(s * .12)), joint="curve")

def side(w, h):
    k = w / 164
    im = Image.new("RGB", (w, h), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, int(4 * k)], fill=ACC)
    shield(d, w / 2, h * .30, 38 * k)
    t = font(int(22 * k), True); d.text((w / 2, h * .52), "Bouclier", font=t, fill=TXT, anchor="mm")
    d.text((w / 2, h * .575), "v3.0", font=font(int(12 * k)), fill=ACC, anchor="mm")
    sf = font(int(10.5 * k))
    for i, line in enumerate(("Studio d'anonymisation", "100 % local", "Aucune donnée ne", "quitte votre PC")):
        d.text((w / 2, h * .70 + i * 15 * k), line, font=sf, fill=SUB, anchor="mm")
    return im

def small(s):
    im = Image.new("RGB", (s, s), BG); shield(ImageDraw.Draw(im), s / 2, s / 2, s * .36); return im

side(164, 314).save("wizard_large.bmp"); side(246, 472).save("wizard_large_2x.bmp")
small(55).save("wizard_small.bmp"); small(110).save("wizard_small_2x.bmp")
small(256).save("icone.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

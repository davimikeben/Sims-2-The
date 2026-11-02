#!/usr/bin/env python3
"""
Plumbob Glass - gerador do teclado virtual (skin pack) para ARMSX2 / PCSX2-Android.

O ARMSX2 desenha cada botao do controle de toque com `ContentScale.Fit` dentro de
uma caixa quadrada que faz `fillMaxSize()`, e aplica `alpha` (a opacidade que o
usuario escolhe). Portanto:

  * a arte precisa ser quadrada (1:1) e o botao deve ocupar o quadro todo;
  * o fundo tem de ser TRANSPARENTE (RGBA), nunca preto;
  * botoes de ombro (L1/L2/R1/R2) e start/select usam 512x256 (2:1), como os
    assets originais do app, para a "pilula" sair no formato certo.

Convencao de nomes (ControllerSkinStore.kt, esquema iOS):
  ic_controller_<key>_button.png  -> cross/circle/square/triangle,
                                     l1 l2 l3 r1 r2 r3, start select,
                                     up down left right, macro1..4
  ic_controller_analog_base.png e ic_controller_analog_stick.png

Uso:
  python3 tools/gen_skin.py --out skin/src --preview docs/preview.png
"""

from __future__ import annotations

import argparse
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------- #
#  Tokens visuais
# --------------------------------------------------------------------------- #

SS = 1                     # escala da COMPOSICAO (512px: barato)
SHAPE_SS = 4               # escala de DESENHO das formas/texto (4x -> AA perfeito)
BASE = 512                 # lado do asset final
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

INK = (8, 13, 15, 255)
GLASS_TOP = (54, 72, 74, 255)
GLASS_BOT = (12, 18, 20, 255)

MINT = (84, 232, 160, 255)
PLUMBOB = (61, 214, 96, 255)
GOLD = (242, 206, 122, 255)
ICE = (232, 250, 244, 255)

PS_TRIANGLE = (86, 226, 150, 255)
PS_CIRCLE = (255, 96, 96, 255)
PS_CROSS = (110, 156, 255, 255)
PS_SQUARE = (255, 122, 214, 255)

WHITE = (255, 255, 255, 255)


# --------------------------------------------------------------------------- #
#  Utilidades de mascara / composicao
# --------------------------------------------------------------------------- #

def _i(seq):
    """Pontos em unidades finais -> inteiros na resolucao de render (x SS)."""
    return [(int(round(x * SHAPE_SS)), int(round(y * SHAPE_SS))) for x, y in seq]


def _b(box):
    return [int(round(v * SHAPE_SS)) for v in box]


def canvas(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))


def mask_canvas(w: int, h: int) -> Image.Image:
    return Image.new("L", (int(w * SHAPE_SS), int(h * SHAPE_SS)), 0)


def smooth(m: Image.Image) -> Image.Image:
    """Mascara desenhada em SHAPE_SS -> resolucao final (bordas com anti-alias)."""
    if SHAPE_SS == 1:
        return m
    return m.resize((int(round(m.width / SHAPE_SS)), int(round(m.height / SHAPE_SS))),
                    Image.LANCZOS)


def vgrad(w: int, h: int, top, bottom) -> Image.Image:
    """Gradiente vertical RGBA em unidades finais (w, h)."""
    hh = h * SS
    strip = Image.new("RGBA", (1, hh))
    d = ImageDraw.Draw(strip)
    for y in range(hh):
        t = y / max(1, hh - 1)
        d.point((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4)))
    return strip.resize((w * SS, hh), Image.NEAREST)


def erode(m: Image.Image, r: int) -> Image.Image:
    return m.filter(ImageFilter.MinFilter(2 * r + 1)) if r > 0 else m


def dilate(m: Image.Image, r: int) -> Image.Image:
    return m.filter(ImageFilter.MaxFilter(2 * r + 1)) if r > 0 else m


def sub(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def paint(mask: Image.Image, color) -> Image.Image:
    """Mascara -> RGBA chapado."""
    color = color if len(color) == 4 else tuple(color) + (255,)
    layer = Image.new("RGBA", mask.size, color)
    layer.putalpha(ImageChops.multiply(mask, layer.getchannel("A")))
    return layer


def paint_grad(mask: Image.Image, top, bottom) -> Image.Image:
    g = vgrad(mask.size[0] // SS, mask.size[1] // SS, top, bottom)
    g.putalpha(ImageChops.multiply(mask, g.getchannel("A")))
    return g


def rounded(mask: Image.Image, box, radius: float, fill=255) -> None:
    x0, y0, x1, y1 = [int(v * SHAPE_SS) for v in box]
    ImageDraw.Draw(mask).rounded_rectangle(
        [x0, y0, x1 - 1, y1 - 1], radius=radius * SHAPE_SS, fill=fill)


def disc(mask: Image.Image, box, fill=255) -> None:
    ImageDraw.Draw(mask).ellipse([int(v * SHAPE_SS) for v in box], fill=fill)


def stroke(mask: Image.Image, pts, width: float, fill=255) -> None:
    """Linha grossa com pontas redondas (coordenadas em unidades finais)."""
    d = ImageDraw.Draw(mask)
    p = [(x * SHAPE_SS, y * SHAPE_SS) for x, y in pts]
    w = width * SHAPE_SS
    d.line(p, fill=fill, width=int(w), joint="curve")
    for x, y in (p[0], p[-1]):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def blur(layer: Image.Image, r: float) -> Image.Image:
    return layer.filter(ImageFilter.GaussianBlur(max(0.1, r) * SS))


def top_half(m: Image.Image, start: float = 0.22, end: float = 0.72) -> Image.Image:
    """Mascara vertical suave (255 no topo -> 0 embaixo) com smoothstep.
    Substitui o corte binario que deixava uma linha reta visivel no aro e no
    brilho dos simbolos."""
    w, h = m.size
    col = Image.new("L", (1, h))
    d = ImageDraw.Draw(col)
    for y in range(h):
        t = y / max(1, h - 1)
        if t <= start:
            v = 1.0
        elif t >= end:
            v = 0.0
        else:
            u = (end - t) / (end - start)
            v = u * u * (3 - 2 * u)
        d.point((0, y), int(round(255 * v)))
    return col.resize((w, h), Image.BILINEAR)


def _measure(f, text: str, tracking: float) -> float:
    return sum(f.getlength(c) for c in text) + tracking * max(0, len(text) - 1)


def fit_text_mask(text: str, w: int, h: int, tracking: float = 0.0,
                  width_frac: float = 0.86, height_frac: float = 0.46) -> Image.Image:
    """Texto em negrito ajustado a uma caixa (w, h em unidades finais)."""
    R = SHAPE_SS
    m = Image.new("L", (int(w * R), int(h * R)), 0)
    size = 10
    best = None
    while size < h * R * 3:
        f = ImageFont.truetype(FONT_BOLD, size)
        tw = _measure(f, text, tracking * R)
        asc, desc = f.getmetrics()
        if tw > w * R * width_frac or (asc + desc) > h * R * height_frac * 1.9:
            break
        best = (f, tw, asc, desc)
        size += 2
    if best is None:
        return m
    f, tw, asc, desc = best
    d = ImageDraw.Draw(m)
    x = (w * R - tw) / 2
    y = (h * R - (asc + desc)) / 2 - desc * 0.08
    for ch in text:
        d.text((x, y), ch, font=f, fill=255)
        x += f.getlength(ch) + tracking * R
    return smooth(m)

# --------------------------------------------------------------------------- #
#  "Vidro" - corpo base compartilhado por todos os botoes
# --------------------------------------------------------------------------- #

def glass_body(shape: Image.Image, accent, *, shadow: int = 18, glow: int = 40,
               rim: float = 2.6, top=GLASS_TOP, bottom=GLASS_BOT) -> Image.Image:
    """Botao de vidro escuro sobre `shape` (mascara L): halo, sombra projetada,
    corpo em gradiente, especular, profundidade e aro colorido."""
    w, h = shape.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # 1) halo colorido atras do botao
    if glow:
        halo_m = blur(dilate(shape, int(glow * SS * 0.30)), glow * 0.85)
        halo_m = halo_m.point(lambda v: int(v * 0.40))
        out.alpha_composite(paint(halo_m, accent[:3] + (255,)))

    # 2) sombra projetada (deslocada para baixo)
    sh = paint(dilate(shape, int(shadow * SS * 0.45)), INK)
    sh = sh.transform(sh.size, Image.AFFINE, (1, 0, 0, 0, 1, -int(shadow * SS * 0.55)),
                      resample=Image.BILINEAR)
    sh.putalpha(blur(sh, shadow * 0.45).getchannel("A").point(lambda v: int(v * 0.70)))
    out.alpha_composite(sh)

    # 3) corpo
    out.alpha_composite(paint_grad(shape, top, bottom))

    bw, bh = w / SS, h / SS

    # 4) especular superior
    spec = Image.new("L", (int(w), int(h)), 0)
    ImageDraw.Draw(spec).ellipse(
        [int(-bw * 0.10), int(-bh * 0.72), int(bw * 1.10), int(bh * 0.34)], fill=255)
    spec = ImageChops.multiply(spec, erode(shape, int(2 * SS)))
    s = paint(spec, WHITE)
    s.putalpha(blur(spec.point(lambda v: int(v * 0.20)), 16))
    out.alpha_composite(s)

    # 5) escurecimento inferior (profundidade)
    low = Image.new("L", (int(w), int(h)), 0)
    ImageDraw.Draw(low).ellipse(
        [int(-bw * 0.10), int(bh * 0.62), int(bw * 1.10), int(bh * 1.35)], fill=255)
    low = ImageChops.multiply(low, erode(shape, int(1.5 * SS)))
    lo = paint(low, INK)
    lo.putalpha(blur(low.point(lambda v: int(v * 0.26)), 20))
    out.alpha_composite(lo)

    # 6) aro: metade de cima na cor de destaque, metade de baixo escura
    band = sub(shape, erode(shape, int(rim * SS)))
    up = top_half(shape)
    ring_top = paint(ImageChops.multiply(band, up), accent[:3] + (255,))
    ring_top.putalpha(ImageChops.multiply(band, up).point(lambda v: int(v * 0.95)))
    out.alpha_composite(ring_top)
    down = ImageChops.invert(up)
    ring_bot = paint(ImageChops.multiply(band, down),
                     tuple(int(c * 0.38) for c in accent[:3]) + (255,))
    out.alpha_composite(ring_bot)

    # 7) bevel: luz interna logo abaixo do aro
    inner = erode(shape, int(rim * SS + 1.8 * SS))
    lip = ImageChops.multiply(sub(erode(shape, int(rim * SS)), inner), up)
    lc = paint(lip, WHITE)
    lc.putalpha(lip.point(lambda v: int(v * 0.32)))
    out.alpha_composite(lc)
    return out


def emboss_symbol(out: Image.Image, sym: Image.Image, color, *, inset: float = 1.0) -> None:
    """Grava o simbolo no vidro: sombra, gradiente, brilho no topo."""
    sd = paint(sym, INK)
    sd = sd.transform(sd.size, Image.AFFINE, (1, 0, 0, 0, 1, -int(3 * SS * inset)),
                      resample=Image.BILINEAR)
    sd.putalpha(blur(sd, 5 * inset).getchannel("A").point(lambda v: int(v * 0.55)))
    out.alpha_composite(sd)

    light = tuple(min(255, int(c * 1.30) + 24) for c in color[:3]) + (255,)
    dark = tuple(int(c * 0.52) for c in color[:3]) + (255,)
    out.alpha_composite(paint_grad(sym, light, dark))

    spec = ImageChops.multiply(sym, top_half(sym, 0.10, 0.62))
    sp = paint(spec, WHITE)
    sp.putalpha(blur(spec.point(lambda v: int(v * 0.42)), 6))
    out.alpha_composite(sp)


# --------------------------------------------------------------------------- #
#  Simbolos
# --------------------------------------------------------------------------- #

def sym_cross(size: int) -> Image.Image:
    m = mask_canvas(size, size)
    a, b = size * 0.315, size * 0.685
    stroke(m, [(a, a), (b, b)], size * 0.098)
    stroke(m, [(b, a), (a, b)], size * 0.098)
    return m


def sym_ring(size: int) -> Image.Image:
    outer = mask_canvas(size, size)
    inner = mask_canvas(size, size)
    disc(outer, [size * 0.29, size * 0.29, size * 0.71, size * 0.71])
    disc(inner, [size * 0.378, size * 0.378, size * 0.622, size * 0.622])
    return sub(outer, inner)


def sym_triangle(size: int) -> Image.Image:
    outer = mask_canvas(size, size)
    inner = mask_canvas(size, size)
    ImageDraw.Draw(outer).polygon(_i([
        (size * 0.5, size * 0.20),
        (size * 0.805, size * 0.735),
        (size * 0.195, size * 0.735)]), fill=255)
    ImageDraw.Draw(inner).polygon(_i([
        (size * 0.5, size * 0.385),
        (size * 0.695, size * 0.650),
        (size * 0.305, size * 0.650)]), fill=255)
    return sub(outer, inner)


def sym_square(size: int) -> Image.Image:
    outer = mask_canvas(size, size)
    inner = mask_canvas(size, size)
    rounded(outer, [size * 0.295, size * 0.295, size * 0.705, size * 0.705], size * 0.085)
    rounded(inner, [size * 0.295 + size * 0.078, size * 0.295 + size * 0.078,
                    size * 0.705 - size * 0.078, size * 0.705 - size * 0.078], size * 0.048)
    return sub(outer, inner)


def sym_chevron(size: int, direction: str) -> Image.Image:
    m = mask_canvas(size, size)
    w = size * 0.115
    if direction == "up":
        stroke(m, [(size * 0.30, size * 0.60), (size * 0.50, size * 0.375),
                   (size * 0.70, size * 0.60)], w)
    elif direction == "down":
        stroke(m, [(size * 0.30, size * 0.40), (size * 0.50, size * 0.625),
                   (size * 0.70, size * 0.40)], w)
    elif direction == "left":
        stroke(m, [(size * 0.60, size * 0.30), (size * 0.375, size * 0.50),
                   (size * 0.60, size * 0.70)], w)
    else:
        stroke(m, [(size * 0.40, size * 0.30), (size * 0.625, size * 0.50),
                   (size * 0.40, size * 0.70)], w)
    return m


def sym_diamond(size: int) -> Image.Image:
    m = mask_canvas(size, size)
    ImageDraw.Draw(m).polygon(_i(
        [(size * 0.5, size * 0.18), (size * 0.78, size * 0.5),
         (size * 0.5, size * 0.82), (size * 0.22, size * 0.5)]), fill=255)
    return m


def sym_hexagon(size: int) -> Image.Image:
    import math
    m = mask_canvas(size, size)
    pts = []
    for i in range(6):
        ang = math.radians(-90 + i * 60)
        pts.append((size * 0.5 + math.cos(ang) * size * 0.31,
                    size * 0.5 + math.sin(ang) * size * 0.31))
    ImageDraw.Draw(m).polygon(_i(pts), fill=255)
    return m


# --------------------------------------------------------------------------- #
#  Botoes
# --------------------------------------------------------------------------- #


def clamp_edges(img: Image.Image, inner: float = 0.93) -> Image.Image:
    """Aplica uma queda radial no alfa para o halo/sombra nao ser cortado pela
    borda do canvas (era isso que desenhava uma "placa quadrada" em volta do
    botao quando o app escalava a imagem)."""
    w, h = img.size
    N = 128
    m = Image.new("L", (N, N))
    px = m.load()
    cx, cy = (N - 1) / 2, (N - 1) / 2
    for y in range(N):
        for x in range(N):
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            r = (dx * dx + dy * dy) ** 0.5
            if r <= inner:
                v = 1.0
            elif r >= 1.0:
                v = 0.0
            else:
                u = (1.0 - r) / (1.0 - inner)
                v = u * u * (3 - 2 * u)
            px[x, y] = int(round(255 * v))
    mask = m.resize((w, h), Image.BICUBIC)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return img


def face(kind: str, color) -> Image.Image:
    m = mask_canvas(BASE, BASE)
    disc(m, [30, 30, BASE - 30, BASE - 30])
    out = glass_body(smooth(m), color, glow=40, shadow=18, rim=2.9)
    sym = smooth({"cross": sym_cross, "circle": sym_ring,
                  "triangle": sym_triangle, "square": sym_square}[kind](BASE))
    emboss_symbol(out, sym, color)
    return out

def dpad(direction: str) -> Image.Image:
    m = mask_canvas(BASE, BASE)
    rounded(m, [22, 22, BASE - 22, BASE - 22], BASE * 0.24)
    out = glass_body(smooth(m), MINT, glow=30, shadow=16, rim=2.4)
    emboss_symbol(out, smooth(sym_chevron(BASE, direction)), ICE)
    return out

def shoulder(label: str, accent) -> Image.Image:
    w, h = BASE, BASE // 2
    m = mask_canvas(w, h)
    rounded(m, [9, 14, w - 9, h - 14], h * 0.30)
    out = glass_body(smooth(m), accent, glow=26, shadow=14, rim=2.3)
    emboss_symbol(out, fit_text_mask(label, w, h, tracking=2.0, height_frac=0.50), ICE)
    return out

def utility(label: str, accent=MINT) -> Image.Image:
    w, h = BASE, BASE // 2
    m = mask_canvas(w, h)
    rounded(m, [26, 26, w - 26, h - 26], h * 0.34)
    out = glass_body(smooth(m), accent, glow=22, shadow=12, rim=2.1)
    emboss_symbol(out, fit_text_mask(label, w, h, tracking=3.5, height_frac=0.42), ICE)
    return out

def stick_click(label: str) -> Image.Image:
    m = mask_canvas(BASE, BASE)
    disc(m, [40, 40, BASE - 40, BASE - 40])
    out = glass_body(smooth(m), GOLD, glow=26, shadow=16, rim=2.6)
    emboss_symbol(out, fit_text_mask(label, BASE, BASE, tracking=1.0, height_frac=0.40), GOLD)
    return out

def macro(index: int) -> Image.Image:
    out = glass_body(smooth(sym_hexagon(BASE)), PLUMBOB, glow=30, shadow=16, rim=2.4)
    emboss_symbol(out, fit_text_mask(f"M{index}", BASE, BASE, tracking=1.0,
                                    height_frac=0.38), PLUMBOB)
    return out

def analog_base() -> Image.Image:
    outer = mask_canvas(BASE, BASE)
    inner = mask_canvas(BASE, BASE)
    disc(outer, [26, 26, BASE - 26, BASE - 26])
    disc(inner, [BASE * 0.215, BASE * 0.215, BASE * 0.785, BASE * 0.785])
    ring = smooth(sub(outer, inner))
    out = glass_body(ring, MINT, glow=30, shadow=14, rim=2.4,
                     top=(34, 46, 48, 255), bottom=(14, 20, 22, 255))
    ticks = mask_canvas(BASE, BASE)
    import math
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        cx = cy = BASE * 0.5
        r1 = BASE * 0.205
        ImageDraw.Draw(ticks).line([(int(cx * SHAPE_SS), int(cy * SHAPE_SS)),
                    (int((cx + math.cos(a) * r1) * SHAPE_SS),
                     int((cy + math.sin(a) * r1) * SHAPE_SS))],
                   fill=255, width=int(BASE * 0.013 * SHAPE_SS))
    t = ImageChops.multiply(smooth(ticks), ring).point(lambda v: int(v * 0.80))
    out.alpha_composite(paint(t, MINT))
    return out

def analog_stick() -> Image.Image:
    m = mask_canvas(BASE, BASE)
    disc(m, [28, 28, BASE - 28, BASE - 28])
    out = glass_body(smooth(m), MINT, glow=36, shadow=22, rim=2.6,
                     top=(64, 84, 86, 255), bottom=(16, 24, 26, 255))
    emboss_symbol(out, smooth(sym_diamond(BASE)), PLUMBOB, inset=0.8)
    return out

# --------------------------------------------------------------------------- #
#  Montagem
# --------------------------------------------------------------------------- #

BUTTONS = {
    "cross": lambda: face("cross", PS_CROSS),
    "circle": lambda: face("circle", PS_CIRCLE),
    "triangle": lambda: face("triangle", PS_TRIANGLE),
    "square": lambda: face("square", PS_SQUARE),
    "up": lambda: dpad("up"),
    "down": lambda: dpad("down"),
    "left": lambda: dpad("left"),
    "right": lambda: dpad("right"),
    "l1": lambda: shoulder("L1", MINT),
    "l2": lambda: shoulder("L2", GOLD),
    "r1": lambda: shoulder("R1", MINT),
    "r2": lambda: shoulder("R2", GOLD),
    "l3": lambda: stick_click("L3"),
    "r3": lambda: stick_click("R3"),
    "start": lambda: utility("START"),
    "select": lambda: utility("SELECT"),
    "macro1": lambda: macro(1),
    "macro2": lambda: macro(2),
    "macro3": lambda: macro(3),
    "macro4": lambda: macro(4),
}

SQUARE_ONLY = {
    "analog_base": analog_base,
    "analog_stick": analog_stick,
}


def filename_for(key: str) -> str:
    if key in ("analog_base", "analog_stick"):
        return f"ic_controller_{key}.png"
    return f"ic_controller_{key}_button.png"


def build_all(verbose: bool = True) -> dict:
    imgs = {}
    for key, fn in BUTTONS.items():
        imgs[key] = clamp_edges(fn())
        if verbose:
            print(f"  {filename_for(key):38s} {imgs[key].size}")
    for key, fn in SQUARE_ONLY.items():
        imgs[key] = clamp_edges(fn())
        if verbose:
            print(f"  {filename_for(key):38s} {imgs[key].size}")
    return imgs


def save(imgs: dict, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for key, img in imgs.items():
        p = os.path.join(out_dir, filename_for(key))
        img.save(p, "PNG", optimize=True)
        paths.append(p)
    return paths


def preview(imgs: dict, path: str) -> str:
    """Mockup 1920x1080 com o controle montado, para conferir o visual."""
    W, H = 1920, 1080
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    g = vgrad(W, H, (18, 32, 30, 255), (4, 8, 9, 255))
    bg.alpha_composite(g)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.18, -H * 0.35, W * 0.82, H * 0.95],
                                 fill=(46, 150, 96, 90))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))

    def put(key, cx, cy, size):
        img = imgs[key]
        s = size / max(img.size)
        w, h = int(img.size[0] * s), int(img.size[1] * s)
        bg.alpha_composite(img.resize((w, h), Image.LANCZOS), (int(cx - w / 2), int(cy - h / 2)))

    put("l2", 190, 92, 210)
    put("l1", 190, 214, 230)
    put("r2", W - 190, 92, 210)
    put("r1", W - 190, 214, 230)

    dcx, dcy, step = 250, 800, 168
    put("up", dcx, dcy - step, 176)
    put("down", dcx, dcy + step, 176)
    put("left", dcx - step, dcy, 176)
    put("right", dcx + step, dcy, 176)

    fcx, fcy, fstep = W - 250, 800, 168
    put("triangle", fcx, fcy - fstep, 168)
    put("cross", fcx, fcy + fstep, 168)
    put("square", fcx - fstep, fcy, 168)
    put("circle", fcx + fstep, fcy, 168)

    put("analog_base", 640, 905, 300)
    put("analog_stick", 640, 905, 190)
    put("analog_base", W - 640, 905, 300)
    put("analog_stick", W - 640, 905, 190)

    put("select", W / 2 - 105, 1012, 140)
    put("start", W / 2 + 105, 1012, 140)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    bg.convert("RGB").save(path, "PNG", optimize=True)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="skin/src")
    ap.add_argument("--preview", default="docs/preview.png")
    args = ap.parse_args()
    print("Gerando Plumbob Glass...")
    imgs = build_all()
    paths = save(imgs, args.out)
    print(f"{len(paths)} PNGs em {args.out}")
    if args.preview:
        print("preview:", preview(imgs, args.preview))


if __name__ == "__main__":
    main()

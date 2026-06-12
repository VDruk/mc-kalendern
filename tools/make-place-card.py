#!/usr/bin/env python3
"""
make-place-card.py - compose a Plats (place) card FRONT image with text baked in.

Place-card front text has THREE elements, and their positions are FIXED so that
a row of cards lines up horizontally:
  1. NAME      - big white Poppins-Bold. Auto-fits to 1 line, wraps to 2 if needed.
                 The name is BOTTOM-anchored: it grows UPWARD from the separator,
                 so 1 vs 2 lines never moves the separator or the city.
  2. SEPARATOR - short cyan line at a FIXED y (SEP_FRAC). Same spot on every card.
  3. CITY      - small letter-spaced caps (one word) at a FIXED y (CITY_FRAC).
A "PLATS" badge sits top-right. A bottom gradient keeps the text readable on photos.

Fixed anchors were measured from the existing cards (ad-nilssons-mc-front.jpg,
ad-italia-bike-center-arboga-front.jpg): city at 0.924 of height, separator just
above it. Keep these constant so all photo place cards align.

Usage:
  python3 tools/make-place-card.py INPUT_PHOTO "Place Name" "CITY" ads/out-front.jpg
  (INPUT_PHOTO may be any aspect ratio; it is center-cropped to 800x1067.)
"""
import sys, os
from PIL import Image, ImageOps, ImageDraw, ImageFont

W, H = 800, 1067
SEP_FRAC  = 0.884   # separator vertical center (FIXED)
CITY_FRAC = 0.924   # city text vertical center (FIXED)
NAME_GAP  = 22      # px between name bottom and separator
CYAN  = (34, 211, 238, 255)
WHITE = (255, 255, 255, 255)
CITYC = (209, 220, 231, 255)   # light cool gray, measured from existing cards
FONT  = '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'     # name (bold) - matches site system font (Helvetica/SF)
FONT_CITY = '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'  # city (regular weight)


def fit_name(draw, text, max_w, start=52, min_size=30):
    """Return (lines, font). One line if it fits; else wrap to 2 lines; shrink to fit."""
    for size in range(start, min_size - 1, -2):
        f = ImageFont.truetype(FONT, size)
        if draw.textlength(text, font=f) <= max_w:
            return [text], f
    # need 2 lines: split near the middle on a space
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        for size in range(start, min_size - 1, -2):
            f = ImageFont.truetype(FONT, size)
            if draw.textlength(a, font=f) <= max_w and draw.textlength(b, font=f) <= max_w:
                w = max(draw.textlength(a, font=f), draw.textlength(b, font=f))
                if best is None or size > best[0]:
                    best = (size, [a, b], f)
                break
    if best:
        return best[1], best[2]
    f = ImageFont.truetype(FONT, min_size)
    return [text], f


def make(photo, name, city, out):
    src = Image.open(photo).convert('RGB')
    base = ImageOps.fit(src, (W, H), Image.LANCZOS, centering=(0.5, 0.5)).convert('RGBA')
    # bottom gradient for readability
    grad = Image.new('L', (1, H), 0)
    g0 = int(H * 0.60)
    for y in range(H):
        t = max(0, (y - g0) / (H - g0))
        grad.putpixel((0, y), int(230 * (t ** 1.3)))
    shade = Image.new('RGBA', (W, H), (8, 10, 24, 255)); shade.putalpha(grad.resize((W, H)))
    base = Image.alpha_composite(base, shade)
    d = ImageDraw.Draw(base)

    sep_y  = round(H * SEP_FRAC)
    city_y = round(H * CITY_FRAC)

    # NAME: bottom-anchored above the separator (grows upward)
    lines, fname = fit_name(d, name, W - 80)
    asc, desc = fname.getmetrics(); lh = asc + desc
    name_bottom = sep_y - NAME_GAP
    y = name_bottom - lh * len(lines)
    for ln in lines:
        w = d.textlength(ln, font=fname)
        d.text(((W - w) / 2, y), ln, font=fname, fill=WHITE)
        y += lh

    # SEPARATOR (fixed)
    d.line([(W // 2 - 38, sep_y), (W // 2 + 38, sep_y)], fill=CYAN, width=3)

    # CITY (fixed, letter-spaced caps) - lighter weight + muted gray to match other cards
    fcity = ImageFont.truetype(FONT_CITY, 22)
    reg = city.upper(); track = 6
    widths = [d.textlength(ch, font=fcity) for ch in reg]
    total = sum(widths) + track * (len(reg) - 1)
    x = (W - total) / 2
    ca, cd = fcity.getmetrics()
    cy = city_y - (ca + cd) / 2
    for ch, w in zip(reg, widths):
        d.text((x, cy), ch, font=fcity, fill=CITYC); x += w + track

    # PLATS badge top-right
    fp = ImageFont.truetype(FONT, 20); pt = 'PLATS'
    pw = d.textlength(pt, font=fp); pa, pd_ = fp.getmetrics(); ph = pa + pd_
    padx, pady = 14, 7; bx2 = W - 18; bx1 = bx2 - (pw + padx * 2); by1 = 20; by2 = by1 + ph + pady * 2
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=(by2 - by1) // 2, fill=(10, 14, 26, 235))
    d.text((bx1 + padx, by1 + pady), pt, font=fp, fill=CYAN)

    base.convert('RGB').save(out, 'JPEG', quality=86, optimize=True, progressive=True)
    print('wrote', out, os.path.getsize(out) // 1024, 'KB |', len(lines), 'name line(s)')


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(__doc__); sys.exit(1)
    make(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

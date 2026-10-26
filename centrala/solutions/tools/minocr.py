"""Mini-OCR skanów generowanych przez gen_common.text_image.

Skan jest renderowany monospace (jeden znak na komórkę o stałej szerokości),
więc segmentacja sprowadza się do wyznaczenia przebiegów atramentu, a
rozpoznanie znaku — do dopasowania wzorca wyrównanego do linii bazowej
(metryka Jaccarda na maskach atramentu).

W wersji produkcyjnej (prawdziwe skany) używa się Tesseracta/easyocr lub VLM.
"""
from __future__ import annotations

import io
import statistics

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT = ImageFont.load_default(size=16)   # ten sam font/size co gen_common.text_image
CHARSET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:;/-_#()[]%+")
INK = 160
PAD = 60


def _ink_bbox(img: "Image.Image"):
    return ImageOps.invert(img).getbbox()


def _threshold_bbox(px, w, h):
    """Bounding box liczony po progu atramentu (identycznie jak dla skanu)."""
    cols = [x for x in range(w) if any(px[y * w + x] < INK for y in range(h))]
    rows = [y for y in range(h) if any(px[y * w + x] < INK for x in range(w))]
    if not cols or not rows:
        return None
    return min(cols), min(rows), max(cols) + 1, max(rows) + 1


def _glyph(ch: str):
    im = Image.new("L", (PAD, PAD), 255)
    ImageDraw.Draw(im).text((4, 4), ch, fill=0, font=FONT)
    px = list(im.getdata())
    bb = _threshold_bbox(px, PAD, PAD)
    if not bb:
        return None
    crop = im.crop(bb)
    return list(crop.getdata()), crop.width, crop.height


_TEMPLATES: dict[str, tuple[list[int], int, int]] = {}
for _c in CHARSET:
    _g = _glyph(_c)
    if _g:
        _TEMPLATES[_c] = _g

CAP1X = _TEMPLATES["H"][2]     # wysokość wielkiej litery w 1x (bez nawiasów/descenderów)


def _place(pixels, w, h, cw, ch) -> list[int]:
    """Wstawia bitmapę glifu na kanwę (przycina to, co nie mieści się)."""
    out = [255] * (cw * ch)
    y_off = ch - h
    for y in range(h):
        ty = y + y_off
        if not (0 <= ty < ch):
            continue
        for x in range(min(w, cw)):
            out[ty * cw + x] = pixels[y * w + x]
    return out


def _mask(pixels) -> list[int]:
    return [1 if p < INK else 0 for p in pixels]


def _jaccard(a, b) -> float:
    inter = union = 0
    for x, y in zip(a, b):
        if x or y:
            union += 1
            if x and y:
                inter += 1
    return 1.0 - (inter / union if union else 0.0)


def _runs(profile) -> list[tuple[int, int]]:
    out, i, n = [], 0, len(profile)
    while i < n:
        if profile[i] == 0:
            i += 1
            continue
        j = i
        while j < n and profile[j] > 0:
            j += 1
        out.append((i, j))
        i = j
    return out


def decode_image(payload: bytes, debug: bool = False) -> list[str]:
    img = Image.open(io.BytesIO(payload)).convert("L")
    w, h = img.size
    px = list(img.getdata())
    ink = [[1 if px[y * w + x] < INK else 0 for x in range(w)] for y in range(h)]
    rows = [sum(r) for r in ink]
    lines = [b for b in _runs(rows) if b[1] - b[0] >= 4]
    out_lines: list[str] = []

    for (y0, y1) in lines:
        colink = [sum(ink[y][x] for y in range(y0, y1)) for x in range(w)]
        runs = _runs(colink)
        if not runs:
            continue
        starts = [a for a, _b in runs]
        diffs = [b - a for a, b in zip(starts, starts[1:]) if b - a > 2]
        raw_cell = statistics.median(diffs) if diffs else 0

        best_line, best_cost = None, None
        for scale in (1, 2, 3, 4):
            cw, chh = 10 * scale + 2, CAP1X * scale + 3
            templates = {c: _mask(_place(_up(p, tw, th, scale), tw * scale, th * scale, cw, chh))
                         for c, (p, tw, th) in _TEMPLATES.items()}
            cell = raw_cell or 10 * scale
            parts: list[str] = []
            prev_start = None
            prev_count = 1
            cost = 0.0
            for (x0, x1) in runs:
                if prev_start is not None:
                    step = x0 - prev_start
                    n_sp = max(0, int(round(step / cell)) - prev_count)
                    if n_sp:
                        parts.append(" " * n_sp)
                rows_ink = [y for y in range(y0, y1) if any(ink[y][x] for x in range(x0, x1))]
                gy0, gy1 = min(rows_ink), max(rows_ink) + 1
                # przebieg może zawierać kilka glifów (sąsiednie znaki stykają się) -
                # podział wyznaczamy dynamicznie, minimalizując sumę odległości
                k = max(1, int(round((x1 - x0) / (cell * 0.85))))

                def segment_cost(xs: int, xe: int):
                    cols_ink = [x for x in range(xs, xe)
                                if any(ink[y][x] for y in range(gy0, gy1))]
                    if not cols_ink:
                        return None
                    bx0, bx1 = min(cols_ink), max(cols_ink) + 1
                    sub = img.crop((bx0, gy0, bx1, gy1))
                    vec = _mask(_place(list(sub.getdata()), bx1 - bx0, gy1 - gy0, cw, chh))
                    cand = min(templates.items(), key=lambda kv: _jaccard(kv[1], vec))
                    return _jaccard(cand[1], vec), cand[0]

                memo: dict[tuple[int, int], tuple[float, list[str]]] = {}

                def cover(xs: int, left: int):
                    if (xs, left) in memo:
                        return memo[(xs, left)]
                    if left == 1:
                        seg = segment_cost(xs, x1)
                        res = (seg[0], [seg[1]]) if seg else (1.0, [""])
                    else:
                        res = (1e9, [""])
                        for xe in range(xs + 3, x1 - 3 * (left - 1) + 1):
                            seg = segment_cost(xs, xe)
                            if seg is None:
                                continue
                            rest = cover(xe, left - 1)
                            cand = (seg[0] + rest[0], [seg[1]] + rest[1])
                            if cand[0] < res[0]:
                                res = cand
                    memo[(xs, left)] = res
                    return res

                seg_cost, chars = cover(x0, k)
                cost += seg_cost / max(1, k)
                parts.extend(chars)
                prev_count = max(1, len(chars))
                if debug:
                    print(f"    s={scale} [{x0},{x1}] k={k} -> {''.join(chars)!r} d={seg_cost:.2f}")
                prev_start = x0
            cost /= len(runs)
            if best_cost is None or cost < best_cost:
                best_cost, best_line = cost, "".join(parts).strip()
        out_lines.append(best_line or "")
    return out_lines


def _up(pixels, w, h, s: int):
    if s <= 1:
        return pixels
    im = Image.new("L", (w, h), 255)
    im.putdata(pixels)
    im = im.resize((w * s, h * s), Image.NEAREST)
    return list(im.getdata())


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from gen_common import text_image
    tests = ["SEKTOR C2: znaleziono slady dwoch osob", "ZGLOSZENIE 441",
             "Tablica rejestracyjna: AGREGAT", "naprawa czujnika dymu",
             "RAPORT DZIENNY 2024_11_12"]
    ok = 0
    for t in tests:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ocr_test.png")
        text_image(p, [t])
        got = " ".join(decode_image(open(p, "rb").read()))
        good = got.upper().replace(" ", "") == t.upper().replace(" ", "")
        ok += good
        print(f"{'OK ' if good else '   '} {t!r:45} -> {got!r}")
    print(f"skuteczność: {ok}/{len(tests)}")

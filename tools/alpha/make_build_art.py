"""Makes the BUILD screen's artwork (launcher/assets/build-forest.pack) and the launcher pages' scenery
(launcher/assets/launcher-forest.pack) and the game's start-up picture (startup-logo.png, engine/assets/ocarina_reborn.png)
from the reference pictures.

    python make_build_art.py [--src art-src/build-forest-reference.png] [--out launcher/assets/build-forest.pack]
                             [--preview <folder>]

The reference (art-src/build-forest-reference.png, 1672 x 941, supplied by the project owner) is one flattened picture
with the interface painted into it. The build screen needs the scenery WITHOUT the live parts, because those are drawn
by the launcher from the build's real progress: this tool takes them out and keeps everything that never changes.

    removed (filled from the surrounding picture)   the percentage and the bar's fill, the file counter, the six step
                                                    icons and labels, the active row's highlight, the status text and its
                                                    icon, the two button labels and icons, the window button glyphs
    replaced                                        the bar's inside: an empty track continued from the reference's own
                                                    empty part (its right end)
    kept                                            the forest, the Ocarina, the title, BUILD, the bar's gold frame and
                                                    gems, the row lines, the status panel and the two button frames

Besides the cleared scenery the pack holds the masks the animation needs (the title's letters for the highlight, the
green letters for their glow, the Ocarina's outline for the energy rings passing behind it) and every position, in the
reference's pixels (the launcher scales them to the window). Developer tool: Pillow is needed here, not in the launcher.
"""
import argparse
import json
import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
W, H = 1672, 941

# ---- positions in the reference (measured from it; build_screen.py draws its live parts at the same places)
GEOM = {
    'size': [W, H],
    'bar': [293, 426, 1377, 489],            # the inside of the gold frame (a capsule)
    'bar_box': [284, 404, 1386, 512],        # what the animated bar re-renders (frame and gems included, from the art)
    'gems': [[836, 418, 15], [836, 493, 17]],   # the frame's two centre gems: the fill passes under them
    'pct': [836, 457],                       # centre of the percentage
    'pct_diamonds': [[749, 457], [924, 457]],
    'counter': [1342, 513],                  # right end, middle of the file / shader counter
    'rows': [536.5, 568, 600.5, 633, 667.5, 705.5],
    'row_icon_x': 542,
    'row_label_x': 588,
    'row_pct_x': 1140,
    'row_lines': [[565, 1153]],              # where the thin lines between the rows run (kept in the art)
    'active': [518, 687, 1157, 724],         # the active row's highlight (the last row's place in the reference)
    'panel': [455, 766, 1217, 816],          # the status panel's inside
    'panel_icon': [577, 791],
    'panel_text': [604, 791],
    'btn_left': [165, 815, 402, 869],
    'btn_right': [1270, 815, 1505, 869],
    'btn_left_icon': [221, 842], 'btn_left_label': [250, 842],
    'btn_right_icon': [1331, 842], 'btn_right_label': [1368, 842],
    'winctl': [[1549, 21], [1597, 21], [1645, 21]],
    'winctl_box': [1525, 0, 1672, 44],
    'logo': [430, 212, 1245, 352],           # "Ocarina Reborn" (with its swirls)
    'ocarina': [640, 8, 1085, 285],          # the instrument
    'rings': [[860, 189, 311, 69, -5.7], [858, 192, 334, 80, -5.7]],   # the painted energy rings (fitted): centre, half axes, tilt
    'glow': [826, 150, 300, 150],            # the Ocarina's blue glow: centre, half axes
    'rays': [[1150, 0, 1672, 520], [0, 0, 420, 330]],   # where sunlight falls through the leaves
    'flowers': [[95, 600], [150, 640], [60, 700], [1520, 700], [1560, 640], [1450, 760], [215, 715], [1600, 560]],
}


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def box_mask(shape, boxes):
    m = np.zeros(shape, bool)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = True
    return m


def dilate(m, r):
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.asarray(img) > 127


def bright_mask(a, box, over=38, r=2):
    """the text / icon pixels inside box: clearly brighter (or more saturated) than the box's own background"""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    L = lum(sub)
    base = np.asarray(Image.fromarray(L.astype(np.uint8)).filter(ImageFilter.MedianFilter(15)), np.float32)
    sat = sub.max(-1) - sub.min(-1)
    m = (L > base + over) | ((sat > 90) & (L > base + 15))
    full = np.zeros(a.shape[:2], bool)
    full[y0:y1, x0:x1] = m
    return dilate(full, r)


def inpaint(a, hole, rounds=1):
    """fills hole from the pixels around it: a pull-push pyramid (every level the average of the known pixels, the coarse
    levels filling what the fine ones do not know), then the fill lightly smoothed and given the area's own fine grain"""
    img = a.astype(np.float32)
    w = (~hole).astype(np.float32)
    levels = []
    c, ww = img * w[..., None], w
    while min(ww.shape) > 4:
        levels.append((c, ww))
        h2, w2 = ww.shape[0] // 2 * 2, ww.shape[1] // 2 * 2
        c = c[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2, 3).sum((1, 3))
        ww = ww[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).sum((1, 3))
    est = c / np.maximum(ww, 1e-6)[..., None]
    for c, ww in reversed(levels):
        hh, wd = ww.shape
        up = np.asarray(Image.fromarray(np.clip(est, 0, 255).astype(np.uint8)).resize((wd, hh), Image.BILINEAR),
                        np.float32)
        known = c / np.maximum(ww, 1e-6)[..., None]
        t = np.clip(ww, 0, 1)[..., None]
        est = known * t + up * (1 - t)
    out = img.copy()
    soft = np.asarray(Image.fromarray(np.clip(est, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)),
                      np.float32)
    rng = np.random.default_rng(7)
    grain = rng.normal(0, 2.2, soft.shape[:2])[..., None]
    out[hole] = np.clip(soft + grain, 0, 255)[hole]
    # (the fill's edge eased into the picture: no seam)
    edge = np.asarray(Image.fromarray((hole * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                      np.float32)[..., None] / 255
    edge = np.where(hole[..., None], 1.0, edge)
    return img * (1 - edge) + out * edge


def capsule(shape, box, r, ss=4):
    """anti-aliased capsule mask (1 inside)"""
    x0, y0, x1, y1 = box
    hh, ww = shape
    ys = (np.arange(hh * ss) + 0.5) / ss
    xs = (np.arange(ww * ss) + 0.5) / ss
    cy = (y0 + y1) / 2
    cx = np.clip(xs, x0 + r, x1 - r)
    d = np.sqrt((xs[None, :] - cx[None, :]) ** 2 + (ys[:, None] - cy) ** 2)
    m = (d <= r).astype(np.float32)
    return m.reshape(hh, ss, ww, ss).mean((1, 3))


def diamond(shape, cx, cy, h):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (np.abs(xx - cx) + np.abs(yy - cy)) <= h


def clear(a):
    g = GEOM
    hole = np.zeros(a.shape[:2], bool)
    # the counter, the status text and icon, the button labels and icons, the window glyphs
    hole |= bright_mask(a, (1215, 500, 1352, 526), over=18, r=3)
    hole |= bright_mask(a, (1536, 8, 1660, 35), over=20, r=3)
    # the six rows as a whole (icons, labels, the active row's highlight); their thin lines are drawn again below
    hole |= box_mask(a.shape[:2], [(512, 518, 1166, 731)])
    out = inpaint(a, hole)
    # the status panel's and the buttons' insides: their own top-to-bottom shading, continued across where the text was
    for box in ((540, 774, 1105, 809), (190, 829, 382, 856), (1300, 829, 1478, 856)):
        out = vfill(out, box)
        hole |= box_mask(a.shape[:2], [box])
    out = row_lines(out)
    return out, hole


def fill_soft(out, box, feather=14):
    """box filled from its surroundings (inpaint) with a fine grain, eased in at the box's edges (no hard seam)"""
    x0, y0, x1, y1 = box
    h, w = y1 - y0, x1 - x0
    hole = np.zeros(out.shape[:2], bool)
    hole[y0:y1, x0:x1] = True
    smooth = inpaint(np.clip(out, 0, 255), hole)[y0:y1, x0:x1]
    fill = smooth + np.random.default_rng(x0 + y0).normal(0, 2.0, (h, w, 1))
    yy, xx = np.mgrid[0:h, 0:w]
    f = (np.clip(np.minimum(xx + 0.5, w - xx - 0.5) / feather, 0, 1) *
         np.clip(np.minimum(yy + 0.5, h - yy - 0.5) / 5, 0, 1))[..., None]   # (softer at the sides than above and below)
    out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - f) + fill * f
    return out


def vfill(out, box, k=31, feather=16):
    """box filled column by column between the pixels just above and just below it, smoothed along the row (over k)"""
    x0, y0, x1, y1 = box
    top = out[y0 - 2:y0, x0 - 20:x1 + 20].mean(0)
    bot = out[y1:y1 + 2, x0 - 20:x1 + 20].mean(0)
    ker = np.ones(k) / k
    sm = lambda v: np.stack([np.convolve(np.pad(v[:, c], k // 2, mode='edge'), ker, 'valid') for c in range(3)], -1)
    top, bot = sm(top)[20:-20], sm(bot)[20:-20]
    t = ((np.arange(y1 - y0) + 0.5) / (y1 - y0))[:, None, None]
    rng = np.random.default_rng(3)
    fill = top[None] * (1 - t) + bot[None] * t + rng.normal(0, 1.2, (y1 - y0, x1 - x0, 1))
    # (eased in over its first and last 16 columns, which hold no text: no edge where the fill begins)
    xs = np.arange(x1 - x0)
    f = np.clip(np.minimum(xs + 0.5, (x1 - x0) - xs - 0.5) / feather, 0, 1)[None, :, None]
    out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - f) + fill * f
    return out


ROW_LINES = [552, 584.5, 617.5, 650, 684.5]


def row_lines(out):
    """the thin lines between the rows, as the reference has them: a 1 px teal line with a faint halo, x 572..1155,
    fading in and out at its ends"""
    x0, x1 = 572, 1155
    xs = np.arange(x0 - 12, x1 + 12)
    fade = np.clip(np.minimum(xs - (x0 - 12), (x1 + 12) - xs) / 24, 0, 1)[:, None]
    core, halo = np.array([36, 62, 67], np.float32), np.array([15, 40, 43], np.float32)
    for y in ROW_LINES:
        for dy, col, k in ((0, core, 0.95), (-1, halo, 0.55), (1, halo, 0.45)):
            yy = int(round(y + dy))
            seg = out[yy, xs]
            out[yy, xs] = seg * (1 - k * fade) + col * k * fade
    return out


def track(out, a):
    """the bar's inside, empty: the reference's own empty end (x 1290..1370) continued along the bar"""
    g = GEOM
    x0, y0, x1, y1 = g['bar']
    r = (y1 - y0) / 2
    m = capsule(out.shape[:2], g['bar'], r)
    for cx, cy, h in g['gems']:
        m[diamond(m.shape, cx, cy, h + 3)] = 0
    col = a[y0 - 2:y1 + 3, 1292:1368].astype(np.float32).mean(1)          # the vertical profile
    rng = np.random.default_rng(11)
    tex = np.repeat(col[:, None, :], x1 - x0 + 2, 1)
    tex += rng.normal(0, 1.4, tex.shape[:2])[..., None]
    region = out[y0 - 2:y1 + 3, x0 - 1:x1 + 1]
    mm = m[y0 - 2:y1 + 3, x0 - 1:x1 + 1][..., None]
    region[:] = region * (1 - mm) + tex[:, :region.shape[1]] * mm
    return m


def masks(a):
    g = GEOM
    x0, y0, x1, y1 = g['logo']
    sub = a[y0:y1, x0:x1].astype(np.float32)
    L = lum(sub)
    letters = np.clip((L - 120) / 90, 0, 1)
    green = np.clip(((sub[..., 1] - sub[..., 0]) - 40) / 60, 0, 1) * np.clip((sub[..., 1] - 110) / 60, 0, 1)
    ox0, oy0, ox1, oy1 = g['ocarina']
    o = a[oy0:oy1, ox0:ox1].astype(np.float32)
    body = (o[..., 2] > 85) & (o[..., 2] > o[..., 0] + 45) & (o[..., 2] > o[..., 1] + 10) & (lum(o) < 200)
    collar = (o[..., 0] > 120) & (o[..., 1] > 90) & (o[..., 2] < 140) & (o[..., 0] > o[..., 2] + 30)
    occ = (body | collar)
    img = Image.fromarray((occ * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    # (only the instrument itself: the largest blob)
    occ = np.asarray(img.filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
    return letters, green, occ


# ---- the pack: a small header, a JSON index, zlib blobs (read by build_screen.py with numpy only)
def write_pack(path, arrays, meta):
    index, blobs, off = {}, [], 0
    for name, arr in arrays.items():
        arr = np.ascontiguousarray(arr)
        b = zlib.compress(arr.tobytes(), 9)
        index[name] = dict(dtype=str(arr.dtype), shape=list(arr.shape), offset=off, length=len(b))
        blobs.append(b)
        off += len(b)
    head = json.dumps(dict(index=index, geom=meta), separators=(',', ':')).encode()
    path.write_bytes(b'OCRPACK1' + struct.pack('<I', len(head)) + head + b''.join(blobs))


# ---- the launcher's pages (art-src/launcher-forest-reference.png, 1536 x 1024: the main page as the owner drew it)
LAUNCHER_BANNER = (32, 78, 1504, 292)   # the forest with the Ocarina and the title, under the window's top row
LAUNCHER_FLOOR = (0, 968, 1536, 1024)   # the plants along the bottom edge


def launcher_pack(src, out):
    """the launcher's scenery: its banner and its floor, cut from the reference where no interface lies on them; every
    panel, button and frame of the pages is drawn by ui.py"""
    a = np.asarray(Image.open(src).convert('RGB'))
    if a.shape[:2] != (1024, 1536):
        raise SystemExit('the launcher reference must be 1536 x 1024')
    x0, y0, x1, y1 = LAUNCHER_BANNER
    banner = a[y0:y1, x0:x1].copy()
    x0, y0, x1, y1 = LAUNCHER_FLOOR
    floor = a[y0:y1, x0:x1].copy()
    write_pack(out, dict(banner=banner, floor=floor), dict(banner=LAUNCHER_BANNER, floor=LAUNCHER_FLOOR, size=[1536, 1024]))
    print(f'{out}: {out.stat().st_size // 1024} KB')


# ---- the game's start-up screen (art-src/start-forest-reference.png, 1672 x 941: what shows after Play). The game draws
# it (engine/gpu/vk/vk_menu.cpp draw_startup) from engine/assets/ocarina_reborn.png: this picture without its live parts
START_BAR = (298, 659, 1369, 737)        # the bar's inside (a capsule); vk_menu.cpp kStartBar
START_GEMS = [(835, 650, 14), (835, 744, 16)]


def png_rgba(path, rgb):
    """an 8-bit RGBA PNG, every row unfiltered: nx2/logo_rgba.py decodes it byte by byte, and unfiltered rows are its
    quickest case"""
    h, w = rgb.shape[:2]
    a = np.dstack([rgb, np.full((h, w), 255, np.uint8)])
    raw = np.zeros((h, w * 4 + 1), np.uint8)
    raw[:, 1:] = a.reshape(h, w * 4)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    path.write_bytes(bytes([0x89]) + b'PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(raw.tobytes(), 9)) + chunk(b'IEND', b''))


def start_picture(src, outs):
    a = np.asarray(Image.open(src).convert('RGB'))
    if a.shape[:2] != (H, W):
        raise SystemExit(f'the start reference must be {W} x {H}')
    # "BUILD" (the game writes START) and the steps' icons and names: each filled column by column from just above and
    # below it, eased in at its sides (a smooth patch would show as a darker box on the stone and the moss)
    out = a.astype(np.float32)
    for box in ((684, 560, 992, 612), (276, 780, 606, 852), (684, 780, 1014, 852), (1104, 780, 1386, 852)):
        out = fill_soft(out, box, feather=18)
    x0, y0, x1, y1 = START_BAR   # (the bar's inside: the reference's own empty end continued along it)
    r = (y1 - y0) / 2
    m = capsule(out.shape[:2], START_BAR, r)
    for cx, cy, gh in START_GEMS:
        m[diamond(m.shape, cx, cy, gh + 3)] = 0
    col = a[y0 - 2:y1 + 3, 1295:1360].astype(np.float32).mean(1)
    rng = np.random.default_rng(13)
    tex = np.repeat(col[:, None, :], x1 - x0 + 2, 1) + rng.normal(0, 1.4, (y1 - y0 + 5, x1 - x0 + 2, 1))
    region = out[y0 - 2:y1 + 3, x0 - 1:x1 + 1]
    mm = m[y0 - 2:y1 + 3, x0 - 1:x1 + 1][..., None]
    region[:] = region * (1 - mm) + tex[:, :region.shape[1]] * mm
    rgb = np.clip(out, 0, 255).astype(np.uint8)
    for o in outs:
        png_rgba(o, rgb)
        print(f'{o}: {o.stat().st_size // 1024} KB')
    return rgb


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--src', type=Path, default=HERE / 'art-src' / 'build-forest-reference.png')
    ap.add_argument('--out', type=Path, default=HERE / 'launcher' / 'assets' / 'build-forest.pack')
    ap.add_argument('--preview', type=Path)
    ap.add_argument('--launcher-src', type=Path, default=HERE / 'art-src' / 'launcher-forest-reference.png')
    ap.add_argument('--launcher-out', type=Path, default=HERE / 'launcher' / 'assets' / 'launcher-forest.pack')
    ap.add_argument('--start-src', type=Path, default=HERE / 'art-src' / 'start-forest-reference.png')
    a_ = ap.parse_args()
    launcher_pack(a_.launcher_src, a_.launcher_out)
    start = start_picture(a_.start_src, [HERE / 'startup-logo.png', HERE.parents[1] / 'engine' / 'assets' / 'ocarina_reborn.png'])
    if a_.preview:
        a_.preview.mkdir(parents=True, exist_ok=True)
        Image.fromarray(start).save(a_.preview / 'start.png')
    a = np.asarray(Image.open(a_.src).convert('RGB'))
    if a.shape[:2] != (H, W):
        raise SystemExit(f'the reference must be {W} x {H}')
    out, hole = clear(a)
    track(out, a)
    letters, green, occ = masks(a)
    bg = np.clip(out, 0, 255).astype(np.uint8)
    meta = dict(GEOM)
    write_pack(a_.out, dict(bg=bg, letters=(letters * 255).astype(np.uint8), green=(green * 255).astype(np.uint8),
                            occ=(occ * 255).astype(np.uint8)), meta)
    print(f'{a_.out}: {a_.out.stat().st_size // 1024} KB')
    if a_.preview:
        a_.preview.mkdir(parents=True, exist_ok=True)
        Image.fromarray(bg).save(a_.preview / 'bg.png')
        Image.fromarray((hole * 255).astype(np.uint8)).save(a_.preview / 'hole.png')
        Image.fromarray((letters * 255).astype(np.uint8)).save(a_.preview / 'letters.png')
        Image.fromarray((green * 255).astype(np.uint8)).save(a_.preview / 'green.png')
        Image.fromarray((occ * 255).astype(np.uint8)).save(a_.preview / 'occ.png')


if __name__ == '__main__':
    main()

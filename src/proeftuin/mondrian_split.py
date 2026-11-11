"""Mondrian Split: de foto opgedeeld in rechthoeken met dikke zwarte lijnen, ingekleurd in de kleuren
van Mondriaan (rood, geel, blauw, wit, zwart). Waar de foto veel verandert, komen de meeste lijnen.
De kleur volgt de helderheid (zwart, blauw, rood, geel, wit), zodat je het gezicht blijft herkennen.

blocks (50-500): het aantal rechthoeken.
"""
import heapq

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from ._common import fit, hex_colors, luminance, stretch, to_array

WORK_SIZE = 400          # klein: het opdelen gebeurt op een mini-versie
OUTPUT_SIZE = 2000
MIN_SIDE = 0.018         # kleinste rechthoek, als fractie van de langste zijde
LINE_WIDTH = 0.007       # dikte van de zwarte lijnen, als fractie van de langste zijde

LOCAL_CONTRAST = 0.6     # hoeveel van de grote licht-donkervlakken wordt weggehaald (0: niets, 1: alles)

# Van donker naar licht: tot deze fracties van het oppervlak zwart, blauw, rood, geel; de rest wit
TONE_STEPS = (0.22, 0.34, 0.50, 0.68)

WHITE, LIGHT_GREY, BLACK, RED, YELLOW, BLUE = hex_colors(
    "#f3efe4", "#d9d6cf", "#151515", "#d52a1e", "#f5c518", "#1f3f9a")


def image_to_mondrian_split(image, blocks=60):
    small = tone_map(to_array(fit(image, WORK_SIZE)))
    height, width = small.shape[:2]
    min_side = max(2, round(MIN_SIDE * max(width, height)))

    # Steeds de rechthoek met de grootste fout (variatie maal oppervlak) in tweeën splitsen
    rects = [(0, 0, width, height)]
    heap = []
    push_split(heap, small, rects[0], min_side)

    while heap and len(rects) < blocks:
        _, rect, parts = heapq.heappop(heap)
        rects.remove(rect)

        for part in parts:
            rects.append(part)
            push_split(heap, small, part, min_side)

    scale = OUTPUT_SIZE / max(width, height)
    out_size = (round(width * scale), round(height * scale))
    canvas = Image.new("RGB", out_size, tuple(int(v * 255) for v in BLACK))
    draw = ImageDraw.Draw(canvas)
    line = max(2, round(LINE_WIDTH * OUTPUT_SIZE))

    colors = mondrian_colors(small, rects)

    for (x0, y0, x1, y1), color in zip(rects, colors):
        box = (round(x0 * scale) + line // 2, round(y0 * scale) + line // 2,
               round(x1 * scale) - (line + 1) // 2, round(y1 * scale) - (line + 1) // 2)

        if box[2] > box[0] and box[3] > box[1]:
            draw.rectangle(box, fill=tuple(int(v * 255) for v in color))

    # Een zwarte rand om het geheel
    draw.rectangle((0, 0, out_size[0] - 1, out_size[1] - 1), outline=(21, 21, 21), width=line)

    return canvas


def tone_map(pixels):
    """De helderheid van de foto, met de plaatselijke verschillen uitvergroot: ogen, wenkbrauwen en mond
    worden donker ten opzichte van de huid eromheen, ook als de foto als geheel licht of donker is.
    Daarop wordt gesplitst en gekleurd; dat houdt het gezicht herkenbaar."""
    lum = ndimage.gaussian_filter(luminance(pixels), 1.0)
    local = lum - LOCAL_CONTRAST * ndimage.gaussian_filter(lum, max(lum.shape) / 8)
    return stretch(local)[..., None]


def push_split(heap, pixels, rect, min_side):
    """Zoekt de beste snede (horizontaal of verticaal) en zet hem in de wachtrij, met de winst als prioriteit."""
    x0, y0, x1, y1 = rect
    part = pixels[y0:y1, x0:x1]
    best = None

    for axis in (0, 1):
        length = part.shape[axis]

        if length < 2 * min_side:
            continue

        # Per rij (axis 0) of kolom (axis 1) de som en de som van kwadraten, opgeteld met cumsum
        sums = part.sum(axis=1 - axis)
        squares = (part ** 2).sum(axis=1 - axis)
        count = part.shape[1 - axis]

        cs = np.cumsum(sums, axis=0)
        cq = np.cumsum(squares, axis=0)
        n = np.arange(1, length + 1)[:, None] * count

        total_s, total_q, total_n = cs[-1], cq[-1], length * count
        left_err = (cq - cs ** 2 / n).sum(axis=1)
        right_err = ((total_q - cq) - (total_s - cs) ** 2 / np.maximum(total_n - n, 1)).sum(axis=1)
        total_err = (total_q - total_s ** 2 / total_n).sum()

        gain = total_err - (left_err + right_err)
        cut_range = np.arange(min_side - 1, length - min_side)

        if len(cut_range) == 0:
            continue

        i = cut_range[np.argmax(gain[cut_range])]

        if best is None or gain[i] > best[0]:
            best = (gain[i], axis, i + 1)

    if best is None or best[0] <= 0:
        return

    gain, axis, cut = best

    if axis == 0:
        parts = ((x0, y0, x1, y0 + cut), (x0, y0 + cut, x1, y1))
    else:
        parts = ((x0, y0, x0 + cut, y1), (x0 + cut, y0, x1, y1))

    heapq.heappush(heap, (-gain, rect, parts))


def mondrian_colors(pixels, rects):
    """Een Mondriaan-kleur per rechthoek, op helderheid: zo blijft het licht en donker van de foto (en dus
    het gezicht) herkenbaar. De grenzen hangen af van de foto zelf: van het oppervlak (donker naar licht)
    wordt het donkerste deel zwart, dan blauw, rood, geel, en het lichtste deel wit."""
    lum = np.array([pixels[y0:y1, x0:x1].mean() for x0, y0, x1, y1 in rects])
    area = np.array([(x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rects], dtype=float)

    order = np.argsort(lum)
    cumulative = np.empty_like(area)
    cumulative[order] = (np.cumsum(area[order]) - area[order] / 2) / area.sum()

    steps = [(TONE_STEPS[0], BLACK), (TONE_STEPS[1], BLUE), (TONE_STEPS[2], RED), (TONE_STEPS[3], YELLOW)]
    colors = []

    for c in cumulative:
        color = next((col for limit, col in steps if c < limit), WHITE)
        colors.append(color)

    return colors

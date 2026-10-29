"""Tekenhulpjes die meerdere algoritmes gebruiken: kleuren van lijntjes en nummers,
de legenda (nummer -> kleur) onder een leeg tekenvel en het lettertype."""

import math
import os

from PIL import Image, ImageDraw, ImageFont

LINE_COLOR = (70, 70, 70)
NUMBER_COLOR = (140, 140, 140)
LEGEND_TEXT_COLOR = (90, 90, 90)


def add_legend(image, palette):
    """Plak onderaan een legenda: elk nummer met zijn kleur."""
    width, height = image.size
    longest = max(width, height)

    swatch = max(18, round(longest * 0.035))
    gap = round(swatch * 0.5)
    margin = round(swatch * 0.7)
    cell_width = round(swatch * 2.6)
    font = get_font(max(10, round(swatch * 0.55)))

    per_row = max(1, (width - 2 * margin) // cell_width)
    rows = math.ceil(len(palette) / per_row)
    band_height = 2 * margin + rows * swatch + (rows - 1) * gap

    result = Image.new("RGB", (width, height + band_height), "white")
    result.paste(image, (0, 0))
    draw = ImageDraw.Draw(result)

    for index, color in enumerate(palette):
        row, column = divmod(index, per_row)

        items_in_row = min(per_row, len(palette) - row * per_row)
        row_width = items_in_row * cell_width
        x0 = (width - row_width) // 2 + column * cell_width
        y0 = height + margin + row * (swatch + gap)

        draw.rectangle(
            (x0, y0, x0 + swatch, y0 + swatch),
            fill=tuple(int(v) for v in color),
            outline=LINE_COLOR,
            width=1,
        )
        draw.text(
            (x0 + swatch + swatch * 0.25, y0 + swatch / 2),
            str(index + 1),
            fill=LEGEND_TEXT_COLOR,
            font=font,
            anchor="lm",
        )

    return result


_font_cache = {}


def get_font(size):
    """Zoek een lettertype dat op elke server werkt."""
    if size in _font_cache:
        return _font_cache[size]

    candidates = []

    try:
        import matplotlib
        candidates.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf"))
    except Exception:
        pass

    candidates += ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]

    font = None

    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            break
        except (OSError, ValueError):
            continue

    if font is None:
        try:
            font = ImageFont.load_default(size)   # Pillow 10.1 of nieuwer
        except TypeError:
            font = ImageFont.load_default()

    _font_cache[size] = font
    return font

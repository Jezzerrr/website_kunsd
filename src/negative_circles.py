"""Negative Circles: de foto vol cirkels. In de cirkels zie je de foto zoals hij is,
tussen de cirkels het negatief (de kleuren omgekeerd). Het geheel is zelf ook een rondje (buiten de grote cirkel: doorzichtig).

Alles met numpy op één raster: per pixel de afstand tot het midden van het dichtstbijzijnde
cirkeltje. Een zachte rand van ongeveer één pixel voorkomt trapjes.
"""

import numpy as np
from PIL import Image, ImageOps

# Langste zijde van het resultaat (vierkant)
OUTPUT_SIZE = 2000

# Straal van een cirkeltje als fractie van de afstand tussen twee middelpunten.
# 0.5: de cirkels raken elkaar net en ertussen ontstaan sterretjes.
RADIUS_FRACTION = 0.5

# Rand om de grote cirkel, als fractie van de zijde (net genoeg om niet tegen de rand te plakken)
OUTER_MARGIN = 0.01


def image_to_negative_circles(image, circles_across=11, gray=False):
    """image: een RGB-foto (PIL). circles_across: hoeveel cirkeltjes er naast elkaar passen in de grote cirkel.
    gray: in zwart-wit in plaats van in kleur."""
    if gray:
        image = image.convert("L").convert("RGB")

    positive = square_photo(image)
    size = positive.shape[0]
    negative = 1.0 - positive

    # Het raster van cirkeltjes, gecentreerd op het midden: er valt altijd een cirkel precies in het midden
    spacing = size * (1 - 2 * OUTER_MARGIN) / circles_across
    radius = spacing * RADIUS_FRACTION

    coords = np.arange(size, dtype=np.float32) + 0.5 - size / 2
    offset = (coords + spacing / 2) % spacing - spacing / 2      # afstand tot het dichtstbijzijnde middelpunt, per as
    distance = np.sqrt(offset[:, None] ** 2 + offset[None, :] ** 2)

    inside = np.clip(radius - distance + 0.5, 0, 1)                  # 1 in een cirkeltje, 0 erbuiten, zacht ertussen
    inside = inside[:, :, None]
    result = inside * positive + (1 - inside) * negative

    # De grote cirkel: daarbuiten doorzichtig
    outer_radius = size / 2 * (1 - 2 * OUTER_MARGIN)
    center_distance = np.sqrt(coords[:, None] ** 2 + coords[None, :] ** 2)
    alpha = np.clip(outer_radius - center_distance + 0.5, 0, 1)

    rgba = np.dstack([result, alpha]) * 255

    return Image.fromarray(np.round(rgba).astype(np.uint8), "RGBA")


def square_photo(image):
    """Het vierkante midden van de foto, als RGB-waarden van 0 t/m 1, met wat extra contrast."""
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2

    square = image.crop((left, top, left + side, top + side))
    square = square.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)
    square = ImageOps.autocontrast(square, cutoff=1, preserve_tone=True)

    return np.asarray(square, dtype=np.float32) / 255

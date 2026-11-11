"""Negative Circles: de foto in zwart-wit, vol cirkels. In de cirkels zie je de foto zoals hij is,
tussen de cirkels het negatief. Het geheel is zelf ook een rondje (buiten de grote cirkel: doorzichtig).

Alles met numpy op één raster: per pixel de afstand tot het midden van het dichtstbijzijnde
cirkeltje. Een zachte rand van ongeveer één pixel voorkomt trapjes.

Het raster van cirkeltjes kan verschoven worden (shift_x, shift_y), zodat bijvoorbeeld een oog
precies op een overgang van normaal naar negatief valt. js/speeltuin.js toont hetzelfde raster
als voorvertoning; houd de rekenwijze daar gelijk aan deze.
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


def image_to_negative_circles(image, circles_across=6, shift_x=0.0, shift_y=0.0):
    """image: een RGB-foto (PIL). circles_across: hoeveel cirkeltjes er naast elkaar passen in de grote cirkel.
    shift_x, shift_y: verschuiving van het raster, als fractie van de afstand tussen twee cirkels
    (0 t/m 1; 0 is een cirkel precies in het midden, positief is naar rechts en naar beneden)."""
    positive = square_gray(image)
    size = positive.shape[0]
    negative = 1.0 - positive

    spacing = size * (1 - 2 * OUTER_MARGIN) / circles_across
    radius = spacing * RADIUS_FRACTION

    coords = np.arange(size, dtype=np.float32) + 0.5 - size / 2

    # Afstand tot het dichtstbijzijnde middelpunt, per as. Zonder verschuiving valt er een cirkel precies in het midden.
    offset_x = (coords - shift_x * spacing + spacing / 2) % spacing - spacing / 2
    offset_y = (coords - shift_y * spacing + spacing / 2) % spacing - spacing / 2
    distance = np.sqrt(offset_y[:, None] ** 2 + offset_x[None, :] ** 2)

    inside = np.clip(radius - distance + 0.5, 0, 1)                  # 1 in een cirkeltje, 0 erbuiten, zacht ertussen
    result = inside * positive + (1 - inside) * negative

    # De grote cirkel: daarbuiten doorzichtig
    outer_radius = size / 2 * (1 - 2 * OUTER_MARGIN)
    center_distance = np.sqrt(coords[:, None] ** 2 + coords[None, :] ** 2)
    alpha = np.clip(outer_radius - center_distance + 0.5, 0, 1)

    # Grijs plus doorzichtigheid ("LA"): een veel kleinere PNG dan RGBA
    gray_alpha = np.dstack([result, alpha]) * 255

    return Image.fromarray(np.round(gray_alpha).astype(np.uint8), "LA")


def square_gray(image):
    """Het vierkante midden van de foto, in grijstinten (0 t/m 1), met wat extra contrast."""
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2

    square = image.crop((left, top, left + side, top + side))
    square = square.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)
    gray = ImageOps.autocontrast(square.convert("L"), cutoff=1)

    return np.asarray(gray, dtype=np.float32) / 255

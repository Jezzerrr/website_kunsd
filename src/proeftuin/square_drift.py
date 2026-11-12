"""Square Drift: honderden rechthoekjes uit de foto worden gekopieerd en een stukje verder van het
midden weer geplakt, als een collage van verschoven snippers.

Hoe het werkt: voor elk snippertje kiezen we een plek q en een afmeting (een heel aantal
rasterhokjes). Het plaatje dat er komt, komt van een plek dichter bij het midden:
bron = q - (q - midden) * f, met f per snipper willekeurig. Hoe verder van het midden, hoe
groter de verschuiving; het midden (meestal het gezicht) blijft herkenbaar. Een dun randje
om elk snippertje laat het lijken op geplakt papier.
"""

import numpy as np
from PIL import Image

# Langste zijde van het resultaat
OUTPUT_SIZE = 2000

# Grootte van een rasterhokje als fractie van de langste zijde. Snippers zijn 1 t/m 4 hokjes breed en hoog.
CELL_FRACTION = 1 / 36
MAX_CELLS = 4

# Aantal snippers per hokje van de foto, bij de sterkste instelling
PIECES_PER_CELL = 0.9

# Kleinste en grootste verschuiving (fractie van de afstand tot het midden), bij sterkte 1
MIN_SHIFT = 0.04
MAX_SHIFT = 0.32

# Hoe donker het randje om een snipper is (0 = geen randje)
EDGE_DARKEN = 0.1


def image_to_square_drift(image, strength=0.6, seed=None):
    """image: een RGB-foto (PIL). strength (0.2 t/m 1): hoeveel en hoe ver de snippers verschuiven."""
    image = fit_size(image)
    source = np.asarray(image, dtype=np.float32)
    result = source.copy()
    height, width = source.shape[:2]

    rng = np.random.default_rng(seed)
    cell = max(4, round(max(width, height) * CELL_FRACTION))
    center = np.array([width / 2, height / 2])
    half_diagonal = np.hypot(width, height) / 2

    n_cells = (width / cell) * (height / cell)
    n_pieces = round(n_cells * PIECES_PER_CELL * strength)

    for _ in range(n_pieces):
        w = cell * rng.integers(1, MAX_CELLS + 1)
        h = cell * rng.integers(1, MAX_CELLS + 1)

        # Plek op een raster van halve hokjes, zodat het rommelig blijft maar niet chaotisch
        x = round(rng.uniform(-w / 2, width - w / 2) / (cell / 2)) * (cell // 2)
        y = round(rng.uniform(-h / 2, height - h / 2) / (cell / 2)) * (cell // 2)

        middle = np.array([x + w / 2, y + h / 2])
        distance = np.linalg.norm(middle - center) / half_diagonal

        # In het midden minder snippers: daar blijft de foto het meest heel
        if rng.random() > 0.15 + distance:
            continue

        shift = (middle - center) * rng.uniform(MIN_SHIFT, MAX_SHIFT) * strength
        sx = int(round(x - shift[0]))
        sy = int(round(y - shift[1]))

        paste(result, source, x, y, sx, sy, w, h)

    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")


def paste(result, source, x, y, sx, sy, w, h):
    """Kopieer het stuk (sx, sy, w, h) uit source naar (x, y) in result, alleen voor zover beide binnen de foto vallen."""
    height, width = source.shape[:2]

    # Afkappen aan alle kanten, voor doel en bron tegelijk
    left = max(0, -x, -sx)
    top = max(0, -y, -sy)
    right = min(w, width - x, width - sx)
    bottom = min(h, height - y, height - sy)

    if right - left < 2 or bottom - top < 2:
        return

    piece = source[sy + top:sy + bottom, sx + left:sx + right].copy()

    # Dun donker randje (1 pixel), alleen aan de kanten die echt bij de snipper horen
    if left == 0:
        piece[:, 0] *= 1 - EDGE_DARKEN
    if top == 0:
        piece[0, :] *= 1 - EDGE_DARKEN
    if right == w:
        piece[:, -1] *= 1 - EDGE_DARKEN
    if bottom == h:
        piece[-1, :] *= 1 - EDGE_DARKEN

    result[y + top:y + bottom, x + left:x + right] = piece


def fit_size(image):
    """Langste zijde precies OUTPUT_SIZE: dan zijn de snippers bij elke foto even groot ten opzichte van het geheel."""
    scale = OUTPUT_SIZE / max(image.size)

    return image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS
    )

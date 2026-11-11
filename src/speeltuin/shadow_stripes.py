"""Shadow Stripes: de foto als zwarte strepen, allemaal onder dezelfde hoek.

Hoe het werkt: over de foto liggen evenwijdige streeplijnen (onder de gekozen hoek), even ver uit
elkaar als een streep dik is. Elke streeplijn heeft een eigen drempel: op die lijn komt een streep
waar de foto donkerder is dan de drempel. De drempels zijn zo over de lijnen verdeeld (gulden-
snede-reeks) dat in een donker vlak bijna alle lijnen een streep krijgen (zwart), in een middentint
een deel (gearceerd) en in een licht vlak geen enkele (wit). Een streep loopt door zolang het donker
genoeg blijft, dus de strepen stoppen precies bij de vormen in de foto. Een langzaam golvende
drempel langs elke lijn breekt lange strepen in middentinten af, zodat het niet te strak wordt.

Alles is vast (geen toeval): dezelfde foto en hoek geven altijd hetzelfde plaatje. js/speeltuin.js
rekent precies hetzelfde uit voor de live voorvertoning, met hetzelfde grijswaardenkaartje
(darkness_map); pas de getallen hieronder dus ook daar aan (STRIPES in js/speeltuin.js).
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# Langste zijde van het grijswaardenkaartje waarop de strepen worden uitgerekend (ook in de browser)
MAP_SIZE = 500

# Langste zijde van het resultaat (de download), en hoeveel keer zo groot er getekend wordt (gladde randen)
OUTPUT_SIZE = 2000
SUPERSAMPLE = 2

# Aantal streeplijnen over de langste zijde
STRIPES_ACROSS = 240

# Drempels: lichter dan LIGHT blijft wit, donkerder dan DARK wordt zwart (donkerte 0 = wit, 1 = zwart)
LIGHT = 0.22
DARK = 0.78

# Golvende drempel langs een lijn: hoe sterk, en de golflengte (fractie van de langste zijde).
# Klein gehouden: lange, rustige strepen (zoals Jesse's voorbeeld) zien er beter uit dan veel korte.
WAVE = 0.04
WAVE_LENGTH = 0.25

# Kortere strepen dan dit (in streepdiktes) worden weggelaten: geen losse puntjes
MIN_LENGTH = 2.5

GOLDEN = (math.sqrt(5) - 1) / 2


def darkness_map(image):
    """Het grijswaardenkaartje: MAP_SIZE op de langste zijde, contrast opgerekt, licht vervaagd.
    0 = wit, 255 = zwart."""
    gray = image.convert("L")
    scale = MAP_SIZE / max(gray.size)
    gray = gray.resize((max(1, round(gray.width * scale)), max(1, round(gray.height * scale))),
                       Image.Resampling.LANCZOS)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.GaussianBlur(1))

    return ImageOps.invert(gray)


def stripe_segments(dark, angle):
    """De strepen als lijst (x1, y1, x2, y2) in pixels van het kaartje.

    dark: numpy-array (hoogte, breedte), 0-255 (255 = zwart). angle: graden, 0 = horizontaal,
    positief = naar rechts omhoog."""
    height, width = dark.shape
    dark = dark.astype(np.float32) / 255
    spacing = max(width, height) / STRIPES_ACROSS
    wave_length = max(width, height) * WAVE_LENGTH

    theta = math.radians(angle)
    ux, uy = math.cos(theta), -math.sin(theta)       # langs de streep (y loopt naar beneden)
    nx, ny = -uy, ux                                 # dwars op de streep
    cx, cy = width / 2, height / 2
    reach = math.hypot(width, height) / 2

    n_half = int(reach / spacing) + 1
    u = np.arange(-math.ceil(reach), math.ceil(reach) + 1, dtype=np.float32)
    segments = []

    for i in range(-n_half, n_half + 1):
        ox, oy = cx + i * spacing * nx, cy + i * spacing * ny
        xs, ys = ox + u * ux, oy + u * uy
        inside = (xs >= 0) & (xs <= width - 1) & (ys >= 0) & (ys <= height - 1)

        if not inside.any():
            continue

        values = np.where(inside, sample(dark, xs, ys), 0)
        threshold = line_threshold(i, u, wave_length)
        above = values > threshold

        segments.extend(runs(above, values - threshold, u, ox, oy, ux, uy, MIN_LENGTH * spacing))

    return segments, spacing


def line_threshold(i, u, wave_length):
    """De drempel van streeplijn i, langs de lijn (u) een beetje golvend."""
    g = (i * GOLDEN) % 1
    phase = ((i * 0.7548776662) % 1) * 2 * math.pi
    base = LIGHT + (DARK - LIGHT) * g

    return base + WAVE * np.sin(u * 2 * math.pi / wave_length + phase)


def sample(dark, xs, ys):
    """Bilineair bemonsteren (xs, ys binnen het kaartje)."""
    height, width = dark.shape
    xs = np.clip(xs, 0, width - 1)
    ys = np.clip(ys, 0, height - 1)
    x0 = np.minimum(xs.astype(int), width - 2)
    y0 = np.minimum(ys.astype(int), height - 2)
    fx, fy = xs - x0, ys - y0

    top = dark[y0, x0] * (1 - fx) + dark[y0, x0 + 1] * fx
    bottom = dark[y0 + 1, x0] * (1 - fx) + dark[y0 + 1, x0 + 1] * fx

    return top * (1 - fy) + bottom * fy


def runs(above, excess, u, ox, oy, ux, uy, min_length):
    """Aaneengesloten stukken waar above waar is, met het begin en eind precies op de drempel."""
    edges = np.diff(np.concatenate(([0], above.astype(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    result = []

    for s, e in zip(starts, ends):
        u1 = crossing(u, excess, s - 1, s) if s > 0 else u[s]
        u2 = crossing(u, excess, e, e + 1) if e < len(u) - 1 else u[e]

        if u2 - u1 >= min_length:
            result.append((ox + u1 * ux, oy + u1 * uy, ox + u2 * ux, oy + u2 * uy))

    return result


def crossing(u, excess, a, b):
    """Waar tussen u[a] en u[b] de drempel precies gepasseerd wordt."""
    t = excess[a] / (excess[a] - excess[b])

    return u[a] + (u[b] - u[a]) * t


def image_to_shadow_stripes(image, angle=20):
    """image: een RGB-foto (PIL). angle: hoek van de strepen in graden (-90 t/m 90)."""
    dark = np.asarray(darkness_map(image))
    segments, spacing = stripe_segments(dark, angle)

    height, width = dark.shape
    scale = OUTPUT_SIZE / max(width, height)
    big = scale * SUPERSAMPLE
    size = (round(width * big), round(height * big))

    canvas = Image.new("L", size, 255)
    draw = ImageDraw.Draw(canvas)
    line_width = max(1, round(spacing * big))

    for x1, y1, x2, y2 in segments:
        draw.line((x1 * big, y1 * big, x2 * big, y2 * big), fill=0, width=line_width)

    result = canvas.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)

    return result.convert("RGB")

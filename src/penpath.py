"""Penpath: een portret van korte rechte lijnen tussen punten op een raster, om zelf te tekenen.

Op het tekenvel staat een raster van punten met coördinaten, zoals bij zeeslag: kolommen A t/m AE,
rijen 1 t/m 41. Op blad 2 staan de lijnen als routes: zet je pen op het vetgedrukte punt en trek
zonder op te tillen van punt naar punt. Zo verschijnt langzaam het portret.

Hoe het werkt (licht genoeg voor de Render free plan):
1. De foto wordt een klein plaatje van WORK_STEP pixels per rasterhokje: hoe donker moet elk plekje
   worden. Details in het gezicht (ogen, neus, mond) worden aangezet ten opzichte van hun omgeving,
   en het midden telt zwaarder dan de randen.
2. Elke mogelijke lijn tussen twee punten die niet verder dan MAX_STEP hokjes uit elkaar liggen
   krijgt een score: hoeveel beter het plaatje wordt als je die lijn tekent (kleinste kwadraten).
3. Het algoritme gaat het liefst verder vanaf het punt waar de vorige lijn eindigde, zodat de
   lijnen lange routes vormen: minder vaak je pen verplaatsen en een korte lijst op het tekenvel.
   Alleen als een lijn elders veel beter is, begint een nieuwe route.
4. Dat herhalen we tot er n_lines lijnen zijn, of tot geen enkele lijn het plaatje nog beter maakt.

Nodig: numpy, scipy en Pillow.
"""

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, sparse

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font

TOOL_NAME = "Penpath"

# Het raster: zoveel kolommen en rijen punten. Op A4 liggen ze ruim 6 mm uit elkaar.
COLUMNS = 31
ROWS = 41

# Het rekenwerk gebeurt op een plaatje van zoveel pixels per rasterhokje
WORK_STEP = 10

# Langste lijn, in hokjes (horizontaal of verticaal). Korte lijnen maken ogen en mond mogelijk.
MAX_STEP = 5

# Hoeveel donker één lijn oplevert (op een schaal waar 1 helemaal zwart is)
INK = 0.5

# Doorgaan vanaf het eindpunt van de vorige lijn, tenzij de beste lijn daar minder dan zoveel
# oplevert als de beste lijn ergens anders. Lager = langere routes, maar iets minder precies.
KEEP_GOING = 0.5

# Voorbewerking van de foto
CONTRAST = 1.2
LOCAL_CONTRAST = 0.4       # details aanzetten ten opzichte van hun omgeving
CENTER_WEIGHT = 0.4        # het midden telt zwaarder dan de randen
EDGE_BOOST = 2.0
BACKGROUND_PENALTY = 0.03

# Het tekenvel: A4 bij 300 dpi, met een witte rand van 5 mm
A4_SIZE = (2480, 3508)
PAGE_MARGIN = round(A4_SIZE[0] * 5 / 210)

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)
DOT_COLOR = (60, 60, 60)

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def image_to_penpath(img, n_lines=900, template=False, output_size=1800):
    """Maak een portret van korte lijnen tussen rasterpunten.

    Args:
        img: PIL Image. Het midden (staand, 3 bij 4) wordt gebruikt.
        n_lines: hoogstens zoveel lijnen.
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (het raster, en de routes).
        output_size: breedte van het voorbeeld in pixels.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    photo = _center_crop(img.convert("RGB"))
    routes = find_routes(_target_darkness(photo), int(n_lines))

    if template:
        return [_draw_grid_page(), _draw_route_page(routes, photo)]

    return _draw_preview(routes, output_size)


def point_name(point):
    """De naam van een punt, zoals bij zeeslag: kolom-letter(s) en rij-nummer, bijv. "M12" of "AB3"."""
    row, column = divmod(point, COLUMNS)

    return _column_name(column) + str(row + 1)


def _column_name(column):
    return LETTERS[column] if column < len(LETTERS) else "A" + LETTERS[column - len(LETTERS)]


# ---------------------------------------------------------------------------
# Rekenen
# ---------------------------------------------------------------------------

def find_routes(target, n_lines):
    """De lijnen als routes: lijsten van punten (genummerd per rij, van links naar rechts)."""
    height, width = target.shape
    points = _point_positions()

    starts, ends = _candidate_lines()

    # Voor elke lijn de pixels waar hij overheen loopt (elk pixel één keer)
    length = np.hypot(*(points[ends] - points[starts]).T)
    samples = int(np.ceil(length.max() * 1.5)) + 2
    t = np.linspace(0.0, 1.0, samples)[None, :]
    xs = np.rint(points[starts, 0:1] + (points[ends, 0:1] - points[starts, 0:1]) * t).astype(np.int32)
    ys = np.rint(points[starts, 1:2] + (points[ends, 1:2] - points[starts, 1:2]) * t).astype(np.int32)
    line_ids = np.repeat(np.arange(len(starts)), samples)

    # Ijle matrix: welke lijn (kolom) over welke pixel (rij) loopt
    crossings = sparse.csr_matrix(
        (np.ones(line_ids.size, dtype=np.float32), ((ys * width + xs).ravel(), line_ids)),
        shape=(width * height, len(starts)),
    )
    crossings.sum_duplicates()
    crossings.data[:] = 1
    pixels_of_line = crossings.T.tocsr()
    pixel_count = np.asarray(crossings.getnnz(axis=0), dtype=np.float64)

    remaining = target.astype(np.float64).ravel()
    darkness_sum = pixels_of_line @ remaining

    # Per punt de lijnen die daar beginnen of eindigen
    lines_at = [[] for _ in range(len(points))]

    for line, (a, b) in enumerate(zip(starts, ends)):
        lines_at[a].append(line)
        lines_at[b].append(line)

    lines_at = [np.array(lines, dtype=int) for lines in lines_at]

    used = np.zeros(len(starts), dtype=bool)
    routes = []
    pen = None      # het punt waar de pen nu staat

    for _ in range(n_lines):
        # Winst van elke lijn: hoeveel kleiner het verschil met de foto wordt (kleinste kwadraten)
        gain = 2 * INK * darkness_sum - INK * INK * pixel_count
        gain[used] = -np.inf
        best = int(np.argmax(gain))

        if gain[best] <= 0:
            break

        if pen is not None:
            here = lines_at[pen]
            option = int(np.argmax(gain[here]))

            if gain[here[option]] >= KEEP_GOING * gain[best]:
                best = int(here[option])
            else:
                pen = None

        a, b = int(starts[best]), int(ends[best])

        if pen is None:
            routes.append([a, b])
            pen = b
        else:
            pen = b if a == pen else a
            routes[-1].append(pen)

        used[best] = True
        pixels = pixels_of_line[best].indices
        remaining[pixels] -= INK
        darkness_sum -= INK * np.asarray(crossings[pixels].sum(axis=0)).ravel()

    return _drawing_order(routes)


def _candidate_lines():
    """Alle lijnen tussen punten die hoogstens MAX_STEP hokjes uit elkaar liggen.

    Lijnen die precies over een ander punt lopen vallen af (die zijn twee kortere lijnen).
    """
    columns = np.arange(COLUMNS * ROWS) % COLUMNS
    rows = np.arange(COLUMNS * ROWS) // COLUMNS
    starts, ends = np.triu_indices(COLUMNS * ROWS, 1)

    dx = np.abs(columns[starts] - columns[ends])
    dy = np.abs(rows[starts] - rows[ends])
    keep = (np.maximum(dx, dy) <= MAX_STEP) & (np.gcd(dx, dy) == 1)

    return starts[keep], ends[keep]


def _join_routes(routes):
    """Plak routes aan elkaar als de ene eindigt waar de andere begint (eventueel omgedraaid).

    Hetzelfde tekenwerk, maar minder vaak je pen verplaatsen en een kortere lijst.
    """
    routes = [list(route) for route in routes]
    joined = True

    while joined:
        joined = False
        ends = {}

        for index, route in enumerate(routes):
            ends.setdefault(route[0], []).append(index)
            ends.setdefault(route[-1], []).append(index)

        taken = set()
        result = []

        for index, route in enumerate(routes):
            if index in taken:
                continue

            taken.add(index)

            for _ in range(2):      # eerst achteraan verlengen, dan (omgedraaid) vooraan
                while True:
                    other = next((i for i in ends.get(route[-1], []) if i not in taken), None)

                    if other is None:
                        break

                    taken.add(other)
                    piece = routes[other] if routes[other][0] == route[-1] else routes[other][::-1]
                    route = route + piece[1:]
                    joined = True

                route = route[::-1]

            result.append(route)

        routes = result

    return routes


def _drawing_order(routes):
    """Routes van boven naar beneden, en elke route vanaf zijn bovenste punt."""
    ordered = []

    for route in _join_routes(routes):
        if route[-1] < route[0]:
            route = route[::-1]

        ordered.append(route)

    return sorted(ordered, key=lambda route: route[0])


def _point_positions(step=WORK_STEP):
    """De punten als (x, y), per rij van links naar rechts."""
    columns = np.arange(COLUMNS * ROWS) % COLUMNS
    rows = np.arange(COLUMNS * ROWS) // COLUMNS

    return np.stack([columns * step, rows * step], axis=1).astype(np.float64)


def _center_crop(img):
    """Het grootste staande stuk (zelfde verhouding als het raster) uit het midden van de foto."""
    ratio = (COLUMNS - 1) / (ROWS - 1)

    if img.width / img.height > ratio:
        width = round(img.height * ratio)
        left = (img.width - width) // 2
        return img.crop((left, 0, left + width, img.height))

    height = round(img.width / ratio)
    top = (img.height - height) // 2
    return img.crop((0, top, img.width, top + height))


def _target_darkness(photo):
    """Per pixel hoe donker het moet worden: 1 = zo donker als kan, 0 of minder = wit laten."""
    width, height = (COLUMNS - 1) * WORK_STEP + 1, (ROWS - 1) * WORK_STEP + 1
    gray = np.asarray(photo.convert("L").resize((width, height), Image.LANCZOS), dtype=np.float32) / 255

    # Contrast oprekken: het donkerste en lichtste procent van de foto worden zwart en wit
    low, high = np.percentile(gray, [1, 99])
    gray = np.clip((gray - low) / max(high - low, 1e-3), 0, 1)
    darkness = (1 - gray) ** CONTRAST

    # Lokaal contrast: een donker plekje in een licht gezicht (een oog) telt mee, ook als de
    # capuchon of het haar eromheen nog veel donkerder is
    size = max(width, height) / 8
    mean = ndimage.gaussian_filter(darkness, size)
    spread = np.sqrt(ndimage.gaussian_filter((darkness - mean) ** 2, size)) + 0.08
    local = np.clip(0.35 + 0.18 * (darkness - mean) / spread, 0, 1)
    darkness = (1 - LOCAL_CONTRAST) * darkness + LOCAL_CONTRAST * local

    # Randen aanzetten
    blurred = ndimage.gaussian_filter(darkness, max(width, height) / 25, mode="nearest")
    darkness = np.clip(darkness + EDGE_BOOST * (darkness - blurred), 0, 1)

    # Het midden telt zwaarder: naar de randen toe wordt het doel lichter
    yy, xx = np.mgrid[0:height, 0:width]
    distance = ((xx - width / 2) / (width / 2)) ** 2 + ((yy - height * 0.45) / (height / 2)) ** 2
    darkness *= 1 - CENTER_WEIGHT * np.clip(distance - 0.3, 0, 1)

    return darkness - BACKGROUND_PENALTY


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

def _route_lines(routes):
    for route in routes:
        for a, b in zip(route, route[1:]):
            yield a, b


def _draw_preview(routes, output_size):
    """Zo ziet het eruit als alle lijnen getekend zijn."""
    scale = 2   # dubbel zo groot tekenen en verkleinen geeft gladde lijnen
    margin = round(output_size * 0.03) * scale
    step = (output_size * scale - 2 * margin) / (COLUMNS - 1)
    points = _point_positions(step) + margin

    width = output_size * scale
    height = round((ROWS - 1) * step) + 2 * margin
    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    # De punten heel licht, zodat je ziet waar ze zaten
    dot = max(1, round(step * 0.04))

    for x, y in points:
        draw.ellipse((x - dot, y - dot, x + dot, y + dot), fill=(215, 215, 215))

    # Een fineliner van 0,3 mm op een raster van ruim 6 mm
    line_width = max(1, round(step * 0.3 / 6.3))

    for a, b in _route_lines(routes):
        draw.line((tuple(points[a]), tuple(points[b])), fill=INK_COLOR, width=line_width)

    return image.resize((output_size, round(height / scale)), Image.LANCZOS)


def _draw_grid_page():
    """Blad 1: het raster met coördinaten, zo groot als op A4 past. Hierop teken je."""
    width, height = A4_SIZE
    label_space = round(width * 0.03)
    title_space = round(width * 0.02)
    step = min((width - 2 * (PAGE_MARGIN + label_space)) / (COLUMNS - 1),
               (height - 2 * (PAGE_MARGIN + label_space) - title_space) / (ROWS - 1))
    left = (width - step * (COLUMNS - 1)) / 2
    top = (height - step * (ROWS - 1) + title_space) / 2

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    label_font = get_font(round(width * 0.0115))
    label_offset = label_space * 0.6

    # Coördinaten rondom: letters boven en onder, nummers links en rechts
    for column in range(COLUMNS):
        x = left + column * step
        name = _column_name(column)
        draw.text((x, top - label_offset), name, fill=LINE_COLOR, font=label_font, anchor="mm")
        draw.text((x, top + (ROWS - 1) * step + label_offset), name, fill=LINE_COLOR, font=label_font,
                  anchor="mm")

    for row in range(ROWS):
        y = top + row * step
        draw.text((left - label_offset, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")
        draw.text((left + (COLUMNS - 1) * step + label_offset, y), str(row + 1), fill=LINE_COLOR,
                  font=label_font, anchor="mm")

    # De punten, elke vijfde rij en kolom iets groter: dan vind je je plek sneller
    for row in range(ROWS):
        for column in range(COLUMNS):
            x, y = left + column * step, top + row * step
            dot = width * (0.0024 if (row + 1) % 5 == 0 or (column + 1) % 5 == 0 else 0.0017)
            draw.ellipse((x - dot, y - dot, x + dot, y + dot), fill=DOT_COLOR)

    small = get_font(round(width * 0.011))
    draw.text((PAGE_MARGIN, PAGE_MARGIN), f"{TOOL_NAME} · blad 1: hierop teken je", fill=NUMBER_COLOR,
              font=small, anchor="lt")
    draw.text((width - PAGE_MARGIN, height - PAGE_MARGIN), "De routes staan op blad 2", fill=NUMBER_COLOR,
              font=small, anchor="rb")

    return image


def _draw_route_page(routes, photo):
    """Blad 2: de routes, met je foto en het "antwoord" klein onderaan.

    Elke route begint met een vetgedrukt punt: daar zet je je pen neer. Daarna trek je zonder op te
    tillen een lijn naar elk volgend punt. Het lettertype wordt zo groot als past, zodat alles op
    één A4 komt. Onderaan, achter een knip- of vouwlijn: wie het antwoord niet wil zien, vouwt het weg.
    """
    width, height = A4_SIZE
    margin = round(width * 0.045)
    picture_height = round(width * 0.24)
    bottom_block = round(width * 0.06) + picture_height + round(width * 0.03)
    list_top = margin + round(width * 0.105)
    list_height = height - margin - bottom_block - list_top

    columns = 5
    column_gap = round(width * 0.02)
    column_width = (width - 2 * margin - (columns - 1) * column_gap) / columns

    # Grootste lettertype waarbij de lijst past
    for font_size in range(30, 15, -1):
        layout = _layout_routes(routes, column_width, font_size)
        rows = math.ceil(len(layout) / columns)

        if rows * round(font_size * 1.45) <= list_height:
            break

    line_height = round(font_size * 1.45)
    rows = math.ceil(len(layout) / columns)

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    n_lines = sum(len(route) - 1 for route in routes)
    draw.text((margin, margin), f"{TOOL_NAME} · {n_lines} lijnen in {len(routes)} routes",
              fill=INK_COLOR, font=get_font(round(width * 0.02)), anchor="lt")
    explanation = [
        "Zet je pen op het vetgedrukte punt en trek met je liniaal een lijn naar het volgende punt,",
        "en zo verder zonder op te tillen. Klaar met de route? Streep hem af en begin aan de volgende.",
    ]

    for number, text in enumerate(explanation):
        draw.text((margin, margin + round(width * 0.04) + number * round(width * 0.022)), text,
                  fill=LINE_COLOR, font=get_font(round(width * 0.0135)), anchor="lt")

    regular = get_font(font_size)
    bold_offset = max(1, round(font_size / 22))

    for position, (start, points) in enumerate(layout):
        column, row = divmod(position, rows)
        x = margin + column * (column_width + column_gap)
        y = list_top + row * line_height + line_height / 2

        for index, (text, offset) in enumerate(points):
            is_start = start and index == 0
            draw.text((x + offset, y), text, fill=INK_COLOR if is_start else LINE_COLOR, font=regular,
                      anchor="lm", stroke_width=bold_offset if is_start else 0, stroke_fill=INK_COLOR)

    _draw_answer(image, routes, photo, margin, picture_height)

    return image


def _layout_routes(routes, column_width, font_size):
    """Elke route op eigen regel(s): per regel (begint hier een route, [(tekst, x), ...]).

    Past een route niet op één regel, dan loopt hij door op de volgende regel, iets ingesprongen.
    """
    font = get_font(font_size)
    space = font.getlength("  ")
    indent = font.getlength("AE40") * 0.5
    layout = []

    for route in routes:
        names = [point_name(point) for point in route]
        line, x, first = [], 0.0, True

        for name in names:
            name_width = font.getlength(name)

            if line and x + name_width > column_width:
                layout.append((first, line))
                line, x, first = [], indent, False

            line.append((name, x))
            x += name_width + space

        layout.append((first, line))

    return layout


def _draw_answer(image, routes, photo, margin, picture_height):
    """Onderaan, achter een gestippelde knip- of vouwlijn: je foto en het antwoord."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    caption_font = get_font(round(width * 0.012))

    picture_width = round(picture_height * (COLUMNS - 1) / (ROWS - 1))
    pictures_top = height - margin - round(width * 0.03) - picture_height
    gap = round(width * 0.06)
    pictures_left = (width - 2 * picture_width - gap) // 2

    fold_y = pictures_top - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    answer = _draw_preview(routes, picture_width * 2).resize((picture_width, picture_height), Image.LANCZOS)
    pictures = [(photo.resize((picture_width, picture_height), Image.LANCZOS), "Je foto"),
                (answer, "Zo wordt het")]

    for number, (picture, caption) in enumerate(pictures):
        x = pictures_left + number * (picture_width + gap)
        image.paste(picture, (x, pictures_top))
        draw.text((x + picture_width / 2, pictures_top + picture_height + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

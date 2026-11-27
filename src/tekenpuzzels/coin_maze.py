"""Coin Maze: een doolhof van boogjes, waarin je portret verschijnt. Een muntje beslist mee.

Op blad 1 staan alleen puntjes: de hoeken van de hokjes, met letters en cijfers erlangs zoals
bij zeeslag. Op blad 2 staat per hokje een getal: 1, 3 of 5. Dat is hoeveel boogjes je in twee
tegenover elkaar liggende hoeken van het hokje tekent. Welke twee hoeken? Dat beslist een muntje:
kop = linksboven en rechtsonder, munt = rechtsboven en linksonder.

De boogjes van buurhokjes sluiten op elkaar aan, en zo ontstaat vanzelf een doolhof van slingerende
lijnen (zogenaamde Truchet-tegels). Waar je foto donker is, liggen veel boogjes dicht op elkaar en
wordt het donker. Iedereen die dezelfde puzzel maakt, krijgt een ander doolhof met hetzelfde gezicht.

Heel licht rekenwerk: geen probleem voor de Render free plan.

Nodig: numpy, scipy en Pillow.
"""

import random

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font
from src.helper_functions.grid_layout import A4_SIZE, fit_picture

TOOL_NAME = "Coin Maze"

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Hoe donker een hokje gemiddeld moet zijn voor 3 of 5 boogjes
LEVEL_THRESHOLDS = (0.22, 0.5)

# De straal van de boogjes, als deel van een hokje: de middelste boog loopt van midden tot midden
ARC_OFFSETS = {1: (0.0,), 3: (-0.17, 0.0, 0.17), 5: (-0.34, -0.17, 0.0, 0.17, 0.34)}

# De hoeken waarin je tekent: (hoek als (0 of 1, 0 of 1), beginhoek van de boog in graden, zoals PIL telt)
HEADS = (((0, 0), 0), ((1, 1), 180))     # kop: linksboven en rechtsonder
TAILS = (((1, 0), 90), ((0, 1), 270))    # munt: rechtsboven en linksonder

# Het tekenvel: A4 bij 300 dpi, met een witte rand van 5 mm
PX_PER_MM = 300 / 25.4
PAGE_MARGIN = round(A4_SIZE[0] * 5 / 210)
LABEL_SPACE = round(A4_SIZE[0] * 0.03)
TITLE_SPACE = round(A4_SIZE[0] * 0.03)

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)
DOT_COLOR = (120, 120, 125)
HALF_DOT_COLOR = (200, 200, 205)
CHART_LINE = (215, 215, 220)


def image_to_coin_maze(img, columns=24, template=False, output_size=1800, seed=None):
    """Maak een muntjesdoolhof van een foto.

    Args:
        img: PIL Image. Wordt bijgesneden tot hij precies in het raster past.
        columns: hoeveel hokjes naast elkaar (hoogstens 26, één letter per kolom).
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (de puntjes, en de getallen).
        output_size: breedte van het voorbeeld in pixels.
        seed: het "muntje" van het voorbeeld. None = elke keer een ander doolhof.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    img = img.convert("RGB")
    columns = max(8, min(26, int(columns)))
    rows, cell = _fit_grid(img.size, columns)
    photo = ImageOps.fit(img, (columns * 32, rows * 32), Image.LANCZOS, centering=(0.5, 0.42))
    counts = find_counts(_darkness(photo), columns, rows)
    coins = _toss_coins(counts.shape, seed)

    if template:
        return [_draw_dot_page(columns, rows, cell), _draw_chart_page(counts, coins, photo)]

    return _draw_maze(counts, coins, output_size)


def find_counts(darkness, columns, rows):
    """Per hokje het aantal boogjes (1, 3 of 5), als array (rijen, kolommen)."""
    mean = np.asarray(Image.fromarray((darkness * 255).astype(np.uint8)).resize((columns, rows), Image.BOX),
                      dtype=np.float32) / 255

    return np.where(mean < LEVEL_THRESHOLDS[0], 1, np.where(mean < LEVEL_THRESHOLDS[1], 3, 5)).astype(np.int8)


def _fit_grid(image_size, columns):
    """Hoeveel rijen er komen, en hoe groot een hokje is (in pixels bij 300 dpi), op staand A4."""
    width, height = A4_SIZE
    room_width = width - 2 * (PAGE_MARGIN + LABEL_SPACE)
    room_height = height - 2 * (PAGE_MARGIN + LABEL_SPACE + TITLE_SPACE)
    cell = room_width / columns
    rows = max(4, round(columns * image_size[1] / image_size[0]))
    rows = min(rows, int(room_height / cell))

    return rows, cell


def _toss_coins(shape, seed):
    """Per hokje kop (True) of munt (False)."""
    generator = np.random.default_rng(random.randrange(1 << 30) if seed is None else seed)

    return generator.random(shape) < 0.5


def _darkness(photo):
    """Per pixel hoe donker het is (0 = wit, 1 = zwart), met wat extra lokaal contrast.

    Wit blijft wit: een uitgeknipte achtergrond wordt een rustig doolhof van enkele boogjes.
    """
    gray = np.asarray(photo.convert("L"), dtype=np.float32) / 255
    darkness = 1 - gray
    content = darkness > 0.03
    sample = darkness[content] if content.mean() > 0.05 else darkness.ravel()

    low, high = np.percentile(sample, [1, 99])
    darkness = np.clip((darkness - low) / max(high - low, 1e-3), 0, 1)

    mean = ndimage.gaussian_filter(darkness, max(photo.size) / 20)
    darkness = np.clip(darkness + 0.6 * (darkness - mean), 0, 1)
    darkness[gray > 0.97] = 0

    return darkness


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

def _draw_tile(draw, left, top, cell, count, heads, line_width, color=INK_COLOR):
    """Eén hokje: count boogjes in de twee hoeken die het muntje aanwijst."""
    for (corner_x, corner_y), start in (HEADS if heads else TAILS):
        cx, cy = left + corner_x * cell, top + corner_y * cell

        for offset in ARC_OFFSETS[count]:
            radius = cell * (0.5 + offset)
            draw.arc((cx - radius, cy - radius, cx + radius, cy + radius), start, start + 90, fill=color,
                     width=line_width)


def _draw_tile_dots(draw, left, top, cell):
    """De stippen van blad 1 in een voorbeeldhokje: groot op de hoeken, klein halverwege de randen."""
    corner = round(PX_PER_MM * 0.35)
    half = round(PX_PER_MM * 0.25)

    for step_y in range(3):
        for step_x in range(3):
            if step_x == 1 and step_y == 1:
                continue

            x, y = left + step_x * cell / 2, top + step_y * cell / 2
            size, color = (corner, DOT_COLOR) if step_x != 1 and step_y != 1 else (half, (165, 165, 170))
            draw.ellipse((x - size, y - size, x + size, y + size), fill=color)


def _draw_maze(counts, coins, output_size, pen_mm=0.4):
    """Zo ziet het eruit als alle boogjes getekend zijn."""
    rows, columns = counts.shape
    supersample = 3
    margin = round(output_size * 0.03) * supersample
    cell = (output_size * supersample - 2 * margin) / columns
    width = output_size * supersample
    height = round(rows * cell) + 2 * margin

    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)

    # Een pen van 0,4 mm op hokjes zo groot als op het tekenvel
    cell_mm = (A4_SIZE[0] - 2 * (PAGE_MARGIN + LABEL_SPACE)) / columns / PX_PER_MM
    line_width = max(1, round(cell * pen_mm / cell_mm))

    for row in range(rows):
        for column in range(columns):
            _draw_tile(draw, margin + column * cell, margin + row * cell, cell, int(counts[row, column]),
                       bool(coins[row, column]), line_width, color=INK_COLOR[0])

    return image.resize((output_size, round(height / supersample)), Image.LANCZOS).convert("RGB")


def _draw_dot_page(columns, rows, cell):
    """Blad 1: alleen puntjes op de hoeken van de hokjes (en lichtere halverwege), met letters en cijfers."""
    width, height = A4_SIZE
    left = (width - columns * cell) / 2
    top = (height - rows * cell) / 2

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)
    label_font = get_font(round(width * 0.0115))
    corner = round(PX_PER_MM * 0.35)
    half = round(PX_PER_MM * 0.2)

    for row in range(rows * 2 + 1):
        for column in range(columns * 2 + 1):
            if row % 2 and column % 2:
                continue    # het midden van een hokje: daar komt niets

            x, y = left + column * cell / 2, top + row * cell / 2
            size, color = (corner, DOT_COLOR) if row % 2 == 0 and column % 2 == 0 else (half, HALF_DOT_COLOR)
            draw.ellipse((x - size, y - size, x + size, y + size), fill=color)

    offset = LABEL_SPACE * 0.6

    for column in range(columns):
        x = left + (column + 0.5) * cell
        draw.text((x, top - offset), LETTERS[column], fill=LINE_COLOR, font=label_font, anchor="mm")
        draw.text((x, top + rows * cell + offset), LETTERS[column], fill=LINE_COLOR, font=label_font, anchor="mm")

    for row in range(rows):
        y = top + (row + 0.5) * cell
        draw.text((left - offset, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")
        draw.text((left + columns * cell + offset, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")

    small = get_font(round(width * 0.011))
    draw.text((PAGE_MARGIN, PAGE_MARGIN), f"{TOOL_NAME} · blad 1: hierop teken je", fill=NUMBER_COLOR,
              font=small, anchor="lt")
    draw.text((width - PAGE_MARGIN, height - PAGE_MARGIN), "Wat je tekent staat op blad 2", fill=NUMBER_COLOR,
              font=small, anchor="rb")

    return image


def _draw_chart_page(counts, coins, photo):
    """Blad 2: uitleg met voorbeeldhokjes, per hokje het aantal boogjes, en het antwoord achter de vouwlijn."""
    rows, columns = counts.shape
    width, height = A4_SIZE
    margin = round(width * 0.045)
    unit = width

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)
    title_font = get_font(round(unit * 0.02))
    text_font = get_font(round(unit * 0.0128))
    small_font = get_font(round(unit * 0.0105))

    total = int(counts.sum()) * 2
    draw.text((margin, margin), f"{TOOL_NAME} · {columns * rows} hokjes, {total} boogjes", fill=INK_COLOR,
              font=title_font, anchor="lt")
    explanation = [
        "Gooi per hokje een muntje. Kop: teken de boogjes in de hoeken linksboven en rechtsonder.",
        "Munt: rechtsboven en linksonder. Het getal zegt hoeveel boogjes je in elk van die twee hoeken tekent.",
        "Een boogje is een kwart rondje om het hoekpunt. Het middelste boogje loopt van kleine stip tot kleine",
        "stip (de stippen halverwege de randen). Bij 3 of 5 komen de andere er op gelijke afstand binnen en buiten.",
    ]
    y = margin + round(unit * 0.04)

    for text in explanation:
        draw.text((margin, y), text, fill=LINE_COLOR, font=text_font, anchor="lt")
        y += round(unit * 0.021)

    # Voorbeeldhokjes: kop en munt, met 1, 3 en 5 boogjes
    y += round(unit * 0.015)
    tile = round(unit * 0.07)
    tile_gap = round(unit * 0.03)
    group_gap = round(unit * 0.08)
    group_width = 3 * tile + 2 * tile_gap
    x = (width - 2 * group_width - group_gap) / 2

    for heads, name in ((True, "Kop"), (False, "Munt")):
        draw.text((x + group_width / 2, y), name, fill=INK_COLOR, font=text_font, anchor="mt")

        for number, count in enumerate((1, 3, 5)):
            tile_left = x + number * (tile + tile_gap)
            tile_top = y + round(unit * 0.025)
            draw.rectangle((tile_left, tile_top, tile_left + tile, tile_top + tile), outline=CHART_LINE, width=2)
            _draw_tile(draw, tile_left, tile_top, tile, count, heads, max(2, round(tile * 0.035)))
            _draw_tile_dots(draw, tile_left, tile_top, tile)
            draw.text((tile_left + tile / 2, tile_top + tile + round(unit * 0.008)), str(count), fill=LINE_COLOR,
                      font=small_font, anchor="mt")

        x += group_width + group_gap

    y += round(unit * 0.025) + tile + round(unit * 0.035)

    # De tabel: zo groot als past tussen de uitleg en het antwoord
    picture_height = round(width * 0.22)
    bottom_block = round(width * 0.06) + picture_height + round(width * 0.03)
    label_space = round(unit * 0.03)
    chart_top = y + label_space
    room_height = height - margin - bottom_block - chart_top - label_space
    room_width = width - 2 * margin - 2 * label_space
    chart_cell = min(room_width / columns, room_height / rows, unit * 0.045)
    chart_left = (width - columns * chart_cell) / 2

    label_font = get_font(round(min(unit * 0.011, chart_cell * 0.45)))
    number_font = get_font(round(chart_cell * 0.5))

    for row in range(rows):
        for column in range(columns):
            count = int(counts[row, column])
            left = chart_left + column * chart_cell
            top = chart_top + row * chart_cell
            # Alle getallen even zwart en zonder kleurvlakken: zo zie je het gezicht nog niet in de tabel
            draw.rectangle((left, top, left + chart_cell, top + chart_cell), outline=CHART_LINE, width=1)
            draw.text((left + chart_cell / 2, top + chart_cell / 2), str(count), fill=INK_COLOR,
                      font=number_font, anchor="mm")

    for column in range(columns):
        x = chart_left + (column + 0.5) * chart_cell
        draw.text((x, chart_top - label_space * 0.5), LETTERS[column], fill=LINE_COLOR, font=label_font,
                  anchor="mm")

    for row in range(rows):
        y = chart_top + (row + 0.5) * chart_cell
        draw.text((chart_left - label_space * 0.5, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")
        draw.text((chart_left + columns * chart_cell + label_space * 0.5, y), str(row + 1), fill=LINE_COLOR,
                  font=label_font, anchor="mm")

    _draw_answer(image, counts, coins, photo, margin, picture_height)

    return image


def _draw_answer(image, counts, coins, photo, margin, max_height):
    """Onderaan, achter een gestippelde knip- of vouwlijn: je foto en een voorbeeld van het antwoord."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    caption_font = get_font(round(width * 0.012))
    rows, columns = counts.shape

    gap = round(width * 0.06)
    picture_width, picture_height = fit_picture((columns, rows), (width - 2 * margin - gap) / 2, max_height)
    pictures_top = height - margin - round(width * 0.03) - max_height + (max_height - picture_height) // 2
    pictures_left = (width - 2 * picture_width - gap) // 2

    fold_y = height - margin - round(width * 0.03) - max_height - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    # Het antwoord zonder witte rand, zodat het even groot is als de foto
    answer = _draw_maze(counts, coins, picture_width * 2)
    inner = round(answer.width * 0.03)
    answer = answer.crop((inner, inner, answer.width - inner, answer.height - inner))
    answer = answer.resize((picture_width, picture_height), Image.LANCZOS)

    pictures = [(photo.resize((picture_width, picture_height), Image.LANCZOS), "Je foto"),
                (answer, "Zo kan het worden (jouw muntje maakt het anders)")]

    for number, (picture, caption) in enumerate(pictures):
        x = pictures_left + number * (picture_width + gap)
        image.paste(picture, (x, pictures_top))
        draw.text((x + picture_width / 2, pictures_top + picture_height + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

"""Hatchwork: een portret van liggende en staande lijnstukjes op ruitjespapier, om zelf te tekenen.

Zo werkten graveurs vroeger: hoe donkerder een plek, hoe meer lagen lijntjes eroverheen
(arceren). Op het tekenvel staat een licht raster met genummerde rijen en kolommen. Op blad 2
staat per rij of kolom van welk tot welk punt je een lijn trekt, in vier rondes:

1. liggende lijnen op de oneven rijen: geeft de vorm
2. staande lijnen op de oneven kolommen: maakt de donkere delen donkerder
3. liggende lijnen op de even rijen: nog donkerder
4. staande lijnen op de even kolommen: alleen de allerdonkerste plekken

Elke ronde tekent alleen waar de foto donkerder is dan de drempel van die ronde. Heel licht
rekenwerk: geen probleem voor de Render free plan.

Nodig: numpy, scipy en Pillow.
"""

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font

TOOL_NAME = "Hatchwork"

# De vier rondes: (richting, oneven of even rijen/kolommen, hoe donker het minstens moet zijn)
ROUNDS = [
    ("h", 0, 0.25, "Ronde 1: liggende lijnen op de oneven rijen"),
    ("v", 0, 0.45, "Ronde 2: staande lijnen op de oneven kolommen"),
    ("h", 1, 0.65, "Ronde 3: liggende lijnen op de even rijen"),
    ("v", 1, 0.85, "Ronde 4: staande lijnen op de even kolommen"),
]

# Een lijnstukje moet over minstens zoveel punten lopen (2 = één hokje lang)
MIN_POINTS = 2

# Voorbewerking van de foto (zoals bij Penpath)
CONTRAST = 1.2
LOCAL_CONTRAST = 0.4
CENTER_WEIGHT = 0.4
EDGE_BOOST = 1.0

# Het tekenvel: A4 bij 300 dpi, met een witte rand van 5 mm
A4_SIZE = (2480, 3508)
PAGE_MARGIN = round(A4_SIZE[0] * 5 / 210)
LABEL_SPACE = round(A4_SIZE[0] * 0.028)
TITLE_SPACE = round(A4_SIZE[0] * 0.02)

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)
GRID_COLOR = (226, 230, 238)
GRID_COLOR_FIFTH = (196, 204, 218)


def image_to_hatchwork(img, columns=70, template=False, output_size=1800):
    """Maak een gearceerd portret op een raster.

    Args:
        img: PIL Image. Het midden (staand, zoals het raster op A4) wordt gebruikt.
        columns: aantal kolommen van het raster. Meer = fijner, maar meer lijntjes.
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (het raster, en de lijst).
        output_size: breedte van het voorbeeld in pixels.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    columns = int(columns)
    rows = grid_rows(columns)
    photo = _center_crop(img.convert("RGB"), columns, rows)
    segments = find_segments(_darkness(photo, columns, rows))

    if template:
        return [_draw_grid_page(columns, rows), _draw_list_page(segments, photo, columns, rows)]

    return _draw_segments(segments, columns, rows, output_size)


def grid_rows(columns):
    """Zoveel rijen dat het raster met deze kolommen precies A4 vult."""
    width, height = A4_SIZE
    step = (width - 2 * (PAGE_MARGIN + LABEL_SPACE)) / (columns - 1)

    return int((height - 2 * (PAGE_MARGIN + LABEL_SPACE) - TITLE_SPACE) / step) + 1


def find_segments(darkness):
    """De lijnstukjes als (ronde, richting, rij- of kolomnummer, van, tot), alles vanaf 0."""
    segments = []

    for round_number, (direction, parity, threshold, _) in enumerate(ROUNDS):
        lines = darkness if direction == "h" else darkness.T

        for index in range(parity, lines.shape[0], 2):
            dark = lines[index] > threshold
            start = None

            for position, is_dark in enumerate(list(dark) + [False]):
                if is_dark and start is None:
                    start = position
                elif not is_dark and start is not None:
                    if position - start >= MIN_POINTS:
                        segments.append((round_number, direction, index, start, position - 1))

                    start = None

    return segments


def _center_crop(img, columns, rows):
    """Het grootste stuk uit het midden van de foto met dezelfde verhouding als het raster."""
    ratio = (columns - 1) / (rows - 1)

    if img.width / img.height > ratio:
        width = round(img.height * ratio)
        left = (img.width - width) // 2
        return img.crop((left, 0, left + width, img.height))

    height = round(img.width / ratio)
    top = (img.height - height) // 2
    return img.crop((0, top, img.width, top + height))


def _darkness(photo, columns, rows):
    """Per rasterpunt hoe donker het moet worden (0 = wit, 1 = zwart)."""
    width, height = columns * 4, rows * 4
    gray = np.asarray(photo.convert("L").resize((width, height), Image.LANCZOS), dtype=np.float32) / 255

    low, high = np.percentile(gray, [1, 99])
    gray = np.clip((gray - low) / max(high - low, 1e-3), 0, 1)
    darkness = (1 - gray) ** CONTRAST

    # Lokaal contrast: details in het gezicht tellen mee, ook naast iets heel donkers
    size = max(width, height) / 8
    mean = ndimage.gaussian_filter(darkness, size)
    spread = np.sqrt(ndimage.gaussian_filter((darkness - mean) ** 2, size)) + 0.08
    local = np.clip(0.35 + 0.18 * (darkness - mean) / spread, 0, 1)
    darkness = (1 - LOCAL_CONTRAST) * darkness + LOCAL_CONTRAST * local

    blurred = ndimage.gaussian_filter(darkness, max(width, height) / 25, mode="nearest")
    darkness = np.clip(darkness + EDGE_BOOST * (darkness - blurred), 0, 1)

    yy, xx = np.mgrid[0:height, 0:width]
    distance = ((xx - width / 2) / (width / 2)) ** 2 + ((yy - height * 0.45) / (height / 2)) ** 2
    darkness *= 1 - CENTER_WEIGHT * np.clip(distance - 0.3, 0, 1)

    # Gemiddelde per rasterpunt
    small = Image.fromarray((darkness * 255).astype(np.uint8)).resize((columns, rows), Image.BOX)

    return np.asarray(small, dtype=np.float32) / 255


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

def _draw_segments(segments, columns, rows, output_size):
    """Zo ziet het eruit als alle lijntjes getekend zijn."""
    scale = 2
    margin = round(output_size * 0.03) * scale
    step = (output_size * scale - 2 * margin) / (columns - 1)
    width = output_size * scale
    height = round((rows - 1) * step) + 2 * margin

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    # Een fineliner van 0,3 mm op hokjes van ongeveer 2,7 mm (bij 70 kolommen)
    step_mm = 190 / (columns - 1)
    line_width = max(1, round(step * 0.3 / step_mm))

    for _, direction, index, start, end in segments:
        if direction == "h":
            y = margin + index * step
            draw.line((margin + start * step, y, margin + end * step, y), fill=INK_COLOR, width=line_width)
        else:
            x = margin + index * step
            draw.line((x, margin + start * step, x, margin + end * step), fill=INK_COLOR, width=line_width)

    return image.resize((output_size, round(height / scale)), Image.LANCZOS)


def _draw_grid_page(columns, rows):
    """Blad 1: een licht raster met genummerde rijen en kolommen. Hierop teken je."""
    width, height = A4_SIZE
    step = (width - 2 * (PAGE_MARGIN + LABEL_SPACE)) / (columns - 1)
    left = PAGE_MARGIN + LABEL_SPACE
    top = (height - step * (rows - 1) + TITLE_SPACE) / 2
    right = left + (columns - 1) * step
    bottom = top + (rows - 1) * step

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)
    label_font = get_font(round(width * 0.0105))
    offset = LABEL_SPACE * 0.55

    # Eerst de lichte lijnen, dan elke vijfde iets donkerder eroverheen
    for fifth in (False, True):
        color = GRID_COLOR_FIFTH if fifth else GRID_COLOR

        for column in range(columns):
            if ((column + 1) % 5 == 0) == fifth:
                x = left + column * step
                draw.line((x, top, x, bottom), fill=color, width=2)

        for row in range(rows):
            if ((row + 1) % 5 == 0) == fifth:
                y = top + row * step
                draw.line((left, y, right, y), fill=color, width=2)

    # Nummers bij 1 en elke vijfde, rondom
    for column in range(columns):
        if column == 0 or (column + 1) % 5 == 0:
            x = left + column * step
            draw.text((x, top - offset), str(column + 1), fill=LINE_COLOR, font=label_font, anchor="mm")
            draw.text((x, bottom + offset), str(column + 1), fill=LINE_COLOR, font=label_font, anchor="mm")

    for row in range(rows):
        if row == 0 or (row + 1) % 5 == 0:
            y = top + row * step
            draw.text((left - offset, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")
            draw.text((right + offset, y), str(row + 1), fill=LINE_COLOR, font=label_font, anchor="mm")

    small = get_font(round(width * 0.011))
    draw.text((PAGE_MARGIN, PAGE_MARGIN), f"{TOOL_NAME} · blad 1: hierop teken je", fill=NUMBER_COLOR,
              font=small, anchor="lt")
    draw.text((width - PAGE_MARGIN, height - PAGE_MARGIN), "Wat je tekent staat op blad 2", fill=NUMBER_COLOR,
              font=small, anchor="rb")

    return image


def _draw_list_page(segments, photo, columns, rows):
    """Blad 2: per ronde per rij of kolom de lijnstukjes, met je foto en het antwoord klein onderaan.

    Het lettertype wordt zo groot als past, zodat alles op één A4 komt.
    """
    width, height = A4_SIZE
    margin = round(width * 0.045)
    picture_height = round(width * 0.24)
    bottom_block = round(width * 0.06) + picture_height + round(width * 0.03)
    list_top = margin + round(width * 0.105)
    list_height = height - margin - bottom_block - list_top

    list_columns = 3
    column_gap = round(width * 0.025)
    column_width = (width - 2 * margin - (list_columns - 1) * column_gap) / list_columns

    for font_size in range(32, 15, -1):
        blocks = _layout_rounds(segments, column_width, font_size, list_columns)
        needed = sum(block_height for _, _, _, block_height in blocks)

        if needed <= list_height:
            break

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    draw.text((margin, margin), f"{TOOL_NAME} · {len(segments)} lijnstukjes in 4 rondes", fill=INK_COLOR,
              font=get_font(round(width * 0.02)), anchor="lt")
    explanation = [
        "Leg je liniaal langs de lijn van het raster en trek een lijn van het eerste tot het tweede getal.",
        "Ronde 1 geeft de vorm, elke volgende ronde maakt de donkere delen donkerder.",
    ]

    for number, text in enumerate(explanation):
        draw.text((margin, margin + round(width * 0.04) + number * round(width * 0.022)), text,
                  fill=LINE_COLOR, font=get_font(round(width * 0.0135)), anchor="lt")

    font = get_font(font_size)
    heading_font = get_font(round(font_size * 1.1))
    line_height = round(font_size * 1.45)
    y = list_top

    for heading, entries, per_column, block_height in blocks:
        draw.text((margin, y), heading, fill=INK_COLOR, font=heading_font, anchor="lt",
                  stroke_width=1, stroke_fill=INK_COLOR)
        top = y + round(font_size * 2)

        for position, (label, text) in enumerate(entries):
            column, row = divmod(position, per_column)
            x = margin + column * (column_width + column_gap)
            entry_y = top + row * line_height + line_height / 2

            if label:
                draw.text((x, entry_y), label, fill=INK_COLOR, font=font, anchor="lm",
                          stroke_width=max(1, round(font_size / 22)), stroke_fill=INK_COLOR)

            draw.text((x + font.getlength("kolom 000  "), entry_y), text, fill=LINE_COLOR, font=font, anchor="lm")

        y += block_height

    _draw_answer(image, segments, photo, columns, rows, margin, picture_height)

    return image


def _layout_rounds(segments, column_width, font_size, list_columns):
    """Per ronde: (kop, regels, regels per kolom, hoogte). Een regel is (label of "", tekst)."""
    font = get_font(font_size)
    text_width = column_width - font.getlength("kolom 000  ")
    line_height = round(font_size * 1.45)
    blocks = []

    for round_number, (direction, _, _, heading) in enumerate(ROUNDS):
        per_line = {}

        for number, _, index, start, end in segments:
            if number == round_number:
                per_line.setdefault(index, []).append(f"{start + 1}–{end + 1}")

        entries = []

        for index, pieces in sorted(per_line.items()):
            label = ("rij " if direction == "h" else "kolom ") + str(index + 1)
            text = ""

            for piece in pieces:
                candidate = f"{text}  {piece}" if text else piece

                if text and font.getlength(candidate) > text_width:
                    entries.append((label, text))
                    label, text = "", piece
                else:
                    text = candidate

            entries.append((label, text))

        count = sum(len(pieces) for pieces in per_line.values())
        per_column = max(1, math.ceil(len(entries) / list_columns))
        block_height = round(font_size * 2) + per_column * line_height + round(font_size * 1.2)
        blocks.append((f"{heading} ({count})", entries, per_column, block_height))

    return blocks


def _draw_answer(image, segments, photo, columns, rows, margin, picture_height):
    """Onderaan, achter een gestippelde knip- of vouwlijn: je foto en het antwoord."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    caption_font = get_font(round(width * 0.012))

    picture_width = round(picture_height * (columns - 1) / (rows - 1))
    pictures_top = height - margin - round(width * 0.03) - picture_height
    gap = round(width * 0.06)
    pictures_left = (width - 2 * picture_width - gap) // 2

    fold_y = pictures_top - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    answer = _draw_segments(segments, columns, rows, picture_width * 2)
    answer = answer.resize((picture_width, picture_height), Image.LANCZOS)
    pictures = [(photo.resize((picture_width, picture_height), Image.LANCZOS), "Je foto"),
                (answer, "Zo wordt het")]

    for number, (picture, caption) in enumerate(pictures):
        x = pictures_left + number * (picture_width + gap)
        image.paste(picture, (x, pictures_top))
        draw.text((x + picture_width / 2, pictures_top + picture_height + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

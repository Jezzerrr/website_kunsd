"""Spiral Scribble: je portret als één lange spiraal, die je kriebelt in plaats van trekt.

Op blad 1 staat alleen een lichtgrijze, lege spiraal met twaalf "wijzers" zoals op een klok.
Er is nog niets van je foto te zien. Op blad 2 staat de "partituur": per rondje van de spiraal
één regel, van 12 uur rond tot 12 uur. Een dikke balk betekent: hier hard kriebelen (een grote
zigzag), een dunne balk: een klein kriebeltje, geen balk: gewoon de lijn volgen. In de partituur
is het gezicht door elkaar gehusseld en onherkenbaar; pas als je kriebelt, verschijnt het.

Het rekenwerk is licht (een paar duizend punten per rondje): geen probleem voor de Render free plan.

Nodig: numpy, scipy en Pillow.
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font
from src.helper_functions.grid_layout import A4_SIZE, fit_picture

TOOL_NAME = "Spiral Scribble"

# Per rondje zoveel vakjes in de partituur: 10 per "uur" van de klok
CELLS_PER_TURN = 120

# Hoe donker het minstens moet zijn voor kriebel 1, 2 en 3
LEVEL_THRESHOLDS = (0.2, 0.45, 0.7)

# Een kriebel van minder dan zoveel vakjes valt weg: dat teken je toch niet precies
MIN_RUN = 3

# Hoe groot de zigzag is per niveau, als deel van de afstand tussen twee rondjes (heen en terug).
# Bij niveau 3 raakt hij de buren bijna: zo wordt het daar echt donker.
AMPLITUDES = (0.0, 0.2, 0.4, 0.62)

# De afmeting van de spiraal op papier: A4 (300 dpi), met een witte rand van 5 mm
PX_PER_MM = 300 / 25.4
PAGE_MARGIN = round(A4_SIZE[0] * 5 / 210)
SPIRAL_RADIUS_MM = 88

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)
GUIDE_COLOR = (165, 165, 170)
SPOKE_COLOR = (215, 215, 220)
BAR_COLOR = (40, 40, 45)
ROW_COLOR = (243, 244, 247)


def image_to_spiral_scribble(img, turns=36, template=False, output_size=1800):
    """Maak een kriebelspiraal van een foto.

    Args:
        img: PIL Image. Het grootste vierkant uit het midden wordt gebruikt.
        turns: hoeveel rondjes de spiraal heeft. Meer = fijner, maar meer werk.
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (de lege spiraal, en de partituur).
        output_size: breedte van het voorbeeld in pixels.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    turns = int(turns)
    photo = ImageOps.fit(img.convert("RGB"), (800, 800), Image.LANCZOS, centering=(0.5, 0.42))
    levels = find_levels(_darkness(photo), turns)

    if template:
        return [_draw_spiral_page(turns), _draw_score_page(levels, photo)]

    return _draw_result(levels, output_size)


def find_levels(darkness, turns):
    """Per rondje en per vakje hoe hard je kriebelt (0 tot en met 3), als array (rondjes, vakjes).

    Rondje 1 begint in het midden bij 12 uur; het vakje telt met de klok mee.
    """
    size = darkness.shape[0]
    center = (size - 1) / 2
    spacing = (size / 2) * 0.98 / turns

    turn, cell = np.mgrid[0:turns, 0:CELLS_PER_TURN].astype(np.float32)
    theta = 2 * math.pi * (turn + (cell + 0.5) / CELLS_PER_TURN)
    radius = spacing * theta / (2 * math.pi)
    x = center + radius * np.sin(theta)
    y = center - radius * np.cos(theta)

    # Iets uitgesmeerd, zodat een vakje het gemiddelde ziet van wat eronder valt
    smooth = ndimage.gaussian_filter(darkness, spacing * 0.35)
    tone = ndimage.map_coordinates(smooth, [y.ravel(), x.ravel()], order=1).reshape(turns, CELLS_PER_TURN)

    levels = np.digitize(tone, LEVEL_THRESHOLDS).astype(np.int8)
    levels = ndimage.median_filter(levels, size=(1, 5), mode="wrap")

    for row in levels:
        _remove_short_runs(row)

    return levels


def _remove_short_runs(row):
    """Een stukje korter dan MIN_RUN vakjes krijgt het niveau van zijn buurman (die het langst is)."""
    for _ in range(3):
        changes = np.flatnonzero(np.diff(row)) + 1
        starts = np.r_[0, changes]
        ends = np.r_[changes, len(row)]
        changed = False

        for number, (start, end) in enumerate(zip(starts, ends)):
            if end - start >= MIN_RUN:
                continue

            before = row[start - 1] if start > 0 else None
            after = row[end] if end < len(row) else None
            neighbours = [value for value in (before, after) if value is not None]

            if neighbours:
                # Kies de buur die het dichtst bij ligt in donkerte, bij gelijkspel de lichtste
                row[start:end] = min(neighbours, key=lambda value: (abs(int(value) - int(row[start])), value))
                changed = True

        if not changed:
            break


def _darkness(photo):
    """Per pixel hoe donker het is (0 = wit, 1 = zwart), met wat extra lokaal contrast.

    Wit blijft wit: een uitgeknipte achtergrond wordt geen kriebelwerk.
    """
    gray = np.asarray(photo.convert("L"), dtype=np.float32) / 255
    darkness = 1 - gray
    content = darkness > 0.03
    sample = darkness[content] if content.mean() > 0.05 else darkness.ravel()

    low, high = np.percentile(sample, [1, 99])
    darkness = np.clip((darkness - low) / max(high - low, 1e-3), 0, 1)

    mean = ndimage.gaussian_filter(darkness, photo.width / 20)
    darkness = np.clip(darkness + 0.6 * (darkness - mean), 0, 1)
    darkness[gray > 0.97] = 0

    return darkness


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

def _spiral_points(turns, radius, center, step):
    """Punten langs de spiraal (in pixels), om de ongeveer step pixels, met per punt het rondje en het vakje."""
    spacing = radius / turns
    total = turns * 2 * math.pi
    # Lengte van een Archimedische spiraal, ruwweg: pi * rondjes^2 * afstand
    count = max(1000, int(math.pi * turns * turns * spacing / step))
    # Gelijke stapjes langs de lijn: theta groeit met de wortel van de afgelegde weg
    theta = np.sqrt(np.linspace(0, 1, count, dtype=np.float64)) * total
    r = spacing * theta / (2 * math.pi)
    x = center[0] + r * np.sin(theta)
    y = center[1] - r * np.cos(theta)

    position = theta / (2 * math.pi)
    turn = np.minimum(position.astype(int), turns - 1)
    cell = np.minimum(((position - turn) * CELLS_PER_TURN).astype(int), CELLS_PER_TURN - 1)

    return x, y, turn, cell


def _scribble(levels, radius, center, scale):
    """De gekriebelde lijn als lijst punten: een zigzag dwars op de spiraal, zo groot als het niveau zegt."""
    turns = levels.shape[0]
    spacing = radius / turns
    x, y, turn, cell = _spiral_points(turns, radius, center, step=max(0.6, spacing / 25))

    amplitude = np.asarray(AMPLITUDES, dtype=np.float64)[levels[turn, cell]] * spacing
    # Zachte overgang, zoals je hand ook niet in één keer van klein naar groot gaat
    amplitude = ndimage.uniform_filter1d(amplitude, max(3, int(spacing / max(0.6, spacing / 25) * 0.6)))

    # De richting dwars op de lijn
    dx, dy = np.gradient(x), np.gradient(y)
    length = np.hypot(dx, dy) + 1e-9
    normal_x, normal_y = -dy / length, dx / length

    # Een zigzag van ongeveer 1,1 mm per heen-en-weer (op papier)
    wavelength = 1.1 * scale
    distance = np.cumsum(length)
    offset = amplitude * np.sin(2 * math.pi * distance / wavelength)

    return list(zip(x + offset * normal_x, y + offset * normal_y))


def _draw_result(levels, output_size, pen_mm=0.4):
    """Zo ziet het eruit als de spiraal helemaal gekriebeld is."""
    supersample = 2
    size = output_size * supersample
    radius = size * 0.47
    scale = radius / SPIRAL_RADIUS_MM    # pixels per mm op papier

    image = Image.new("L", (size, size), 255)
    draw = ImageDraw.Draw(image)
    points = _scribble(levels, radius, (size / 2, size / 2), scale)
    draw.line(points, fill=INK_COLOR[0], width=max(1, round(pen_mm * scale)), joint="curve")

    return image.resize((output_size, output_size), Image.LANCZOS).convert("RGB")


def _draw_spiral_page(turns):
    """Blad 1: de lege spiraal in lichtgrijs, met twaalf wijzers en de rondjes genummerd. Hierop teken je."""
    width, height = A4_SIZE
    radius = SPIRAL_RADIUS_MM * PX_PER_MM
    center = (width / 2, height / 2)
    spacing = radius / turns

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)
    clock_font = get_font(round(width * 0.016))
    turn_font = get_font(round(width * 0.0085))

    # De wijzers, met de uren erbuiten, en een streepje op elk half uur
    for hour in range(12):
        angle = 2 * math.pi * hour / 12
        sin, cos = math.sin(angle), -math.cos(angle)
        inner = spacing * 1.5
        draw.line((center[0] + inner * sin, center[1] + inner * cos,
                   center[0] + radius * sin, center[1] + radius * cos), fill=SPOKE_COLOR, width=2)
        label = radius + width * 0.025
        draw.text((center[0] + label * sin, center[1] + label * cos), str(hour or 12), fill=LINE_COLOR,
                  font=clock_font, anchor="mm")

    for half in range(12):
        angle = 2 * math.pi * (half + 0.5) / 12
        sin, cos = math.sin(angle), -math.cos(angle)
        draw.line((center[0] + (radius + 8) * sin, center[1] + (radius + 8) * cos,
                   center[0] + (radius + 28) * sin, center[1] + (radius + 28) * cos), fill=GUIDE_COLOR, width=3)

    # De spiraal zelf
    x, y, _, _ = _spiral_points(turns, radius, center, step=3)
    draw.line(list(zip(x, y)), fill=GUIDE_COLOR, width=3, joint="curve")

    # Startpunt in het midden
    dot = round(width * 0.003)
    draw.ellipse((center[0] - dot, center[1] - dot, center[0] + dot, center[1] + dot), fill=LINE_COLOR)

    # Rondjes genummerd langs de wijzer van 12 uur: rondje t begint daar op afstand (t - 1) keer de afstand
    for turn in range(5, turns + 1, 5):
        ry = center[1] - (turn - 1) * spacing
        draw.text((center[0] - spacing * 0.25, ry - spacing * 0.5), str(turn), fill=NUMBER_COLOR, font=turn_font,
                  anchor="rm", stroke_width=4, stroke_fill=PAPER_COLOR)

    small = get_font(round(width * 0.011))
    draw.text((PAGE_MARGIN, PAGE_MARGIN), f"{TOOL_NAME} · blad 1: hierop teken je", fill=NUMBER_COLOR,
              font=small, anchor="lt")
    draw.text((center[0], center[1] + radius + width * 0.075),
              "Begin in het midden en volg de lijn met de klok mee", fill=NUMBER_COLOR, font=small, anchor="mm")
    draw.text((width - PAGE_MARGIN, height - PAGE_MARGIN), "Hoe je kriebelt staat op blad 2", fill=NUMBER_COLOR,
              font=small, anchor="rb")

    return image


def _draw_score_page(levels, photo):
    """Blad 2: uitleg, de vier soorten kriebel op ware grootte, de partituur en het antwoord achter de vouwlijn."""
    turns = levels.shape[0]
    width, height = A4_SIZE
    margin = round(width * 0.045)
    unit = width

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    title_font = get_font(round(unit * 0.02))
    text_font = get_font(round(unit * 0.0128))
    small_font = get_font(round(unit * 0.0105))

    draw.text((margin, margin), f"{TOOL_NAME} · de partituur: {turns} rondjes", fill=INK_COLOR, font=title_font,
              anchor="lt")
    explanation = [
        "Zet je pen in het midden van blad 1 en volg de spiraal met de klok mee, zonder op te tillen.",
        "Elke regel hieronder is één rondje, van 12 uur tot 12 uur. De balk zegt hoe hard je kriebelt:",
    ]
    y = margin + round(unit * 0.04)

    for text in explanation:
        draw.text((margin, y), text, fill=LINE_COLOR, font=text_font, anchor="lt")
        y += round(unit * 0.021)

    # De vier soorten kriebel, op ware grootte voor dit aantal rondjes
    y += round(unit * 0.012)
    spacing_px = SPIRAL_RADIUS_MM * PX_PER_MM / turns
    legend = ["Geen balk: gewoon de lijn volgen", "Dunne balk: klein kriebeltje",
              "Halve balk: flink kriebelen", "Volle balk: zo groot dat je de buren raakt"]
    row_height = round(unit * 0.0185)
    legend_column = (width - 2 * margin) / 2

    for level, text in enumerate(legend):
        column, line = divmod(level, 2)
        x = margin + column * legend_column
        ly = y + line * round(spacing_px * 2.6 + unit * 0.004)
        bar_left = x
        bar_right = x + round(unit * 0.06)
        _draw_bar(draw, bar_left, bar_right, ly + spacing_px, level, row_height)

        sample_left = bar_right + round(unit * 0.02)
        sample_right = sample_left + round(unit * 0.12)
        _draw_sample(draw, sample_left, sample_right, ly + spacing_px, level, spacing_px)
        draw.text((sample_right + round(unit * 0.02), ly + spacing_px), text, fill=LINE_COLOR, font=small_font,
                  anchor="lm")

    y += 2 * round(spacing_px * 2.6 + unit * 0.004) + round(unit * 0.015)

    # Ruimte voor de partituur: alles tussen de uitleg en het antwoord
    picture_height = round(width * 0.22)
    bottom_block = round(width * 0.06) + picture_height + round(width * 0.03)
    score_top = y + round(unit * 0.03)
    score_bottom = height - margin - bottom_block
    row_height = min(round(unit * 0.028), (score_bottom - score_top) / turns)

    label_space = round(unit * 0.035)
    left = margin + label_space
    right = width - margin - label_space
    cell_width = (right - left) / CELLS_PER_TURN

    # Uren erboven, met lichte lijnen erdoor
    score_height = row_height * turns
    hour_font = get_font(round(unit * 0.0115))

    for row in range(turns):
        top = score_top + row * row_height
        if row % 2 == 0:
            draw.rectangle((left, top, right, top + row_height), fill=ROW_COLOR)

    for hour in range(13):
        x = left + hour * (right - left) / 12
        draw.line((x, score_top - round(unit * 0.004), x, score_top + score_height), fill=SPOKE_COLOR, width=2)
        draw.text((x, score_top - round(unit * 0.009)), str(hour % 12 or 12), fill=LINE_COLOR, font=hour_font,
                  anchor="mb")

    number_font = get_font(max(14, min(round(unit * 0.0095), round(row_height * 0.72))))

    for row in range(turns):
        top = score_top + row * row_height
        middle = top + row_height / 2
        label_color = INK_COLOR if (row + 1) % 5 == 0 or row == 0 else NUMBER_COLOR
        draw.text((left - round(unit * 0.008), middle), str(row + 1), fill=label_color, font=number_font,
                  anchor="rm")
        draw.text((right + round(unit * 0.008), middle), str(row + 1), fill=label_color, font=number_font,
                  anchor="lm")

        changes = np.flatnonzero(np.diff(levels[row])) + 1
        for start, end in zip(np.r_[0, changes], np.r_[changes, CELLS_PER_TURN]):
            level = int(levels[row][start])
            if level:
                _draw_bar(draw, left + start * cell_width, left + end * cell_width, middle, level, row_height)

    _draw_answer(image, levels, photo, margin, picture_height)

    return image


def _draw_bar(draw, left, right, middle, level, row_height):
    """Een balk in de partituur: hoe dikker, hoe harder kriebelen. Bij niveau 0 alleen een dun lijntje."""
    if level == 0:
        draw.line((left, middle, right, middle), fill=GUIDE_COLOR, width=2)
        return

    half = row_height * (0.12, 0.25, 0.42)[level - 1]
    draw.rectangle((left, middle - half, right, middle + half), fill=BAR_COLOR)


def _draw_sample(draw, left, right, middle, level, spacing):
    """Een stukje kriebel op ware grootte, met de buurlijnen erboven en eronder in lichtgrijs."""
    for neighbour in (-1, 1):
        draw.line((left, middle + neighbour * spacing, right, middle + neighbour * spacing), fill=SPOKE_COLOR,
                  width=2)

    wavelength = 1.1 * PX_PER_MM
    x = np.arange(left, right, 1.0)
    y = middle + AMPLITUDES[level] * spacing * np.sin(2 * math.pi * (x - left) / wavelength)
    draw.line(list(zip(x, y)), fill=INK_COLOR, width=round(0.4 * PX_PER_MM), joint="curve")


def _draw_answer(image, levels, photo, margin, max_height):
    """Onderaan, achter een gestippelde knip- of vouwlijn: je foto en het antwoord, naast elkaar."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    caption_font = get_font(round(width * 0.012))

    gap = round(width * 0.06)
    side, _ = fit_picture((1, 1), (width - 2 * margin - gap) / 2, max_height)
    pictures_top = height - margin - round(width * 0.03) - max_height + (max_height - side) // 2
    pictures_left = (width - 2 * side - gap) // 2

    fold_y = height - margin - round(width * 0.03) - max_height - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    # Ronde foto, net als de spiraal
    mask = Image.new("L", (side * 2, side * 2), 0)
    ImageDraw.Draw(mask).ellipse((side * 0.06, side * 0.06, side * 1.94, side * 1.94), fill=255)
    mask = mask.resize((side, side), Image.LANCZOS)
    round_photo = Image.new("RGB", (side, side), PAPER_COLOR)
    round_photo.paste(photo.resize((side, side), Image.LANCZOS), (0, 0), mask)

    answer = _draw_result(levels, side * 2, pen_mm=0.4).resize((side, side), Image.LANCZOS)
    pictures = [(round_photo, "Je foto"), (answer, "Zo wordt het")]

    for number, (picture, caption) in enumerate(pictures):
        x = pictures_left + number * (side + gap)
        image.paste(picture, (x, pictures_top))
        draw.text((x + side / 2, pictures_top + side + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

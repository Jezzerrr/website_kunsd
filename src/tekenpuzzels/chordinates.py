"""Chordinates: een portret van alleen rechte lijnen, om zelf na te tekenen met een liniaal.

Rond een cirkel staan genummerde punten. Het algoritme kiest een paar honderd lijnen van punt naar
punt. Trek je die met een liniaal en een fineliner, dan verschijnt langzaam de foto: waar veel lijnen
elkaar kruisen wordt het donker. Het idee komt van string art (draad om spijkers), maar dan met pen.

Hoe het werkt (licht genoeg voor de Render free plan):
1. De foto wordt een klein vierkant (WORK_SIZE pixels): hoe donker moet elk plekje worden. Randen
   (ogen, haar, baard) worden iets aangezet, anders verdwijnen ze tussen de lange lijnen.
2. Elke mogelijke lijn tussen twee punten krijgt een score: hoe donker het gemiddeld nog moet worden
   langs die lijn. De beste lijn wordt "getekend": langs die lijn wordt het nog-te-tekenen-donker minder.
3. Dat herhalen we tot er n_lines lijnen zijn. Bij meer lijnen telt elke lijn iets minder zwaar,
   zodat de lijnen zich over het hele plaatje verdelen: meer lijnen = meer diepte en detail.
   De scores bijwerken gaat snel met een ijle matrix (welke lijn loopt over welke pixel).
4. Het resultaat is óf een voorbeeld van de getekende lijnen, óf het tekenvel van twee bladen:
   blad 1 de cirkel met genummerde punten (zo groot mogelijk, om op te tekenen), blad 2 per punt de
   lijnen die daar beginnen, met je foto en het "antwoord" (het voorbeeld) klein erbij.

Nodig: numpy, scipy en Pillow.
"""

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, sparse

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font

# Aantal punten rond de cirkel. Bij een cirkel van 18 cm liggen ze bijna 4 mm uit elkaar: genoeg
# ruimte voor een nummer bij elk punt, en genoeg richtingen voor een herkenbaar silhouet.
N_PINS = 150

# Het rekenwerk gebeurt op een vierkant van zoveel pixels
WORK_SIZE = 200

# Steekproefpunten langs elke lijn (voor de score)
SAMPLES = 120

# Dikte van een getekende lijn, als deel van de middellijn: een fineliner van 0,3 mm op een cirkel
# van 19 cm. Dat bepaalt hoeveel donker één lijn "oplevert".
PEN_WIDTH = 0.3 / 190

# Lijnen tussen punten die dichter bij elkaar liggen zijn te kort om iets te doen
MIN_PIN_GAP = 8

# Randen aanzetten (hoeveel van het verschil met een vervaagde versie erbij komt)
EDGE_BOOST = 2.0

# Lichte delen (de achtergrond) krijgen een kleine straf, zodat lijnen er liever omheen gaan
BACKGROUND_PENALTY = 0.05

# Tot zoveel lijnen telt elke lijn als een volle penstreek. Bij meer lijnen telt elke lijn naar
# verhouding minder, anders zijn de donkere delen na ongeveer zoveel lijnen "af" en voegen extra
# lijnen niets meer toe.
FULL_INK_LINES = 360

# De naam op het tekenvel
TOOL_NAME = "Chordinates"

# Het tekenvel: A4 bij 300 dpi
A4_SIZE = (2480, 3508)

# Witte rand om het tekenvel: 5 mm, zo smal als de meeste printers aankunnen. Het tekenvel wordt
# zonder extra marge geprint (zie js/jouw_kunst.js), dus deze rand is de enige.
PAGE_MARGIN = round(A4_SIZE[0] * 5 / 210)

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)


def image_to_chordinates(img, n_lines=600, contrast=1.2, template=False, output_size=2400):
    """Maak een portret van rechte lijnen tussen punten op een cirkel.

    Args:
        img: PIL Image. Het midden (een vierkant) wordt gebruikt.
        n_lines: aantal lijnen. Meer = meer diepte en detail, maar ook meer tekenwerk.
        contrast: groter dan 1 maakt lichte delen lichter (minder lijnen in de achtergrond).
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (zie _draw_circle_page en _draw_list_page).
        output_size: breedte van het voorbeeld in pixels.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    target = _target_darkness(img, contrast)
    lines = find_lines(target, int(n_lines))

    if template:
        return [_draw_circle_page(), _draw_list_page(lines, _center_square(img.convert("RGB")))]

    return _draw_preview(lines, output_size)


def find_lines(target, n_lines, n_pins=N_PINS):
    """De gekozen lijnen als lijst (punt a, punt b), met punten genummerd vanaf 0 en a < b."""
    size = target.shape[0]
    pins = _pin_positions(n_pins, size)

    # Alle mogelijke lijnen, behalve heel korte
    starts, ends = np.triu_indices(n_pins, 1)
    gap = np.minimum(ends - starts, n_pins - (ends - starts))
    starts, ends = starts[gap >= MIN_PIN_GAP], ends[gap >= MIN_PIN_GAP]

    # Voor elke lijn de pixels van de steekproefpunten
    t = np.linspace(0.0, 1.0, SAMPLES)[None, :]
    xs = np.rint(pins[starts, 0:1] + (pins[ends, 0:1] - pins[starts, 0:1]) * t).astype(np.int32)
    ys = np.rint(pins[starts, 1:2] + (pins[ends, 1:2] - pins[starts, 1:2]) * t).astype(np.int32)
    pixel_ids = ys * size + xs

    # Ijle matrix: hoe vaak elke lijn (kolom) over elke pixel (rij) komt
    line_ids = np.repeat(np.arange(len(starts)), SAMPLES)
    crossings = sparse.csr_matrix(
        (np.ones(line_ids.size, dtype=np.float32), (pixel_ids.ravel(), line_ids)),
        shape=(size * size, len(starts)),
    )

    remaining = target.astype(np.float32).ravel()
    scores = remaining[pixel_ids].sum(axis=1)
    ink = PEN_WIDTH * size * min(1.0, FULL_INK_LINES / max(1, n_lines))
    chosen = []

    for _ in range(min(n_lines, len(starts))):
        best = int(np.argmax(scores))

        chosen.append((int(starts[best]), int(ends[best])))
        scores[best] = -np.inf

        # "Tekenen": elk pixel onder de lijn wordt minder donker, en de scores van alle lijnen
        # over die pixels gaan omlaag
        pixels = np.unique(pixel_ids[best])
        remaining[pixels] -= ink
        scores -= ink * np.asarray(crossings[pixels].sum(axis=0)).ravel()

    return chosen


def _target_darkness(img, contrast):
    """Een vierkant: 1 = zo donker als kan, 0 = wit laten. Buiten de cirkel heel negatief."""
    img = _center_square(img.convert("L")).resize((WORK_SIZE, WORK_SIZE), Image.LANCZOS)

    gray = np.asarray(img, dtype=np.float32) / 255.0

    # Contrast oprekken: het donkerste en lichtste procent van de foto worden zwart en wit
    low, high = np.percentile(gray, [1, 99])
    gray = np.clip((gray - low) / max(high - low, 1e-3), 0, 1)

    darkness = (1.0 - gray) ** max(0.3, float(contrast))

    # Randen aanzetten: ogen, wenkbrauwen en de rand van het haar tellen zwaarder
    blurred = ndimage.gaussian_filter(darkness, sigma=WORK_SIZE / 25, mode="nearest")
    darkness = np.clip(darkness + EDGE_BOOST * (darkness - blurred), 0, 1)

    target = darkness - BACKGROUND_PENALTY

    # Buiten de cirkel komen geen lijnen (lijnen tussen punten op de cirkel komen daar ook nooit,
    # maar door afronden kan een steekproefpunt er net buiten vallen)
    yy, xx = np.mgrid[0:WORK_SIZE, 0:WORK_SIZE]
    center = (WORK_SIZE - 1) / 2
    target[(xx - center) ** 2 + (yy - center) ** 2 > (center + 0.5) ** 2] = 0

    return target


def _center_square(img):
    """Het grootste vierkant uit het midden van de foto: daar komt de cirkel."""
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2

    return img.crop((left, top, left + side, top + side))


def _pin_positions(n_pins, size):
    """De punten op de cirkel, als (x, y) in pixels. Punt 0 staat bovenaan, daarna met de klok mee."""
    center = (size - 1) / 2
    radius = center
    angles = -math.pi / 2 + 2 * math.pi * np.arange(n_pins) / n_pins

    return np.stack([center + radius * np.cos(angles), center + radius * np.sin(angles)], axis=1)


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

# Het voorbeeld wordt op dubbele grootte getekend en dan verkleind: dat geeft gladde lijnen.
SUPERSAMPLE = 2


def _draw_preview(lines, output_size):
    """Zo ziet het eruit als alle lijnen getekend zijn."""
    size = output_size * SUPERSAMPLE
    margin = round(size * 0.03)
    diameter = size - 2 * margin
    pins = _pin_positions(N_PINS, diameter) + margin

    image = Image.new("RGB", (size, size), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    line_width = max(1, round(PEN_WIDTH * diameter))

    for a, b in lines:
        draw.line((tuple(pins[a]), tuple(pins[b])), fill=INK_COLOR, width=line_width)

    # De punten heel licht, zodat je ziet waar ze zaten
    dot = max(1, round(size * 0.0015))

    for x, y in pins:
        draw.ellipse((x - dot, y - dot, x + dot, y + dot), fill=(200, 200, 200))

    return image.resize((output_size, output_size), Image.LANCZOS)


def _draw_pin(image, index, position, center, radius, label_offset, fonts):
    """Eén punt op de cirkel met zijn nummer erbuiten; elk tiende punt iets groter en donkerder.

    Het nummer staat in de richting van het middelpunt (als een spaak), zodat de nummers boven en
    onder op de cirkel niet over elkaar heen vallen. Links staat het andersom, zodat je het niet
    op zijn kop leest.
    """
    x, y = position
    dot = fonts["dot"]
    ImageDraw.Draw(image).ellipse((x - dot, y - dot, x + dot, y + dot), fill=LINE_COLOR)

    is_tenth = (index + 1) % 10 == 0
    font = fonts["bold"] if is_tenth else fonts["normal"]
    color = LINE_COLOR if is_tenth else NUMBER_COLOR
    text = str(index + 1)

    # Het nummer eerst plat op een eigen plaatje, dan draaien
    left, top, right, bottom = font.getbbox(text)
    label = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    ImageDraw.Draw(label).text((2 - left, 2 - top), text, fill=255, font=font)

    dx, dy = x - center[0], y - center[1]
    angle = math.degrees(math.atan2(-dy, dx))

    if dx < -1e-6:
        angle += 180

    label = label.rotate(angle, expand=True, resample=Image.BICUBIC)

    # Het midden van het nummer op een vaste afstand buiten de cirkel
    distance = label_offset + max(right - left, bottom - top) / 2
    label_x = x + dx / radius * distance - label.width / 2
    label_y = y + dy / radius * distance - label.height / 2

    image.paste(Image.new("RGB", label.size, color), (round(label_x), round(label_y)), label)


def _draw_circle_page():
    """Blad 1: alleen de cirkel met genummerde punten, zo groot als op A4 past. Hierop teken je."""
    width, height = A4_SIZE
    margin = PAGE_MARGIN
    label_space = round(width * 0.032)      # ruimte voor de nummers buiten de cirkel
    diameter = width - 2 * (margin + label_space)
    left = (width - diameter) // 2
    top = (height - diameter) // 2

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    draw.ellipse((left, top, left + diameter, top + diameter),
                 outline=(228, 228, 228), width=max(1, round(width * 0.0006)))

    pins = _pin_positions(N_PINS, diameter) + np.array([left, top])
    center = np.array([left + diameter / 2, top + diameter / 2])
    fonts = {
        "dot": max(2, round(width * 0.0022)),
        "normal": get_font(round(width * 0.0105)),
        "bold": get_font(round(width * 0.0125)),
    }

    for index, position in enumerate(pins):
        _draw_pin(image, index, position, center, diameter / 2, label_space * 0.12, fonts)

    small = get_font(round(width * 0.011))
    draw.text((margin, margin), f"{TOOL_NAME} \u00b7 blad 1: hierop teken je", fill=NUMBER_COLOR,
              font=small, anchor="lt")
    draw.text((width - margin, height - margin), "De lijnen staan op blad 2", fill=NUMBER_COLOR,
              font=small, anchor="rb")

    return image


def _draw_list_page(lines, photo):
    """Blad 2: per beginpunt de eindpunten, met je foto en het "antwoord" klein onderaan.

    Onderaan, achter een knip- of vouwlijn: wie het antwoord niet wil zien, vouwt het weg.
    Bij heel veel lijnen wordt het blad iets langer; printen past het dan vanzelf op één pagina.
    """
    width = A4_SIZE[0]
    margin = round(width * 0.045)

    # Per beginpunt de eindpunten, van klein naar groot. Zo werk je de cirkel rond: liniaal
    # op punt 1, lijnen naar alle punten achter de 1, dan door naar punt 2, enzovoort.
    groups = {}

    for a, b in sorted(lines):
        groups.setdefault(a, []).append(b)

    title_font = get_font(round(width * 0.02))
    text_font = get_font(round(width * 0.0135))
    caption_font = get_font(round(width * 0.012))
    entry_font = get_font(round(width * 0.0125))
    start_font = get_font(round(width * 0.013))

    # De lijst in vier kolommen; lange rijen lopen door op een volgende regel
    columns = 4
    column_gap = round(width * 0.025)
    column_width = (width - 2 * margin - (columns - 1) * column_gap) / columns
    start_width = round(width * 0.04)
    number_width = round(width * 0.036)
    per_line = max(1, int((column_width - start_width) // number_width))

    text_lines = []

    for a, ends in groups.items():
        for chunk_start in range(0, len(ends), per_line):
            text_lines.append((a if chunk_start == 0 else None, ends[chunk_start:chunk_start + per_line]))

    # Bovenaan titel en uitleg, dan de lijst; onderaan twee kleine plaatjes naast elkaar
    picture = round(width * 0.22)
    list_top = margin + round(width * 0.11)
    line_height = round(width * 0.02)
    rows = math.ceil(len(text_lines) / columns)
    bottom_block = round(width * 0.06) + picture + round(width * 0.03)   # knip-/vouwlijn, plaatjes, bijschrift
    height = max(A4_SIZE[1], list_top + rows * line_height + bottom_block + margin)
    pictures_top = height - margin - round(width * 0.03) - picture

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    draw.text((margin, margin), f"{TOOL_NAME} \u00b7 {len(lines)} lijnen", fill=INK_COLOR,
              font=title_font, anchor="lt")
    explanation = [
        "Leg je liniaal op het vetgedrukte punt en trek een lijn naar elk punt dat erachter staat.",
        "Dan door naar het volgende punt. Streep af wat klaar is, dan raak je je plek niet kwijt.",
    ]

    for number, text in enumerate(explanation):
        draw.text((margin, margin + round(width * 0.04) + number * round(width * 0.022)), text,
                  fill=LINE_COLOR, font=text_font, anchor="lt")

    # Je foto (rond, zoals de cirkel) en het antwoord
    mask = Image.new("L", (picture, picture), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, picture - 1, picture - 1), fill=255)
    round_photo = Image.new("RGB", (picture, picture), PAPER_COLOR)
    round_photo.paste(photo.resize((picture, picture), Image.LANCZOS), (0, 0), mask)
    answer = _draw_preview(lines, picture)

    gap = round(width * 0.06)
    pictures_left = (width - 2 * picture - gap) // 2

    # Gestippelde knip- of vouwlijn boven de plaatjes
    fold_y = pictures_top - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    for number, (picture_image, caption) in enumerate([(round_photo, "Je foto"), (answer, "Zo wordt het")]):
        x = pictures_left + number * (picture + gap)
        image.paste(picture_image, (x, pictures_top))
        draw.text((x + picture / 2, pictures_top + picture + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

    # De lijst
    for position, (start, ends) in enumerate(text_lines):
        column, row = divmod(position, rows)
        x0 = margin + column * (column_width + column_gap)
        y = list_top + row * line_height + line_height / 2

        if start is not None:
            draw.text((x0, y), str(start + 1), fill=INK_COLOR, font=start_font, anchor="lm",
                      stroke_width=1, stroke_fill=INK_COLOR)

        for index, end in enumerate(ends):
            x = x0 + start_width + index * number_width
            draw.text((x, y), str(end + 1), fill=LINE_COLOR, font=entry_font, anchor="lm")

    return image

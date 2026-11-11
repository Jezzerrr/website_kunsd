"""Pen Up: een portret van evenwijdige schuine lijnstukjes. Het plaatje zit verstopt in een lijst getallen.

Het idee: schuine hulplijnen over het hele plaatje. Op elke hulplijn teken je alleen de stukjes waar
de foto donker is: pen erop, lijn trekken, pen eraf ("pen up"). Zo ontstaat het portret.

Het tekenvel verraadt niets: op blad 1 staat alleen een gelijkmatig raster van puntjes op heel lichte
hulplijnen, met een nummer bij het begin van elke lijn. Het nummeren begint rechtsonder: zo krijgen de
nummers onder het plaatje maar twee cijfers en passen ze op één rij. Elke lijn loopt met een dun lijntje
door tot aan zijn eigen nummer, zodat je niet hoeft te raden welk nummer bij welke lijn hoort. Op blad 2 staat per lijn welke stukjes je tekent,
bijvoorbeeld "62   1-14   31-37": op lijn 62 teken je van punt 1 tot punt 14 en van punt 31 tot punt 37.
Je telt steeds vanaf het begin van de lijn, dus een telfout werkt niet door. Pas tijdens het tekenen zie
je wat het wordt.

Hoe het werkt (licht: numpy, scipy en Pillow, minder dan een seconde):
1. De foto wordt grijs en het contrast wordt opgerekt. Met de schuif "Contrast" tellen details ten
   opzichte van hun omgeving zwaarder (lokaal contrast): dan komt bijvoorbeeld blond haar voor een
   lichte muur toch op papier.
2. Langs elke hulplijn kijken we op elk punt hoe donker de foto daar is.
3. De donkerste INK deel van alle punten wordt "inkt" (zo werkt het op lichte en donkere foto's).
4. Opeenvolgende inkt-punten op een lijn vormen samen één stukje om te tekenen.

Het tekenvel moet er strak uitzien, ook ingezoomd en geprint. Daarom:
- de hulplijnen worden per pixel uitgerekend (hoe ver ligt dit pixel van de lijn), met zachte randjes;
- elk puntje en streepje is een stempel die op 16x zo groot is getekend en verkleind, met een aparte
  stempel voor elke positie tussen twee pixels in: alle rondjes zijn precies even groot en even rond.
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, get_font
from src.helper_functions.grid_layout import A4_SIZE, fit_picture

TOOL_NAME = "Pen Up"

# A4 bij 300 dpi: zoveel pixels per millimeter
MM = A4_SIZE[0] / 210

# Afstand tussen de punten op een lijn, als deel van de afstand tussen de lijnen
POINT_RATIO = 1.0

# Zoveel van alle punten wordt inkt
INK = 0.30

# Een stukje bestaat uit minstens zoveel punten (2 = een lijntje van één puntafstand)
MIN_RUN = 2

# Lijnnummers: lettergrootte, en hoe ver onder of naast het kader het nummer staat (in mm). Het
# verbindingslijntje (de lijn, doorgetrokken tot zijn nummer) is iets donkerder dan de hulplijnen.
LABEL_FONT_MM = 2.0
LABEL_DROP_MM = 2.4
LABEL_PAD_MM = 0.35
LEADER_GRAY = 185

# Het tekenvel: witte rand, ruimte voor de lijnnummers en de titel (in mm)
PAGE_MARGIN_MM = 8
LABEL_MM = 8
TITLE_MM = 6

PAPER_COLOR = (255, 255, 255)
INK_COLOR = (25, 25, 30)

# Blad 1, in grijswaarden (0 = zwart, 255 = wit): zo licht dat het in je tekening niet stoort.
# Elk 10e punt is het duidelijkst (een groter puntje), elk 5e punt heeft een klein dwars streepje.
GUIDE_GRAY = 215
GUIDE_WIDTH_MM = 0.10
DOT_GRAY = 160
DOT_RADIUS_MM = 0.21
TENTH_GRAY = 110
TENTH_RADIUS_MM = 0.36
FIFTH_GRAY = 140
FIFTH_LENGTH_MM = 1.1
FIFTH_WIDTH_MM = 0.16

# Stempels: zo vaak groter tekenen voor het verkleinen, en zoveel posities tussen twee pixels
STAMP_DETAIL = 16
SUBPIXEL = 4


def image_to_pen_up(img, lines_per_10cm=40, angle=35, contrast=50, template=False, output_size=1800):
    """Maak een Pen Up-portret.

    Args:
        img: PIL Image. De hele foto wordt gebruikt (een liggende foto krijgt liggend A4).
        lines_per_10cm: hoe dicht de hulplijnen liggen: 40 = elke 2,5 mm een lijn.
        angle: hoek van de hulplijnen in graden (10 tot 80), oplopend van links naar rechts.
        contrast: 0 tot 100; hoger = details ten opzichte van hun omgeving tellen zwaarder.
        template: False = voorbeeld van hoe het eruitziet als het af is (één afbeelding),
            True = het tekenvel: een lijst van twee A4-bladen (de puntjes, en de lijst per lijn).
        output_size: breedte van het voorbeeld in pixels.

    Returns:
        PIL Image (RGB), of bij template=True een lijst van twee PIL Images.
    """
    img = img.convert("RGB")
    spacing = 100 / float(lines_per_10cm) * MM
    angle = -float(np.clip(angle, 10, 80))      # negatief: in plaatjes loopt y naar beneden
    paper, frame = _layout(img.size)
    lines = find_lines(img, frame, spacing, angle, float(np.clip(contrast, 0, 100)) / 100)

    if template:
        return [_draw_grid_page(lines, frame, paper, spacing, angle), _draw_code_page(lines, img, frame, angle)]

    return _draw_preview(lines, frame, angle, output_size)


# ---------------------------------------------------------------------------
# Rekenen
# ---------------------------------------------------------------------------

def _layout(image_size):
    """Papier (staand of liggend A4) en het kader waarin het plaatje komt: (links, boven, breedte, hoogte)."""
    width, height = image_size
    paper = (A4_SIZE[1], A4_SIZE[0]) if width > height else A4_SIZE
    border = (PAGE_MARGIN_MM + LABEL_MM) * MM
    title = TITLE_MM * MM

    room_width = paper[0] - 2 * border
    room_height = paper[1] - 2 * border - 2 * title
    scale = min(room_width / width, room_height / height)
    frame_width, frame_height = width * scale, height * scale
    left = (paper[0] - frame_width) / 2
    top = (paper[1] - frame_height) / 2

    return paper, (left, top, frame_width, frame_height)


def find_lines(img, frame, spacing, angle, contrast):
    """De hulplijnen, van linksboven naar rechtsonder. Elke lijn: dict met "points" (N x 2, pixels op het
    A4), "offset" (afstand van het midden, loodrecht op de lijnen), "start" (waar de lijn het kader
    binnenkomt: ("left", y) of ("bottom", x)), "number" (lijnnummer: 1 is de lijn rechtsonder) en
    "runs" (lijst van (van, tot), puntnummers vanaf 1)."""
    left, top, width, height = frame
    darkness = _darkness(img, width, height, spacing, contrast)
    scale = darkness.shape[1] / width

    direction, normal = _directions(angle)
    center = np.array([left + width / 2, top + height / 2])
    reach = math.hypot(width, height) / 2 + spacing
    along = np.arange(-reach, reach + 1e-6, spacing * POINT_RATIO)

    lines = []

    for offset in np.arange(-reach, reach + 1e-6, spacing):
        points = center + offset * normal + along[:, None] * direction
        inside = ((points[:, 0] >= left) & (points[:, 0] <= left + width)
                  & (points[:, 1] >= top) & (points[:, 1] <= top + height))

        if inside.sum() < 3:
            continue

        points = points[inside]
        xs = np.clip(((points[:, 0] - left) * scale).astype(int), 0, darkness.shape[1] - 1)
        ys = np.clip(((points[:, 1] - top) * scale).astype(int), 0, darkness.shape[0] - 1)

        start = _frame_entry(points[0], direction, frame)
        lines.append({"points": points, "offset": offset, "dark": darkness[ys, xs], "start": start})

    threshold = np.quantile(np.concatenate([line["dark"] for line in lines]), 1 - INK)

    for index, line in enumerate(lines):
        line["runs"] = _runs(line.pop("dark") >= threshold)
        # Nummeren vanaf rechtsonder: de nummers onder het plaatje blijven dan klein (twee cijfers)
        line["number"] = len(lines) - index

    return lines


def _directions(angle):
    """Eenheidsvectoren langs de lijnen (naar rechtsboven) en loodrecht erop (naar de volgende lijn)."""
    radians = math.radians(angle)

    return (np.array([math.cos(radians), math.sin(radians)]),
            np.array([-math.sin(radians), math.cos(radians)]))


def _frame_entry(first_point, direction, frame):
    """Waar de lijn het kader binnenkomt (links of onder), voor het nummer: ("left", y) of ("bottom", x)."""
    left, top, width, height = frame
    bottom = top + height
    # Terug langs de lijn tot de linkerrand en tot de onderrand; de dichtstbijzijnde is de ingang
    to_left = (first_point[0] - left) / direction[0]
    to_bottom = (first_point[1] - bottom) / direction[1]

    if to_left <= to_bottom:
        return "left", first_point[1] - to_left * direction[1]

    return "bottom", first_point[0] - to_bottom * direction[0]


def _runs(ink):
    """Opeenvolgende inkt-punten als (van, tot), puntnummers vanaf 1."""
    runs = []
    index = 0

    while index < len(ink):
        if not ink[index]:
            index += 1
            continue

        end = index

        while end + 1 < len(ink) and ink[end + 1]:
            end += 1

        if end - index + 1 >= MIN_RUN:
            runs.append((index + 1, end + 1))

        index = end + 1

    return runs


def _darkness(img, width, height, spacing, contrast):
    """Hoe donker de foto is, op een klein plaatje (4 pixels per lijnafstand), 0 = wit en 1 = zwart.

    contrast (0 tot 1) mengt de gewone donkerte met lokaal contrast: hoe veel donkerder of lichter een
    plekje is dan zijn omgeving, gedeeld door hoeveel het daar sowieso varieert. Hoe hoger, hoe kleiner
    die omgeving en hoe zwaarder het telt.
    """
    per_pixel = spacing / 4
    size = (max(8, round(width / per_pixel)), max(8, round(height / per_pixel)))
    gray = ImageOps.autocontrast(img.convert("L").resize(size, Image.LANCZOS), cutoff=1)
    darkness = ndimage.gaussian_filter(1 - np.asarray(gray, dtype=np.float32) / 255, 1.3)

    if contrast > 0:
        surroundings = max(size) / (12 + 18 * contrast)
        mean = ndimage.gaussian_filter(darkness, surroundings)
        spread = np.sqrt(ndimage.gaussian_filter((darkness - mean) ** 2, surroundings)) + 0.05
        local = np.clip(0.5 + 0.25 * (darkness - mean) / spread, 0, 1)
        darkness = (1 - contrast) * darkness + contrast * local

    return darkness


# ---------------------------------------------------------------------------
# Tekenen
# ---------------------------------------------------------------------------

_stamp_cache = {}


def _stamp(kind, size_px, extra=0.0):
    """Een stempel (alfamasker) voor een puntje of streepje, voor elke positie tussen twee pixels.

    kind "dot": rondje met straal size_px. kind "tick": streepje van lengte size_px, met extra =
    (dikte, richting dwars op de lijnen). Geeft (halve breedte in hele pixels, {(fx, fy): masker}).
    """
    key = (kind, round(size_px, 3), repr(extra))

    if key in _stamp_cache:
        return _stamp_cache[key]

    half = int(math.ceil(size_px)) + 2
    box = 2 * half + 1
    big = box * STAMP_DETAIL
    masks = {}

    for fx in range(SUBPIXEL):
        for fy in range(SUBPIXEL):
            mask = Image.new("L", (big, big), 0)
            draw = ImageDraw.Draw(mask)
            cx = (half + 0.5 + fx / SUBPIXEL) * STAMP_DETAIL
            cy = (half + 0.5 + fy / SUBPIXEL) * STAMP_DETAIL

            if kind == "dot":
                r = size_px * STAMP_DETAIL
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
            else:
                thickness, across = extra
                along = np.array([-across[1], across[0]])
                a = np.array(across) * size_px / 2 * STAMP_DETAIL
                b = along * thickness / 2 * STAMP_DETAIL
                corners = [(cx + sa * a[0] + sb * b[0], cy + sa * a[1] + sb * b[1])
                           for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                draw.polygon(corners, fill=255)

            masks[(fx, fy)] = mask.resize((box, box), Image.BOX)

    _stamp_cache[key] = (half, masks)

    return _stamp_cache[key]


def _put(image, stamp, gray, x, y):
    """Zet een stempel met middelpunt (x, y) (in pixels, met decimalen) op het plaatje."""
    half, masks = stamp
    ix, fx = _split(x)
    iy, fy = _split(y)

    image.paste(gray, (ix - half, iy - half), masks[(fx, fy)])


def _split(position):
    """Pixelpositie (midden van pixel i is i + 0,5) als heel pixel plus stapje tussen twee pixels in."""
    whole = math.floor(position - 0.5)
    part = round((position - 0.5 - whole) * SUBPIXEL)

    if part == SUBPIXEL:
        whole, part = whole + 1, 0

    return whole, part


def _guide_layer(size, lines, angle, spacing, scale=1.0, shift=(0.0, 0.0), width_px=1.0, gray=GUIDE_GRAY):
    """De hulplijnen als grijswaarden-plaatje, per pixel uitgerekend: strak en zonder trapjes.

    Voor elk pixel: hoe ver ligt het van de dichtstbijzijnde hulplijn (loodrecht), en ligt het tussen
    het eerste en laatste punt van die lijn? Dat geeft de dekking (0 tot 1), met zachte randjes.
    """
    direction, normal = _directions(angle)
    image = np.full((size[1], size[0]), 255, dtype=np.uint8)

    # Per lijn: afstand tot het midden, en van waar tot waar hij loopt (langs de lijn)
    offsets = np.array([line["offset"] for line in lines]) * scale
    first = np.array([line["points"][0] for line in lines]) * scale + shift
    last = np.array([line["points"][-1] for line in lines]) * scale + shift
    origin = first[0] - offsets[0] * normal     # een punt op de "middellijn"
    t_first = (first - origin) @ direction
    t_last = (last - origin) @ direction
    step = spacing * scale

    xs = np.arange(size[0], dtype=np.float32) + 0.5

    for y0 in range(0, size[1], 256):
        ys = np.arange(y0, min(size[1], y0 + 256), dtype=np.float32)[:, None] + 0.5
        across = (xs[None, :] - origin[0]) * normal[0] + (ys - origin[1]) * normal[1]
        along = (xs[None, :] - origin[0]) * direction[0] + (ys - origin[1]) * direction[1]
        index = np.rint((across - offsets[0]) / step).astype(np.int64)
        valid = (index >= 0) & (index < len(lines))
        index = np.clip(index, 0, len(lines) - 1)
        distance = np.abs(across - offsets[index])
        coverage = np.clip(width_px / 2 + 0.5 - distance, 0, 1)
        inside = valid & (along >= t_first[index]) & (along <= t_last[index])
        coverage = np.where(inside, coverage, 0)
        image[y0:y0 + len(ys)] = np.rint(255 - (255 - gray) * coverage).astype(np.uint8)

    return Image.fromarray(image, "L")


def _draw_marks(image, lines, angle, scale=1.0, shift=(0.0, 0.0), light=False):
    """De puntjes: elk 10e punt groter, elk 5e met een dwars streepje, de rest een klein puntje."""
    _, normal = _directions(angle)
    lift = (lambda gray: 255 - (255 - gray) * 0.45) if light else (lambda gray: gray)
    dot = _stamp("dot", DOT_RADIUS_MM * MM * scale)
    tenth = _stamp("dot", TENTH_RADIUS_MM * MM * scale)
    fifth = _stamp("tick", FIFTH_LENGTH_MM * MM * scale,
                   (FIFTH_WIDTH_MM * MM * scale, (round(normal[0], 4), round(normal[1], 4))))

    for line in lines:
        points = line["points"] * scale + shift

        for number, (x, y) in enumerate(points, 1):
            if number % 10 == 0:
                _put(image, tenth, round(lift(TENTH_GRAY)), x, y)
            elif number % 5 == 0:
                _put(image, fifth, round(lift(FIFTH_GRAY)), x, y)
            else:
                _put(image, dot, round(lift(DOT_GRAY)), x, y)


def _draw_preview(lines, frame, angle, output_size):
    """Zo ziet het eruit als alle stukjes getekend zijn."""
    left, top, width, height = frame
    margin = output_size * 0.03
    scale = (output_size - 2 * margin) / width
    shift = np.array([margin - left * scale, margin - top * scale])
    size = (output_size, round(height * scale + 2 * margin))
    spacing = abs(lines[1]["offset"] - lines[0]["offset"]) if len(lines) > 1 else 10

    image = _guide_layer(size, lines, angle, spacing, scale, shift, max(0.6, GUIDE_WIDTH_MM * MM * scale),
                         gray=235)
    _draw_marks(image, lines, angle, scale, shift, light=True)

    # De getekende stukjes: een fineliner van 0,4 mm, 3x zo groot getekend en verkleind (gladde lijnen)
    detail = 3
    ink = Image.new("L", (size[0] * detail, size[1] * detail), 0)
    draw = ImageDraw.Draw(ink)
    line_width = max(1, round(0.4 * MM * scale * detail))

    for line in lines:
        points = (line["points"] * scale + shift) * detail

        for first, last in line["runs"]:
            draw.line((tuple(points[first - 1]), tuple(points[last - 1])), fill=255, width=line_width)

    ink = ink.resize(size, Image.LANCZOS)
    image.paste(INK_COLOR[0], (0, 0), ink)

    return image.convert("RGB")


def _draw_grid_page(lines, frame, paper, spacing, angle):
    """Blad 1: de hulplijnen, de puntjes en de lijnnummers, netjes op een rij naast en onder het kader."""
    width, height = paper
    left, top, frame_width, frame_height = frame

    image = _guide_layer(paper, lines, angle, spacing, width_px=GUIDE_WIDTH_MM * MM)
    _draw_marks(image, lines, angle)
    image = image.convert("RGB")

    _draw_labels(image, lines, frame, angle)
    draw = ImageDraw.Draw(image)

    small = get_font(round(2.6 * MM))
    margin = PAGE_MARGIN_MM * MM
    draw.text((margin, margin), f"{TOOL_NAME} · blad 1: hierop teken je", fill=NUMBER_COLOR, font=small,
              anchor="lt")
    draw.text((width - margin, height - margin),
              "Wat je tekent staat op blad 2. Volg het dunne lijntje van het nummer naar punt 1.",
              fill=NUMBER_COLOR, font=small, anchor="rb")

    return image


def _draw_labels(image, lines, frame, angle):
    """De lijnnummers: onder het kader op één rij, links in één kolom (rechts uitgelijnd).

    Elke lijn loopt met een dun lijntje schuin door tot net bij zijn eigen nummer. Zo is meteen duidelijk
    welk nummer bij welke lijn hoort. Liggen de nummers onder het kader toch te dicht op elkaar, dan om
    en om op twee rijen (met langere lijntjes naar de onderste rij).
    """
    left, top, frame_width, frame_height = frame
    draw = ImageDraw.Draw(image)
    font = get_font(round(LABEL_FONT_MM * MM))
    direction, _ = _directions(angle)
    back = -direction                           # van punt 1 terug, naar linksonder
    drop = LABEL_DROP_MM * MM
    pad = LABEL_PAD_MM * MM

    bottom = sorted((line["start"][1], line) for line in lines if line["start"][0] == "bottom")
    widest = max((font.getlength(str(line["number"])) for _, line in bottom), default=0)
    distance = min((b[0] - a[0] for a, b in zip(bottom, bottom[1:])), default=widest * 2)
    two_rows = distance < widest + 0.6 * MM
    row_height = (LABEL_FONT_MM + 0.6) * MM
    leaders = []

    for index, (_, line) in enumerate(bottom):
        first = line["points"][0]
        down = top + frame_height + drop + (row_height if two_rows and index % 2 else 0) - first[1]
        end = first + back * (down / back[1])
        leaders.append((first, end))
        draw.text((end[0], end[1] + pad), str(line["number"]), fill=LINE_COLOR, font=font, anchor="mt")

    for line in lines:
        if line["start"][0] == "left":
            first = line["points"][0]
            end = first + back * ((first[0] - (left - drop)) / -back[0])
            leaders.append((first, end))
            draw.text((end[0] - pad, end[1]), str(line["number"]), fill=LINE_COLOR, font=font, anchor="rm")

    _draw_leaders(image, leaders, GUIDE_WIDTH_MM * MM)


def _draw_leaders(image, segments, width_px, detail=4):
    """Dunne rechte lijntjes met zachte randjes: getekend op detail x zo groot en verkleind, alleen in het
    stukje van het blad waar ze liggen (zo blijft het licht voor het geheugen)."""
    if not segments:
        return

    corners = np.array([point for segment in segments for point in segment])
    x0, y0 = np.floor(corners.min(axis=0)).astype(int) - 2
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int) + 2
    mask = Image.new("L", ((x1 - x0) * detail, (y1 - y0) * detail), 0)
    draw = ImageDraw.Draw(mask)

    for start, end in segments:
        draw.line(((start[0] - x0) * detail, (start[1] - y0) * detail, (end[0] - x0) * detail,
                   (end[1] - y0) * detail), fill=255, width=max(1, round(width_px * detail)))

    mask = mask.resize((x1 - x0, y1 - y0), Image.BOX)
    image.paste((LEADER_GRAY,) * 3, (int(x0), int(y0)), mask)


def _draw_code_page(lines, photo, frame, angle):
    """Blad 2: per lijn de stukjes om te tekenen, met je foto en het "antwoord" klein onderaan."""
    width, height = A4_SIZE
    margin = round(width * 0.045)
    picture_height = round(width * 0.24)
    bottom_block = round(width * 0.06) + picture_height + round(width * 0.03)
    list_top = margin + round(width * 0.105)
    list_height = height - margin - bottom_block - list_top

    entries = sorted((line["number"], line["runs"]) for line in lines if line["runs"])
    list_columns = 4
    column_gap = round(width * 0.025)
    column_width = (width - 2 * margin - (list_columns - 1) * column_gap) / list_columns

    # Grootste lettertype waarbij de lijst past (een lijn wordt nooit over twee kolommen verdeeld)
    for font_size in range(34, 14, -1):
        line_height = round(font_size * 1.45)
        placed = _place_code(_layout_code(entries, column_width, font_size), list_columns,
                             list_height // line_height if font_size > 15 else 10 ** 6)

        if placed is not None:
            break

    image = Image.new("RGB", (width, height), PAPER_COLOR)
    draw = ImageDraw.Draw(image)

    n_pieces = sum(len(runs) for _, runs in entries)
    draw.text((margin, margin), f"{TOOL_NAME} · {n_pieces} stukjes op {len(entries)} lijnen",
              fill=INK_COLOR, font=get_font(round(width * 0.02)), anchor="lt")
    explanation = [
        "Per lijn: zet je pen op het eerste punt en trek met je liniaal een lijn tot het tweede punt.",
        "Tel steeds vanaf punt 1, waar het lijntje van het nummer begint. Elk 5e punt heeft een streepje, elk 10e is groter.",
    ]

    for row, text in enumerate(explanation):
        draw.text((margin, margin + round(width * 0.04) + row * round(width * 0.022)), text,
                  fill=LINE_COLOR, font=get_font(round(width * 0.0135)), anchor="lt")

    regular = get_font(font_size)
    bold = max(1, round(font_size / 22))
    number_width = regular.getlength("000  ")

    for column, row, number, text in placed:
        x = margin + column * (column_width + column_gap)
        y = list_top + row * line_height + line_height / 2

        if number is not None:
            draw.text((x, y), str(number), fill=INK_COLOR, font=regular, anchor="lm", stroke_width=bold,
                      stroke_fill=INK_COLOR)

        draw.text((x + number_width, y), text, fill=LINE_COLOR, font=regular, anchor="lm")

    _draw_answer(image, lines, photo, frame, angle, margin, picture_height)

    return image


def _place_code(layout, list_columns, rows_per_column):
    """Verdeel de regels over de kolommen zonder een lijn op te knippen: [(kolom, rij, nummer, tekst)].

    None als het niet past. Bij het kleinste lettertype gaat het altijd door (dan maar langer).
    """
    blocks = []

    for number, text in layout:
        if number is not None or not blocks:
            blocks.append([])

        blocks[-1].append((number, text))

    total = sum(len(block) for block in blocks)
    target = max(math.ceil(total / list_columns), max(len(block) for block in blocks))
    placed, column, row = [], 0, 0

    for block in blocks:
        if row + len(block) > target and row > 0:
            column, row = column + 1, 0

        for number, text in block:
            placed.append((column, row, number, text))
            row += 1

    rows_needed = max(entry[1] for entry in placed) + 1

    if column >= list_columns or rows_needed > rows_per_column:
        # Lukt het niet met evenveel regels per kolom, probeer dan de kolommen zo vol mogelijk
        placed, column, row = [], 0, 0

        for block in blocks:
            if row + len(block) > rows_per_column and row > 0:
                column, row = column + 1, 0

            for number, text in block:
                placed.append((column, row, number, text))
                row += 1

        if column >= list_columns:
            return None

    return placed


def _layout_code(entries, column_width, font_size):
    """Elke lijn op eigen regel(s): (lijnnummer of None bij een vervolgregel, tekst)."""
    font = get_font(font_size)
    room = column_width - font.getlength("000  ")
    layout = []

    for number, runs in entries:
        text, first = "", True

        for first_point, last_point in runs:
            piece = f"{first_point}-{last_point}"
            candidate = f"{text}   {piece}" if text else piece

            if text and font.getlength(candidate) > room:
                layout.append((number if first else None, text))
                text, first = piece, False
            else:
                text = candidate

        layout.append((number if first else None, text))

    return layout


def _draw_answer(image, lines, photo, frame, angle, margin, max_height):
    """Onderaan, achter een gestippelde knip- of vouwlijn: je foto en het antwoord, naast elkaar."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    caption_font = get_font(round(width * 0.012))

    gap = round(width * 0.06)
    picture_width, picture_height = fit_picture(photo.size, (width - 2 * margin - gap) / 2, max_height)
    pictures_top = height - margin - round(width * 0.03) - max_height + (max_height - picture_height) // 2
    pictures_left = (width - 2 * picture_width - gap) // 2

    fold_y = height - margin - round(width * 0.03) - max_height - round(width * 0.035)
    dash = round(width * 0.008)

    for x in range(margin, width - margin, 2 * dash):
        draw.line((x, fold_y, min(x + dash, width - margin), fold_y), fill=(190, 190, 190), width=2)

    draw.text((width / 2, fold_y), "  knip of vouw hier als je het antwoord nog niet wilt zien  ",
              fill=NUMBER_COLOR, font=caption_font, anchor="mm", stroke_width=8, stroke_fill=PAPER_COLOR)

    answer = _draw_preview(lines, frame, angle, picture_width * 2)
    answer = answer.resize((picture_width, picture_height), Image.LANCZOS)
    pictures = [(photo.resize((picture_width, picture_height), Image.LANCZOS), "Je foto"),
                (answer, "Zo wordt het")]

    for number, (picture, caption) in enumerate(pictures):
        x = pictures_left + number * (picture_width + gap)
        image.paste(picture, (x, pictures_top))
        draw.text((x + picture_width / 2, pictures_top + picture_height + round(width * 0.012)), caption,
                  fill=NUMBER_COLOR, font=caption_font, anchor="mt")

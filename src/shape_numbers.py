"""Shape division: eigen kleuren, gelijke grootte per vorm en de lege kleurplaat met nummers.

Dit bestand gebruikt de functies uit shape_division.py (zelfde vormen en zelfde kleuren als de
ingekleurde variant) en de nummers, de legenda en de kleurfuncties uit helper_functions (zoals bij
de Kleurplaat). shape_division.py zelf blijft ongewijzigd.

Wat hier staat:
- side_for_equal_area(): zorgt dat elke vorm bij dezelfde instelling even gedetailleerd is
- image_to_palette_shapes(): ingekleurd met een zelfgekozen kleurenlijst
- image_to_numbered_shapes(): leeg, met een nummer in elke vorm en een legenda
"""

import math

import numpy as np
from PIL import Image, ImageDraw

from src.helper_functions.drawing import LINE_COLOR, NUMBER_COLOR, add_legend, get_font
from src.helper_functions.lab_colors import balanced_color_bias, parse_color, rgb_to_lab
from src.shape_division import (
    SHAPES,
    create_polygons,
    get_polygon_average,
    polygon_intersects_image,
    quantize_colors,
)

# Gemiddelde oppervlakte van één vorm, in "zijde in het kwadraat". In shape_division.py betekent
# grid_size bij elke vorm iets anders (de zijde van een driehoek, de zijde van een plus, ...), en
# daardoor is een driehoek bij dezelfde zijde veel kleiner dan een plus. Met deze getallen
# rekenen we om, zodat elke vorm bij dezelfde instelling dezelfde oppervlakte heeft.
AREA_FACTORS = {
    "squares": 1.0,
    "brick": 2.0,
    "triangles": math.sqrt(3) / 4,
    "hexagons": 3 * math.sqrt(3) / 2,
    "rhombi": math.sqrt(3) / 2,
    "cubes": math.sqrt(3) / 2,
    "octagons_squares": (2 * (1 + math.sqrt(2)) + 1) / 2,   # gemiddelde van achthoek en ruitje
    "crosses": 5.0,
}


def side_for_equal_area(shape, square_side):
    """De grid_size voor shape_division.py waarbij één vorm even groot is als een vierkant met zijde square_side.

    Zo geeft dezelfde instelling bij elke vorm ongeveer evenveel vormen, dus evenveel detail.
    """
    return square_side / math.sqrt(AREA_FACTORS.get(shape, 1.0))


# De lijntjes worden eerst op dubbele grootte getekend en dan verkleind: dat geeft gladde lijnen.
SUPERSAMPLE = 2


def image_to_palette_shapes(img, grid_size, shape, colors):
    """Ingekleurde vormen met een zelfgekozen kleurenlijst.

    Elke vorm krijgt van jouw kleuren de kleur die het dichtst bij de gemiddelde kleur van
    dat stuk van de foto ligt.

    Args:
        img: PIL Image.
        grid_size: ongeveer de grootte van een vorm (zie side_for_equal_area).
        shape: naam van de vorm (alles uit SHAPES behalve "truchet").
        colors: lijst kleuren, bijv. ["#ff0000", (0, 128, 255)].

    Returns:
        PIL Image (RGB).
    """
    img, polygons, shape_colors = _polygons_and_colors(img, grid_size, 256, shape, colors)
    width, height = img.size

    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)

    for polygon, color in zip(polygons, shape_colors):
        draw.polygon(polygon, fill=color)

    return output


def image_to_numbered_shapes(
        img,
        grid_size=20,
        max_colors=12,
        shape="hexagons",
        legend=True,
        colors=None,
):
    """Verdeel een afbeelding in vormen en geef de lege versie: lijntjes, een nummer per vorm en een legenda.

    De kleuren zijn dezelfde als bij de ingekleurde variant, dus de twee horen bij elkaar.
    Nummer 1 is de donkerste kleur.

    Args:
        img: PIL Image.
        grid_size: ongeveer de grootte van een vorm, in pixels.
        max_colors: maximaal aantal kleuren (alleen als colors niet is opgegeven).
        shape: naam van de vorm (alles uit SHAPES behalve "truchet").
        legend: onder de afbeelding een legenda (nummer -> kleur) zetten.
        colors: eigen kleuren als lijst; anders worden ze uit de foto gehaald.

    Returns:
        PIL Image (RGB).
    """
    img, polygons, shape_colors = _polygons_and_colors(img, grid_size, max_colors, shape, colors)
    width, height = img.size
    longest = max(width, height)

    # Kleurnummers: donkerste eerst. Alleen kleuren die echt voorkomen komen in de legenda.
    unique = sorted(set(shape_colors), key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    number_of = {color: index + 1 for index, color in enumerate(unique)}
    palette = np.array(unique, dtype=np.float32)

    image = _draw_outlines(polygons, width, height)
    draw = ImageDraw.Draw(image)

    base_font = max(10, round(longest * 0.011))

    for polygon, color in zip(polygons, shape_colors):
        # Alleen het stuk van de vorm dat in beeld is: daar moet het nummer in
        visible = _clip_to_image(polygon, width, height)

        if len(visible) < 3:
            continue

        x, y = _centroid(visible)
        number = str(number_of[color])
        font_size = _fit_font_size(number, _inradius(visible, x, y), base_font)

        if font_size is None:
            continue    # een heel klein randstukje waar geen nummer in past

        draw.text((x, y), number, fill=NUMBER_COLOR, font=get_font(font_size), anchor="mm")

    if legend:
        image = add_legend(image, palette)

    return image


def suggest_shape_palette(img, grid_size, shape, n_colors):
    """De kleuren die de automatische variant zou kiezen, donker naar licht, als HEX-lijst.

    Dient als beginpunt voor "Kleuren uit foto": dezelfde vormen en dezelfde kleurkeuze als de
    automatische modus, zodat je ze daarna zelf kunt aanpassen.
    """
    _, _, shape_colors = _polygons_and_colors(img, grid_size, n_colors, shape, None)
    unique = sorted(set(shape_colors), key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])

    return ["#%02x%02x%02x" % tuple(int(v) for v in c) for c in unique]


def _polygons_and_colors(img, grid_size, max_colors, shape, colors):
    """De vormen en de kleur van elke vorm. Voor alle varianten hetzelfde, zodat ze bij elkaar passen."""
    if grid_size <= 0:
        raise ValueError("grid_size must be greater than 0")

    if not 1 <= max_colors <= 256:
        raise ValueError("max_colors must be between 1 and 256")

    if shape not in SHAPES or shape == "truchet":
        raise ValueError("shape must be one of: " + ", ".join(sorted(SHAPES - {"truchet"})))

    img = img.convert("RGB")
    img_array = np.array(img)
    width, height = img.size

    polygons = create_polygons(width=width, height=height, grid_size=grid_size, shape=shape)
    polygons = [p for p in polygons if polygon_intersects_image(p, width, height)]

    average_colors = [get_polygon_average(img_array, p) for p in polygons]

    if colors:
        shape_colors = _nearest_palette_colors(average_colors, colors)
    else:
        shape_colors = quantize_colors(average_colors, max_colors)

    return img, polygons, shape_colors


def _nearest_palette_colors(average_colors, colors):
    """Geef elke vorm een kleur uit het gekozen palet: de dichtstbijzijnde (in Lab), maar zo dat elke kleur voldoende voorkomt."""
    if len(average_colors) == 0:
        return []

    palette = np.array([parse_color(c) for c in colors], dtype=np.float32)
    averages = np.array(average_colors, dtype=np.float32)

    palette_lab = rgb_to_lab(palette[None, :, :])[0]
    averages_lab = rgb_to_lab(averages[None, :, :])[0]

    distances = ((averages_lab[:, None, :] - palette_lab[None, :, :]) ** 2).sum(axis=2)

    # Elke gekozen kleur moet echt voorkomen, ook als hij niet in de foto zit (zie helper_functions/lab_colors.py)
    distances = distances + balanced_color_bias(averages_lab, palette_lab)
    nearest = distances.argmin(axis=1)

    return [tuple(int(v) for v in palette[index]) for index in nearest]


def _draw_outlines(polygons, width, height):
    scale = SUPERSAMPLE
    line = max(2, round(max(width, height) * 0.0012 * scale))

    big = Image.new("RGB", (width * scale, height * scale), "white")
    draw = ImageDraw.Draw(big)

    for polygon in polygons:
        points = [(x * scale, y * scale) for x, y in polygon]

        # Als lijnstuk tekenen, niet met draw.polygon(width=...): dat maakt per vorm een compleet
        # nieuw beeld aan en is daardoor bij duizenden vormen veel te traag.
        draw.line(points + [points[0]], fill=LINE_COLOR, width=line, joint="curve")

    # Een lijst om de hele afbeelding, zoals bij de Kleurplaat
    draw.rectangle((0, 0, width * scale - 1, height * scale - 1), outline=LINE_COLOR, width=line)

    return big.resize((width, height), Image.Resampling.LANCZOS)


def _fit_font_size(number, radius, base_font):
    """Grootste letterhoogte waarbij het nummer binnen de vorm past, of None als het niet past."""
    half_diagonal = 0.5 * math.hypot(0.65 * len(number), 0.8)   # per punt letterhoogte
    size = int(min(base_font, radius * 0.8 / half_diagonal))     # 0,8: een beetje ruimte tot de lijntjes

    return size if size >= 7 else None


def _clip_to_image(polygon, width, height):
    """Knip een vorm bij tot het stuk dat binnen de afbeelding valt (Sutherland-Hodgman)."""
    points = list(polygon)

    for axis, limit, keep_greater in ((0, 0, True), (0, width, False), (1, 0, True), (1, height, False)):
        if not points:
            break

        clipped = []
        previous = points[-1]

        for current in points:
            current_inside = current[axis] >= limit if keep_greater else current[axis] <= limit
            previous_inside = previous[axis] >= limit if keep_greater else previous[axis] <= limit

            if current_inside != previous_inside:
                t = (limit - previous[axis]) / (current[axis] - previous[axis])
                clipped.append((
                    previous[0] + t * (current[0] - previous[0]),
                    previous[1] + t * (current[1] - previous[1]),
                ))

            if current_inside:
                clipped.append(current)

            previous = current

        points = clipped

    return points


def _centroid(points):
    """Zwaartepunt van een vlak."""
    area2 = 0.0
    cx = 0.0
    cy = 0.0

    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    if abs(area2) < 1e-9:
        return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))

    return cx / (3 * area2), cy / (3 * area2)


def _inradius(points, x, y):
    """Afstand van een punt tot de dichtstbijzijnde rand van het vlak."""
    smallest = float("inf")

    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        dx, dy = x1 - x0, y1 - y0
        length_squared = dx * dx + dy * dy

        if length_squared == 0:
            distance = math.hypot(x - x0, y - y0)
        else:
            t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length_squared))
            distance = math.hypot(x - (x0 + t * dx), y - (y0 + t * dy))

        smallest = min(smallest, distance)

    return smallest

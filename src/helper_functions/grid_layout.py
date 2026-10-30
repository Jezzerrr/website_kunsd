"""Het raster van een tekenpuzzel (Penpath, Hatchwork) zo groot mogelijk op A4, strak om het plaatje.

Een liggend plaatje krijgt een liggend A4, een staand plaatje een staand A4. De afstand tussen de
rasterpunten ligt vast (zo fijn als short_points punten op de korte kant van A4); het aantal kolommen
en rijen volgt uit hoe groot het plaatje op het papier past. Zo blijft er geen leeg raster over.
"""

# A4 bij 300 dpi, staand
A4_SIZE = (2480, 3508)


def fit_grid(image_size, short_points, border, title_space):
    """Kies papier en raster voor een plaatje.

    Args:
        image_size: (breedte, hoogte) van het plaatje (de verhouding telt).
        short_points: zoveel punten zouden er op de korte kant van A4 passen: dat bepaalt de afstand.
        border: ruimte aan elke kant van het raster (witte rand plus de coördinaten), in pixels.
        title_space: extra ruimte boven het raster (titel) en eronder (verwijzing naar blad 2), in pixels.

    Returns:
        (papier, kolommen, rijen, afstand): papier als (breedte, hoogte) in pixels, afstand in pixels.
    """
    width, height = image_size
    is_landscape = width > height
    paper = (A4_SIZE[1], A4_SIZE[0]) if is_landscape else A4_SIZE

    # Boven en onder het raster staat tekst: liggend gaat die ruimte van de korte kant af
    step = (min(paper) - 2 * border - (2 * title_space if is_landscape else 0)) / (short_points - 1)
    room_width = paper[0] - 2 * border
    room_height = paper[1] - 2 * border - 2 * title_space

    # Het plaatje zo groot als past, en dan zoveel hokjes als erin passen
    scale = min(room_width / width, room_height / height)
    columns = max(2, int(width * scale / step + 1e-6) + 1)
    rows = max(2, int(height * scale / step + 1e-6) + 1)

    return paper, columns, rows, step


def fit_picture(picture_size, max_width, max_height):
    """De grootste (breedte, hoogte) met de verhouding van picture_size binnen max_width bij max_height."""
    width, height = picture_size
    scale = min(max_width / width, max_height / height)

    return max(1, round(width * scale)), max(1, round(height * scale))

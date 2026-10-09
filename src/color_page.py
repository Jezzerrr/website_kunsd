"""Kleurplaat: verandert een foto in vlakken van dezelfde kleur.

Twee varianten:
- fill=True : de ingekleurde kleurplaat (egale vlakken)
- fill=False: de lege kleurplaat, met lijntjes, een klein grijs nummer in elk
              vlak en een legenda onderaan (nummer -> kleur)

Hoe het werkt:
1. De foto wordt verkleind (max_size) zodat het snel blijft.
2. Kleuren kiezen: zelf opgegeven, of automatisch via k-means op de foto.
3. Elke pixel krijgt de dichtstbijzijnde kleur (in Lab, dichter bij hoe ogen kleur zien).
4. Gladstrijken: elke kleur wordt vervaagd en per plek wint de sterkste kleur.
   Dat maakt randen vloeiend en laat dunne streepjes en kleine vlekjes verdwijnen.
5. Details terughalen: kleine vormen die duidelijk afsteken (ogen, mond, lichtpuntjes)
   worden niet weggepoetst, ook al zijn ze klein. Ruis en dunne randjes wel.
6. Te kleine, onbelangrijke vlakjes worden samengevoegd met hun buurman.
7. Tekenen: egale vlakken, of lijntjes + nummers + legenda.

Nodig: numpy, scipy en Pillow (scipy zit ook in scikit-image).
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

LINE_COLOR = (70, 70, 70)
NUMBER_COLOR = (140, 140, 140)
LEGEND_TEXT_COLOR = (90, 90, 90)


def image_to_color_page(
        img,
        n_colors=6,
        colors=None,
        smoothness=1.0,
        min_region_size=0.1,
        detail=0.6,
        fill=True,
        legend=True,
        max_size=1200,
        line_width=None,
        seed=0,
):
    """Verander een afbeelding in een kleurplaat.

    Args:
        img: PIL Image.
        n_colors: aantal kleuren (alleen als colors niet is opgegeven).
        colors: eigen kleuren als lijst, bijv. [(255, 0, 0), "#00aa55"].
            Standaard (None) worden de kleuren bepaald uit de foto zelf.
        smoothness: hoe glad de randen zijn. 0 = geen gladstrijken, hoger = vloeiender
            en minder dunne streepjes. Handig bereik: 0 t/m 5.
        min_region_size: kleinste toegestane vlak, in procent van de hele afbeelding.
            Kleinere vlakjes worden samengevoegd met een buurvlak (tenzij ze door
            "detail" worden beschermd). Handig bereik: 0.05 t/m 1.
        detail: 0 t/m 1. Hoeveel kleine, duidelijk afstekende vormen (ogen, mond,
            lichtpuntjes) behouden blijven, ook als ze kleiner zijn dan min_region_size
            of dunner dan smoothness toelaat. 0 = niets beschermen, 1 = zoveel mogelijk.
        fill: True = ingekleurd, False = leeg met nummers.
        legend: bij de lege variant een legenda (nummer -> kleur) onder de afbeelding zetten.
        max_size: de langste zijde wordt hoogstens zoveel pixels (houdt het snel).
        line_width: dikte van de lijntjes in de lege variant, in pixels. None = automatisch.
        seed: zorgt dat dezelfde foto steeds dezelfde kleuren krijgt.

    Returns:
        PIL Image (RGB).
    """
    img, rgb, lab = _prepare(img, max_size)
    width, height = img.size
    longest = max(width, height)

    # 1. Kleuren kiezen
    if colors:
        palette = np.array([_parse_color(c) for c in colors], dtype=np.float32)
        palette_lab = _rgb_to_lab(palette[None, :, :])[0]
    else:
        palette, palette_lab = _palette_from_image(rgb, lab, n_colors, seed)

    # 2. Elke pixel krijgt de dichtstbijzijnde kleur. Bij eigen kleuren zorgen we er ook voor
    #    dat elke gekozen kleur voldoende voorkomt (ook als hij niet in de foto zit).
    bias = None

    if colors:
        flat_lab = lab.reshape(-1, 3)
        rng = np.random.default_rng(seed)
        sample = rng.choice(len(flat_lab), size=min(len(flat_lab), 40000), replace=False)
        bias = balanced_color_bias(flat_lab[sample], palette_lab)

    raw = _nearest_color(lab, palette_lab, bias)

    # 3. Gladstrijken en opruimen. Zie de uitleg bovenaan dit bestand.
    sigma = smoothness * 0.005 * longest
    min_area = max(1, int(width * height * min_region_size / 100))

    detail = float(np.clip(detail, 0, 1))
    protect = None

    if detail > 0:
        protect = {
            "palette_lab": palette_lab,
            # Hoe sterk een vorm moet afsteken (verschil in Lab-kleur) om beschermd te worden
            "threshold": 10 + 70 * (1 - detail),
            # Hoe klein een beschermde vorm minstens moet zijn (in pixels)
            "floor_area": max(12, int(min_area * (0.35 - 0.3 * detail))),
            # Hoe dik hij minstens moet zijn (straal in pixels): dunne randjes vallen af
            "min_thickness": longest * (0.006 - 0.004 * detail),
        }

    # Ruis (losse pixels) meteen weghalen, anders blijft er veel te veel rommel over
    noise_area = max(4, int(width * height * 0.00005))
    raw = _remove_small_regions(raw, noise_area)

    labels = _smooth_labels(raw, sigma)
    labels = _remove_small_regions(labels, min_area, protect)

    if sigma > 0:
        if protect:
            # Haal duidelijke details terug die het gladstrijken wegpoetste
            labels = _restore_details(raw, labels, **protect)

        # Lichte ronde: maakt de randen van teruggehaalde vormen weer mooi rond
        labels = _smooth_labels(labels, max(1.0, sigma / 3))
        labels = _remove_small_regions(labels, min_area, protect)

    # Te smalle stukken weghalen: anders lopen de lijntjes aan weerszijden van een smal vlak
    # in elkaar over en lijkt een vlak in tweeën gesplitst. Geldt voor beide varianten,
    # zodat de ingekleurde en de lege versie bij elkaar passen.
    outline = line_width if line_width is not None else max(2.0, longest * 0.002)
    labels = _remove_thin_parts(labels, radius=max(2.0, outline * 1.25))
    labels = _remove_small_regions(labels, min_area, protect)

    # 4. Alleen gebruikte kleuren houden, donkerste eerst (nummer 1 = donkerste)
    labels, palette = _renumber_by_darkness(labels, palette)

    if fill:
        return Image.fromarray(palette[labels].astype(np.uint8))

    return _draw_empty_page(labels, palette, legend, line_width)


def suggest_palette(img, n_colors=6, max_size=600, seed=0):
    """Geef de automatisch gekozen kleuren als lijst hex-codes, donker naar licht.

    Handig als beginpunt: laat de gebruiker de kleuren daarna zelf aanpassen.
    """
    _, rgb, lab = _prepare(img, max_size)
    palette, _ = _palette_from_image(rgb, lab, n_colors, seed)

    brightness = 0.299 * palette[:, 0] + 0.587 * palette[:, 1] + 0.114 * palette[:, 2]
    order = np.argsort(brightness)

    return ["#{:02x}{:02x}{:02x}".format(*(int(round(v)) for v in palette[i])) for i in order]


def _prepare(img, max_size):
    """Verkleinen, een heel klein beetje ruis weghalen en naar Lab omrekenen."""
    img = _limit_size(img.convert("RGB"), max_size)

    rgb = np.asarray(img, dtype=np.float32)
    rgb = ndimage.gaussian_filter(rgb, sigma=(1, 1, 0), mode="nearest")

    return img, rgb, _rgb_to_lab(rgb)


# ---------------------------------------------------------------------------
# Kleuren
# ---------------------------------------------------------------------------

def _palette_from_image(rgb, lab, n_colors, seed):
    """Bepaal de kleuren automatisch met k-means (in Lab) op een steekproef van de foto."""
    n_colors = max(1, int(n_colors))

    rng = np.random.default_rng(seed)
    flat_lab = lab.reshape(-1, 3)
    flat_rgb = rgb.reshape(-1, 3)

    sample_size = min(len(flat_lab), 20000)
    sample = rng.choice(len(flat_lab), size=sample_size, replace=False)
    points = flat_lab[sample]
    points_rgb = flat_rgb[sample]

    centers = _kmeans(points, n_colors, rng)

    # De kleur van elk groepje is het gemiddelde van de echte (RGB) pixels erin
    assignments = _nearest_color_flat(points, centers)
    palette = np.zeros((len(centers), 3), dtype=np.float32)
    palette_lab = centers.copy()

    for index in range(len(centers)):
        members = points_rgb[assignments == index]

        if len(members) > 0:
            palette[index] = members.mean(axis=0)
            palette_lab[index] = points[assignments == index].mean(axis=0)
        else:
            palette[index] = _lab_center_to_rgb_fallback(centers[index])

    return palette, palette_lab


def _kmeans(points, k, rng, iterations=15):
    """Eenvoudige k-means met slimme startpunten (k-means++)."""
    k = min(k, len(points))

    centers = [points[rng.integers(len(points))]]
    distances = ((points - centers[0]) ** 2).sum(axis=1)

    for _ in range(1, k):
        total = distances.sum()

        if total <= 0:
            index = rng.integers(len(points))
        else:
            index = rng.choice(len(points), p=distances / total)

        centers.append(points[index])
        distances = np.minimum(distances, ((points - points[index]) ** 2).sum(axis=1))

    centers = np.array(centers, dtype=np.float32)

    for _ in range(iterations):
        assignments = _nearest_color_flat(points, centers)

        for index in range(len(centers)):
            members = points[assignments == index]

            if len(members) > 0:
                centers[index] = members.mean(axis=0)

    return centers


def _nearest_color_flat(points, centers):
    distances = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return distances.argmin(axis=1)


def _nearest_color(lab, palette_lab, bias=None):
    """Geef elke pixel het nummer van de dichtstbijzijnde kleur (zonder een groot 3D-blok in het geheugen).

    Met bias (een getal per kleur) wordt de afstand tot die kleur kleiner of groter gemaakt,
    zodat een kleur vaker of minder vaak gekozen wordt. Zie balanced_color_bias().
    """
    best_distance = np.full(lab.shape[:2], np.inf, dtype=np.float32)
    labels = np.zeros(lab.shape[:2], dtype=np.int32)

    for index, color in enumerate(palette_lab):
        distance = ((lab - color) ** 2).sum(axis=2)

        if bias is not None:
            distance = distance + bias[index]

        closer = distance < best_distance
        best_distance[closer] = distance[closer]
        labels[closer] = index

    return labels


# Elke eigen gekozen kleur komt minstens voor in dit deel van "een eerlijk aandeel"
# (1 / aantal kleuren). 0,7 betekent: bij 5 kleuren heeft elke kleur minstens 14% van de plaat.
MIN_COLOR_SHARE = 0.7


def balanced_color_bias(points_lab, palette_lab, min_share=MIN_COLOR_SHARE):
    """Zorgt dat bij eigen kleuren elke kleur echt gebruikt wordt.

    Met alleen "de dichtstbijzijnde kleur" blijven kleuren die niet in de foto zitten (een felgroen
    in een foto zonder groen) ongebruikt. Hier krijgt elke kleur een kleine bonus, precies groot
    genoeg dat hij op minstens min_share / aantal_kleuren van de punten wint. De punten waar
    dat het meest op lijkt (het dichtst bij die kleur) krijgen hem. Het resultaat volgt dus nog
    steeds de contouren van de foto, maar wijkt bewust af van de originele kleuren.

    Args:
        points_lab: (N, 3) Lab-kleuren van pixels of vormen (een steekproef is genoeg).
        palette_lab: (K, 3) Lab-kleuren van het palet.

    Returns:
        (K,) getallen om op de kwadratische afstand op te tellen (zie _nearest_color).
    """
    points = np.asarray(points_lab, dtype=np.float32)
    count = len(palette_lab)
    bias = np.zeros(count, dtype=np.float32)

    if count < 2 or len(points) == 0:
        return bias

    floor = min_share / count
    needed = max(1, int(math.ceil(floor * len(points))))
    needed = min(needed, len(points))

    distance = np.stack([((points - color) ** 2).sum(axis=1) for color in palette_lab], axis=1)

    for _ in range(80):
        cost = distance + bias
        shares = np.bincount(cost.argmin(axis=1), minlength=count) / len(points)
        under = np.nonzero(shares < floor - 1e-9)[0]

        if len(under) == 0:
            break

        for index in under:
            others = np.delete(cost, index, axis=1).min(axis=1)
            margin = cost[:, index] - others

            # Het "needed"-na dichtstbijzijnde punt bepaalt hoeveel bonus nodig is
            threshold = np.partition(margin, needed - 1)[needed - 1]
            bias[index] -= threshold + 1e-3
            cost[:, index] = distance[:, index] + bias[index]

    return bias


def _parse_color(color):
    if isinstance(color, str):
        text = color.strip().lstrip("#")

        if len(text) == 3:
            text = "".join(letter * 2 for letter in text)

        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))

    return tuple(int(value) for value in color[:3])


def _lab_center_to_rgb_fallback(center):
    # Alleen voor een leeg k-means-groepje: grijs met de juiste helderheid
    gray = int(np.clip(center[0] * 2.55, 0, 255))
    return np.array([gray, gray, gray], dtype=np.float32)


def _rgb_to_lab(rgb):
    """RGB (0-255) naar Lab. Werkt op elke vorm zolang de laatste as 3 is."""
    srgb = np.asarray(rgb, dtype=np.float32) / 255.0
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)

    matrix = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ], dtype=np.float32)

    xyz = linear @ matrix.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883], dtype=np.float32)

    delta = 6 / 29
    f = np.where(xyz > delta ** 3, np.cbrt(xyz), xyz / (3 * delta ** 2) + 4 / 29)

    lightness = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])

    return np.stack([lightness, a, b], axis=-1).astype(np.float32)


# ---------------------------------------------------------------------------
# Vlakken gladstrijken en opruimen
# ---------------------------------------------------------------------------

def _smooth_labels(labels, sigma):
    """Maak randen vloeiend: vervaag elke kleur, en per plek wint de sterkste kleur.

    Smalle streepjes en kleine vlekjes verliezen daardoor van hun omgeving en verdwijnen.
    """
    if sigma <= 0:
        return labels

    best_weight = np.full(labels.shape, -1.0, dtype=np.float32)
    smoothed = labels.copy()

    for index in np.unique(labels):
        mask = (labels == index).astype(np.float32)
        weight = _blur(mask, sigma)

        stronger = weight > best_weight
        best_weight[stronger] = weight[stronger]
        smoothed[stronger] = index

    return smoothed


def _blur(mask, sigma):
    """Gaussisch vervagen. Bij een grote sigma doen we het op een verkleinde versie (veel sneller)."""
    factor = int(min(4, max(1, sigma // 3)))

    if factor == 1:
        return ndimage.gaussian_filter(mask, sigma=sigma, mode="nearest", truncate=3.0)

    height, width = mask.shape
    pad_y = (-height) % factor
    pad_x = (-width) % factor
    padded = np.pad(mask, ((0, pad_y), (0, pad_x)), mode="edge")

    small = padded.reshape(padded.shape[0] // factor, factor,
                           padded.shape[1] // factor, factor).mean(axis=(1, 3))
    small = ndimage.gaussian_filter(small, sigma=sigma / factor, mode="nearest", truncate=3.0)

    large = ndimage.zoom(small, factor, order=1, mode="nearest", grid_mode=True)

    return large[:height, :width]


def _label_regions(labels):
    """Geef elk aaneengesloten vlak een eigen nummer (twee vlakken van dezelfde kleur zijn twee vlakken)."""
    region_ids = np.zeros(labels.shape, dtype=np.int32)
    offset = 0

    for index in np.unique(labels):
        components, count = ndimage.label(labels == index)
        mask = components > 0
        region_ids[mask] = components[mask] + offset
        offset += count

    return region_ids, offset


def _region_thickness(labels, region_ids, ids):
    """De 'dikte' van elk vlak: hoe ver je er minimaal vanaf de rand kunt staan (straal van de grootste cirkel)."""
    boundary = np.zeros(labels.shape, dtype=bool)
    boundary[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    boundary[:-1, :] |= labels[:-1, :] != labels[1:, :]

    distance = ndimage.distance_transform_edt(~boundary)

    return ndimage.maximum(distance, labels=region_ids, index=ids)


def _color_difference(palette_lab, labels_a, labels_b):
    """Verschil in kleur (Lab) tussen twee kaarten met kleurnummers, per pixel."""
    return np.sqrt(((palette_lab[labels_a] - palette_lab[labels_b]) ** 2).sum(axis=2))


def _remove_small_regions(labels, min_area, protect=None):
    """Voeg te kleine vlakjes samen met het dichtstbijzijnde grotere vlak.

    Met protect (zie image_to_color_page) blijven kleine vlakjes staan die duidelijk afsteken
    en dik genoeg zijn, zoals een oog of een lichtpuntje.
    """
    for _ in range(3):
        region_ids, count = _label_regions(labels)
        areas = np.bincount(region_ids.ravel(), minlength=count + 1)

        small = areas < min_area
        small[0] = False

        if not small.any() or small[1:].all():
            break

        small_mask = small[region_ids]

        # Voor elke pixel in een klein vlak: de dichtstbijzijnde pixel die wel mag blijven
        nearest = ndimage.distance_transform_edt(
            small_mask, return_distances=False, return_indices=True
        )
        targets = labels[nearest[0], nearest[1]]

        remove = small.copy()

        if protect:
            ids = np.nonzero(small)[0]

            difference = _color_difference(protect["palette_lab"], labels, targets)
            contrast = ndimage.mean(difference, labels=region_ids, index=ids)
            thickness = _region_thickness(labels, region_ids, ids)

            keep = (
                (areas[ids] >= protect["floor_area"])
                & (contrast >= protect["threshold"])
                & (thickness >= protect["min_thickness"])
            )
            remove[ids[keep]] = False

        remove_mask = remove[region_ids]

        if not remove_mask.any():
            break

        labels = np.where(remove_mask, targets, labels)

    return labels


def _remove_thin_parts(labels, radius):
    """Haal delen weg die dunner zijn dan twee keer radius (een 'opening' per kleur).

    Dunne streepjes, smalle uitsteeksels en smalle halzen tussen twee delen van één vlak
    verdwijnen; de pixels gaan naar de dichtstbijzijnde buur. Brede vlakken blijven zoals ze zijn.
    """
    keep = np.zeros(labels.shape, dtype=bool)

    for index in np.unique(labels):
        mask = labels == index

        core = ndimage.distance_transform_edt(mask) > radius
        opened = ndimage.distance_transform_edt(~core) <= radius

        keep |= opened & mask

    removed = ~keep

    if not removed.any() or not keep.any():
        return labels

    nearest = ndimage.distance_transform_edt(removed, return_distances=False, return_indices=True)

    return labels[nearest[0], nearest[1]]


def _restore_details(raw, smoothed, palette_lab, threshold, floor_area, min_thickness):
    """Zet duidelijke kleine vormen terug die het gladstrijken heeft weggepoetst.

    Een vorm komt terug als hij (bijna) helemaal verdwenen is, sterk afsteekt tegen
    wat er nu staat, groot genoeg is en dik genoeg (dunne randjes tussen twee kleuren
    komen dus niet terug).
    """
    region_ids, count = _label_regions(raw)

    if count == 0:
        return smoothed

    ids = np.arange(1, count + 1)
    areas = np.bincount(region_ids.ravel(), minlength=count + 1)[1:]

    lost = raw != smoothed
    lost_count = ndimage.sum(lost, labels=region_ids, index=ids)

    difference = _color_difference(palette_lab, raw, smoothed)
    difference_sum = ndimage.sum(np.where(lost, difference, 0.0), labels=region_ids, index=ids)
    contrast = difference_sum / np.maximum(lost_count, 1)

    candidates = (areas >= floor_area) & (lost_count > 0.5 * areas) & (contrast >= threshold)

    # De dikte uitrekenen kost tijd, dus alleen voor de kandidaten
    thickness = np.zeros(count)
    candidate_ids = ids[candidates]

    if len(candidate_ids) > 0:
        thickness[candidates] = _region_thickness(raw, region_ids, candidate_ids)

    restore = candidates & (thickness >= min_thickness)

    restore_flags = np.zeros(count + 1, dtype=bool)
    restore_flags[1:] = restore
    restore_mask = restore_flags[region_ids]

    return np.where(restore_mask, raw, smoothed)


def _renumber_by_darkness(labels, palette):
    used = np.unique(labels)
    palette = palette[used]

    # Perceptuele helderheid (gewogen), donkerste eerst
    brightness = 0.299 * palette[:, 0] + 0.587 * palette[:, 1] + 0.114 * palette[:, 2]
    order = np.argsort(brightness)

    old_to_new = np.zeros(labels.max() + 1, dtype=np.int32)
    old_to_new[used[order]] = np.arange(len(used))

    return old_to_new[labels], palette[order]


# ---------------------------------------------------------------------------
# Tekenen van de lege variant
# ---------------------------------------------------------------------------

def _draw_empty_page(labels, palette, legend, line_width):
    height, width = labels.shape
    longest = max(width, height)

    if line_width is None:
        line_width = max(2.0, longest * 0.002)

    # Randen: waar twee buren een andere kleur hebben
    boundary = np.zeros(labels.shape, dtype=bool)
    boundary[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    boundary[:-1, :] |= labels[:-1, :] != labels[1:, :]

    # De rand van de afbeelding telt mee als rand, zodat nummers nooit half buiten beeld vallen
    # en er een nette lijst om de kleurplaat komt.
    boundary[0, :] = True
    boundary[-1, :] = True
    boundary[:, 0] = True
    boundary[:, -1] = True

    # Afstand tot de dichtstbijzijnde rand: geeft de lijnen en de plek waar het nummer
    # het best past (het "midden" van het vlak).
    distance = ndimage.distance_transform_edt(~boundary)

    # Lijnen: dikte bepalen, dan licht vervagen en weer scherp trekken.
    # Dat haalt de trapjes uit de randen en geeft zachte, vloeiende lijnen.
    line = (distance <= line_width / 2).astype(np.float32)
    line = ndimage.gaussian_filter(line, sigma=0.9)
    alpha = np.clip((line - 0.3) * 3, 0, 1)[..., None]

    page = 255.0 * (1 - alpha) + np.array(LINE_COLOR, dtype=np.float32) * alpha

    image = Image.fromarray(page.astype(np.uint8))
    draw = ImageDraw.Draw(image)

    # Een nummer in elk vlak, op de plek het verst van alle randen
    region_ids, count = _label_regions(labels)
    ids = np.arange(1, count + 1)

    positions = ndimage.maximum_position(distance, labels=region_ids, index=ids)
    radii = ndimage.maximum(distance, labels=region_ids, index=ids)

    base_font = max(10, round(longest * 0.011))

    for region_id, (y, x), radius in zip(ids, positions, radii):
        number = int(labels[y, x]) + 1
        font_size = int(max(7, min(base_font, radius * 1.5)))

        draw.text((x, y), str(number), fill=NUMBER_COLOR, font=_get_font(font_size), anchor="mm")

    if legend:
        image = _add_legend(image, palette)

    return image


def _add_legend(image, palette):
    """Plak onderaan een legenda: elk nummer met zijn kleur."""
    width, height = image.size
    longest = max(width, height)

    swatch = max(18, round(longest * 0.035))
    gap = round(swatch * 0.5)
    margin = round(swatch * 0.7)
    cell_width = round(swatch * 2.6)
    font = _get_font(max(10, round(swatch * 0.55)))

    per_row = max(1, (width - 2 * margin) // cell_width)
    rows = math.ceil(len(palette) / per_row)
    band_height = 2 * margin + rows * swatch + (rows - 1) * gap

    result = Image.new("RGB", (width, height + band_height), "white")
    result.paste(image, (0, 0))
    draw = ImageDraw.Draw(result)

    for index, color in enumerate(palette):
        row, column = divmod(index, per_row)

        items_in_row = min(per_row, len(palette) - row * per_row)
        row_width = items_in_row * cell_width
        x0 = (width - row_width) // 2 + column * cell_width
        y0 = height + margin + row * (swatch + gap)

        draw.rectangle(
            (x0, y0, x0 + swatch, y0 + swatch),
            fill=tuple(int(v) for v in color),
            outline=LINE_COLOR,
            width=1,
        )
        draw.text(
            (x0 + swatch + swatch * 0.25, y0 + swatch / 2),
            str(index + 1),
            fill=LEGEND_TEXT_COLOR,
            font=font,
            anchor="lm",
        )

    return result


_font_cache = {}


def _get_font(size):
    """Zoek een lettertype dat op elke server werkt."""
    if size in _font_cache:
        return _font_cache[size]

    candidates = []

    try:
        import matplotlib
        candidates.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf"))
    except Exception:
        pass

    candidates += ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]

    font = None

    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            break
        except (OSError, ValueError):
            continue

    if font is None:
        try:
            font = ImageFont.load_default(size)   # Pillow 10.1 of nieuwer
        except TypeError:
            font = ImageFont.load_default()

    _font_cache[size] = font
    return font


def _limit_size(img, max_size):
    width, height = img.size
    longest = max(width, height)

    if not max_size or longest <= max_size:
        return img

    scale = max_size / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))

    return img.resize(new_size, Image.LANCZOS)

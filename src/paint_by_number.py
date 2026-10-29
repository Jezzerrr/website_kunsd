"""Paint By Number (kleuren op nummer): een foto als 'schilderen op nummer'-pakket.

Honderden kleine vlakjes met veel kleuren (standaard 16), zoals de schilderpakketten uit
de winkel. Ingekleurd lijkt het weer echt op de foto. De bouwstenen staan in color_page.py.

Hoe het werkt (licht genoeg voor de Render free plan):
1. Alle rekenwerk gebeurt op een kleine versie van de foto (zo'n 400 tot 700 pixels).
   Vlakjes moeten toch groot genoeg zijn om een nummer in te schrijven, dus meer pixels
   voegen niets toe.
2. Kleuren kiezen (k-means in Lab, of eigen kleuren) en elke pixel de dichtstbijzijnde kleur geven.
3. Opruimen: randen licht gladstrijken, te dunne stukjes en te kleine vlakjes samenvoegen
   met hun buurman, zodat er in elk vlak een nummer past.
4. Pas daarna vergroten naar de printgrootte, met vloeiende randen.
5. Tekenen: dunne lijntjes, een nummer in elk vlak en een legenda.

Nodig: numpy, scipy en Pillow (staan al in requirements.txt).
"""

import numpy as np
from PIL import Image
from scipy import ndimage

from src.color_page import (
    _draw_empty_page,
    _nearest_color,
    _palette_from_image,
    _prepare,
    _remove_small_regions,
    _remove_thin_parts,
    _renumber_by_darkness,
    _smooth_labels,
)
from src.helper_functions.lab_colors import balanced_color_bias, parse_color, rgb_to_lab

# Automatische kleuren die minder dan dit verschillen (in Lab) worden samengevoegd: zulke
# kleuren zijn met verf of potlood toch niet uit elkaar te houden.
MIN_COLOR_DIFFERENCE = 8.0


def image_to_paint_by_number(
        img,
        n_colors=16,
        colors=None,
        detail=0.5,
        fill=False,
        legend=True,
        output_size=1600,
        seed=0,
):
    """Verander een afbeelding in een schilderen-op-nummer-plaat.

    Args:
        img: PIL Image.
        n_colors: aantal kleuren (alleen als colors niet is opgegeven). Handig bereik: 8 t/m 24.
            Bijna gelijke kleuren worden samengevoegd, dus soms worden het er iets minder.
        colors: eigen kleuren als lijst, bijv. [(255, 0, 0), "#00aa55"]. None = uit de foto.
        detail: 0 t/m 1. Hoger = meer en kleinere vlakjes (meer werk om in te kleuren).
        fill: True = ingekleurd (hoe het eruitziet als het af is), False = leeg met nummers.
        legend: bij de lege variant een legenda (nummer -> kleur) onder de afbeelding.
        output_size: langste zijde van het resultaat in pixels (1600 is genoeg voor A4).
        seed: zorgt dat dezelfde foto steeds dezelfde kleuren krijgt.

    Returns:
        PIL Image (RGB).
    """
    detail = float(np.clip(detail, 0, 1))

    # 1. Rekenen op een kleine versie
    work_size = int(400 + 400 * detail)
    small, rgb, lab = _prepare(img, work_size)
    width, height = small.size

    # Mediaanfilter: haalt ruis weg maar houdt randen (ogen, mond) scherp
    lab = ndimage.median_filter(lab, size=(3, 3, 1), mode="nearest")

    # 2. Kleuren
    bias = None

    if colors:
        palette = np.array([parse_color(c) for c in colors], dtype=np.float32)
        palette_lab = rgb_to_lab(palette[None, :, :])[0]

        flat_lab = lab.reshape(-1, 3)
        rng = np.random.default_rng(seed)
        sample = rng.choice(len(flat_lab), size=min(len(flat_lab), 40000), replace=False)
        bias = balanced_color_bias(flat_lab[sample], palette_lab)
    else:
        palette, palette_lab = _palette_from_image(rgb, lab, n_colors, seed)
        palette, palette_lab = _drop_similar_colors(palette, palette_lab)

    labels = _nearest_color(lab, palette_lab, bias)

    # 3. Opruimen. Kleinste vlak en kleinste dikte hangen af van detail: bij veel detail
    #    mogen vlakjes kleiner zijn (en worden de nummers kleiner).
    longest = max(width, height)
    labels = _smooth_labels(labels, sigma=0.8)
    labels = _remove_thin_parts(labels, radius=2.0)

    min_area = max(6, int((longest * (0.022 - 0.012 * detail)) ** 2))
    labels = _remove_small_regions(labels, min_area)

    labels, palette = _renumber_by_darkness(labels, palette)

    # 4. Vergroten naar printgrootte met vloeiende randen
    labels = _upscale_labels(labels, output_size / longest)

    if fill:
        return Image.fromarray(palette[labels].astype(np.uint8))

    # 5. Dunne lijntjes, want er zijn veel vlakjes
    line_width = max(2.0, output_size * 0.0013)

    return _draw_empty_page(labels, palette, legend, line_width)


def _drop_similar_colors(palette, palette_lab, min_difference=MIN_COLOR_DIFFERENCE):
    """Haal kleuren weg die bijna gelijk zijn aan een kleur die al gekozen is.

    Bij veel kleuren kiest k-means in een donkere foto vaak vier bijna-zwarten. Hun pixels gaan
    daarna vanzelf naar de dichtstbijzijnde overgebleven kleur.
    """
    keep = []

    for index, color in enumerate(palette_lab):
        if all(np.sqrt(((color - palette_lab[other]) ** 2).sum()) >= min_difference for other in keep):
            keep.append(index)

    return palette[keep], palette_lab[keep]


def _upscale_labels(labels, scale):
    """Vergroot een kaart met kleurnummers zonder trapjes.

    Elke kleur wordt als vloeiend masker vergroot (lineair) en per pixel wint het sterkste masker.
    """
    if scale <= 1:
        return labels

    best_weight = None
    result = None

    for index in np.unique(labels):
        mask = (labels == index).astype(np.float32)
        mask = ndimage.gaussian_filter(mask, sigma=1.0, mode="nearest")
        weight = ndimage.zoom(mask, scale, order=1, mode="nearest", grid_mode=True)

        if best_weight is None:
            best_weight = weight
            result = np.full(weight.shape, index, dtype=np.int32)
            continue

        stronger = weight > best_weight
        best_weight[stronger] = weight[stronger]
        result[stronger] = index

    return result

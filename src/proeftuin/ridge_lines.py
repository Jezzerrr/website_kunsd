"""Ridge Lines: je gezicht als een landschap van bergruggen, uitgeknipt uit lagen gekleurd papier.
Elke rug komt omhoog waar de foto donker is en heeft de kleur van de foto op die hoogte. De ruggen
liggen over elkaar heen en werpen een schaduw op de laag erachter: het lijkt een maquette van karton.

lines (20-90): het aantal lagen.
"""
import numpy as np
from scipy import ndimage

from ._common import fit, luminance, saturate, stretch, to_array, to_image

OUTPUT_SIZE = 1600
HEIGHT = 3.2             # hoe hoog een piek wordt, in laagafstanden
SHADOW = 0.55            # hoe donker de schaduw onder een rand is
PAPER = np.array([0.96, 0.94, 0.90], dtype=np.float32)


def image_to_ridge_lines(image, lines=45):
    lines = int(lines)
    pixels = saturate(to_array(fit(image, OUTPUT_SIZE)), 1.3)
    height, width = pixels.shape[:2]
    darkness = 1 - stretch(ndimage.gaussian_filter(luminance(pixels), max(height, width) / 300))

    margin = 0.05 * height
    spacing = (height - 2 * margin) / lines
    rows = np.arange(height, dtype=np.float32)[:, None]
    rng = np.random.default_rng(7)

    out = np.broadcast_to(PAPER, pixels.shape).copy()
    shade = np.ones((height, width), dtype=np.float32)

    # Van achter (boven) naar voor (onder): elke laag bedekt alles onder zijn rug
    for i in range(lines):
        base = margin + (i + 1) * spacing
        source_row = int(min(height - 1, (i + 0.5) / lines * height))
        band = slice(max(0, source_row - int(spacing / 2)), source_row + int(spacing / 2) + 1)

        value = darkness[band].mean(axis=0) ** 1.4
        value = ndimage.gaussian_filter1d(value + rng.normal(0, 0.03, width) * value, width / 400)
        ridge = base - value * HEIGHT * spacing                      # de bovenrand van deze laag, per kolom

        # Kleur van de laag: de foto op deze hoogte, in de breedte een beetje vervaagd (papier, geen foto)
        color = ndimage.gaussian_filter1d(pixels[band].mean(axis=0), width / 120, axis=0)

        # Alleen de rijen waar deze laag te zien is of schaduw geeft: van iets boven zijn hoogste punt tot
        # waar de volgende laag hem zeker bedekt (de laatste laag loopt door tot onderaan). Scheelt veel tijd.
        top = max(0, int(ridge.min() - 2 * spacing))
        bottom = height if i == lines - 1 else min(height, int(base + spacing) + 2)
        part = slice(top, bottom)

        depth = rows[part] - ridge[None, :]                          # hoe ver onder de rand (negatief: erboven)
        inside = depth >= 0
        # Een lichte snijrand bovenaan de laag, zoals bij gesneden karton
        edge = np.clip(1 - depth / max(1.5, height / 900), 0, 1)[..., None] * 0.18
        out[part] = np.where(inside[..., None], color[None, :, :] + edge, out[part])

        # Schaduw op de lagen erachter, vlak boven de rand; binnen de laag begint het weer licht
        shadow = 1 - SHADOW * np.exp(np.minimum(depth, 0) / (0.35 * spacing))
        shade[part] = np.where(inside, 1.0, shade[part] * shadow)

    return to_image(out * shade[..., None])

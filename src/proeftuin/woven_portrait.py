"""Woven Portrait: twee afdrukken van je foto, in stroken gesneden en door elkaar gevlochten, zoals een
mandje. De staande stroken zijn je foto in kleur, de liggende stroken dezelfde foto in blauwdruk.
De stroken zijn met de hand gesneden: ze liggen nooit helemaal recht, dus je gezicht verspringt een
beetje van strook tot strook. Elke keer net anders gevlochten (toeval).

strips (8-40): het aantal stroken in de breedte.
"""
import numpy as np

from ._common import fit, hex_colors, luminance, saturate, stretch, to_array, to_image

OUTPUT_SIZE = 1600
INK, PAPER = hex_colors("#0f2a5f", "#f4efe2")        # blauwdruk: donker en licht
SLIP = 0.32              # hoe ver een strook kan verschuiven, in strookbreedtes
GAP = 0.035              # de kier tussen twee stroken, in strookbreedtes


def image_to_woven_portrait(image, strips=18, seed=None):
    rng = np.random.default_rng(seed)
    strips = int(strips)
    pixels = to_array(fit(image, OUTPUT_SIZE))
    height, width = pixels.shape[:2]
    size = width / strips                                    # breedte van een strook in pixels

    color = saturate(pixels, 1.25)
    tone = stretch(luminance(pixels))[..., None]
    blueprint = INK + (PAPER - INK) * tone

    y, x = np.mgrid[0:height, 0:width]
    column, row = (x / size).astype(int), (y / size).astype(int)
    u, v = (x / size) % 1, (y / size) % 1                    # plek binnen het hokje (0-1)

    # Elke strook is een stukje verschoven in zijn lengterichting
    slip_down = (rng.normal(0, SLIP, column.max() + 1) * size).astype(int)
    slip_right = (rng.normal(0, SLIP, row.max() + 1) * size).astype(int)
    standing = color[np.clip(y + slip_down[column], 0, height - 1), x]
    lying = blueprint[y, np.clip(x + slip_right[row], 0, width - 1)]

    # Vlechten: om en om ligt de staande of de liggende strook boven
    standing_on_top = (column + row) % 2 == 0
    across = np.where(standing_on_top, u, v)                 # dwars over de bovenste strook
    along = np.where(standing_on_top, v, u)                  # in de lengte van de bovenste strook

    # Een strook bolt een beetje: donkerder aan zijn randen, en donkerder waar hij onder de volgende duikt
    shade = 1 - 0.30 * np.abs(2 * across - 1) ** 3
    shade *= 1 - 0.45 * np.exp(-np.minimum(along, 1 - along) / 0.10)
    kier = np.minimum(across, 1 - across) < GAP
    shade = np.where(kier, 0.25, shade)

    out = np.where(standing_on_top[..., None], standing, lying)
    return to_image(out * shade[..., None])

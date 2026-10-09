"""Kleurhulpjes die meerdere algoritmes gebruiken: kleuren inlezen, naar Lab omrekenen en
zorgen dat elke eigen gekozen kleur echt gebruikt wordt."""

import math

import numpy as np

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


def parse_color(color):
    if isinstance(color, str):
        text = color.strip().lstrip("#")

        if len(text) == 3:
            text = "".join(letter * 2 for letter in text)

        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))

    return tuple(int(value) for value in color[:3])


def rgb_to_lab(rgb):
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

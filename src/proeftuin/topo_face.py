"""Topo Face: je gezicht als maquette van gestapeld papier. De helderheid is de hoogte: elke hoogtelijn
is de rand van een nieuw vel in een eigen kleur, en elk vel werpt een schaduw op het vel eronder.
Zoals de hoogtekaarten die uit lagen karton worden gesneden.

levels (4-16): het aantal lagen papier.
"""
import numpy as np
from scipy import ndimage

from ._common import fit, hex_colors, luminance, stretch, to_array, to_image

OUTPUT_SIZE = 1500
PALETTE = hex_colors("#14213d", "#1d4e89", "#2a9d8f", "#8ab17d", "#e9c46a", "#f4a261", "#e76f51", "#fdf0d5")
SHADOW = 0.6             # hoe donker de schaduw van een vel is


def image_to_topo_face(image, levels=9):
    levels = int(levels)
    pixels = to_array(fit(image, OUTPUT_SIZE))
    longest = max(pixels.shape)
    height = stretch(ndimage.gaussian_filter(luminance(pixels), longest / 220))
    value = height * (levels - 0.02) + 0.01
    layer = np.floor(value)                                  # op welk vel ligt elke pixel (0 = onderste)
    del pixels, height

    # Kleur per vel, uit het palet
    position = layer / max(levels - 1, 1) * (len(PALETTE) - 1)
    # (Kleine gehele getallen en del: Render heeft maar 512 MB geheugen.)
    low = np.floor(position).astype(np.int8)
    high = np.minimum(low + 1, len(PALETTE) - 1).astype(np.int8)
    t = (position - low)[..., None]
    del position
    out = PALETTE[low] * (1 - t)
    out += PALETTE[high] * t
    del low, high, t

    # Gladde randen: vlak bij een rand mengen de twee vellen over één pixel (anders kartelt het)
    gy, gx = np.gradient(value)
    slope = np.hypot(gx, gy) + 1e-6

    # Schaduw: het licht komt van linksboven. Schuif de lagenkaart naar rechtsonder en vervaag hem;
    # waar die hoger is dan het vel zelf, ligt er een hoger vel vlakbij dat schaduw geeft.
    offset = longest / 160
    lifted = ndimage.shift(layer, (offset, offset), order=1, mode="nearest")
    lifted = ndimage.gaussian_filter(lifted, offset * 0.9)
    shadow = np.clip(lifted - layer, 0, 1.5) / 1.5
    del lifted

    # Een lichte snijrand aan de lichtkant van elk vel, en papierkorrel
    distance = (value - layer) / slope                       # pixels tot de onderrand van dit vel
    light_side = np.clip(-(gx + gy) / slope, 0, 1)
    rim = np.clip(1 - distance / (longest / 700), 0, 1) * light_side * (layer > 0)
    del distance, light_side, gx, gy, slope, value
    grain = np.random.default_rng(3).normal(0, 0.012, layer.shape).astype(np.float32)

    out *= 1 - SHADOW * shadow[..., None]
    out += rim[..., None] * 0.22
    out += grain[..., None]
    return to_image(out)


"""Woven Portrait: twee afdrukken van je foto, in stroken gesneden en door elkaar gevlochten, zoals een
mandje. De staande stroken zijn je foto in kleur, de liggende stroken dezelfde foto in blauwdruk.
De stroken zijn met de hand gesneden: ze liggen nooit helemaal recht, dus je gezicht verspringt een
beetje van strook tot strook. Elke keer net anders gevlochten (toeval).

strips (8-40): het aantal stroken in de breedte.
"""
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from ._common import fit, hex_colors

OUTPUT_SIZE = 1600
INK, PAPER = hex_colors("#0f2a5f", "#f4efe2")        # blauwdruk: donker en licht
SLIP = 0.32              # hoe ver een strook kan verschuiven, in strookbreedtes
GAP = 0.035              # de kier tussen twee stroken, in strookbreedtes


def image_to_woven_portrait(image, strips=18, seed=None):
    rng = np.random.default_rng(seed)
    strips = int(strips)
    photo = fit(image, OUTPUT_SIZE).convert("RGB")
    color = np.asarray(ImageEnhance.Color(photo).enhance(1.25))          # hele getallen 0-255: zuinig
    height, width = color.shape[:2]
    size = width / strips                                    # breedte van een strook in pixels

    # Blauwdruk: de helderheid (opgerekt) tussen inkt en papier
    grey = np.asarray(ImageOps.autocontrast(photo.convert("L"), cutoff=1), dtype=np.float32)[..., None] / 255
    blueprint = ((INK + (PAPER - INK) * grey) * 255).astype(np.uint8)
    del grey

    # Stroken en de plek binnen een hokje hangen alleen af van x (staand) of alleen van y (liggend):
    # daarom lijstjes van één rij of één kolom, geen volle beelden (scheelt veel geheugen)
    xs, ys = np.arange(width), np.arange(height)
    column, row = (xs / size).astype(int), (ys / size).astype(int)
    u, v = ((xs / size) % 1).astype(np.float32), ((ys / size) % 1).astype(np.float32)

    # Elke strook is een stukje verschoven in zijn lengterichting
    slip_down = (rng.normal(0, SLIP, column.max() + 1) * size).astype(int)
    slip_right = (rng.normal(0, SLIP, row.max() + 1) * size).astype(int)
    standing = color[np.clip(ys[:, None] + slip_down[column][None, :], 0, height - 1), xs[None, :]]
    lying = blueprint[ys[:, None], np.clip(xs[None, :] + slip_right[row][:, None], 0, width - 1)]
    del color, blueprint

    # Vlechten: om en om ligt de staande of de liggende strook boven
    standing_on_top = (column[None, :] + row[:, None]) % 2 == 0
    out = np.where(standing_on_top[..., None], standing, lying)
    del standing, lying

    # Een strook bolt een beetje: donkerder aan zijn randen, en donkerder waar hij onder de volgende duikt.
    # across is dwars over de bovenste strook, along in zijn lengte.
    across = np.where(standing_on_top, u[None, :], v[:, None])
    along = np.where(standing_on_top, v[:, None], u[None, :])
    del standing_on_top
    shade = 1 - np.float32(0.30) * np.abs(2 * across - 1) ** 3
    shade *= 1 - np.float32(0.45) * np.exp(-np.minimum(along, 1 - along) / np.float32(0.10))
    shade[np.minimum(across, 1 - across) < GAP] = 0.25
    del across, along

    return Image.fromarray((out * shade[..., None] + 0.5).astype(np.uint8))

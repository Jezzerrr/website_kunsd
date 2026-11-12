"""Stained Glass: de foto als glas-in-lood. Honderden scherven in de kleur van de foto, met donkere
loodlijnen ertussen. Kleine scherven waar veel gebeurt (ogen, mond), grote in de achtergrond.
Elke keer een ander patroon.

shards (150-2500): het aantal scherven.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from scipy.spatial import Voronoi, cKDTree

from src.helper_functions.arrays import fit, luminance, saturate, stretch, to_array

OUTPUT_SIZE = 1800
LABEL_SIZE = 360         # op deze mini-versie wordt de kleur per scherf bepaald
LEAD = (28, 24, 22)


def image_to_stained_glass(image, shards=800, seed=None):
    rng = np.random.default_rng(seed)
    shards = int(shards)
    small = to_array(fit(image, LABEL_SIZE))
    height, width = small.shape[:2]

    # Waar de foto veel verandert, meer scherven
    lum = ndimage.gaussian_filter(luminance(small), 1.0)
    detail = stretch(np.hypot(ndimage.sobel(lum, 0), ndimage.sobel(lum, 1)), 5, 99)
    weight = (0.15 + ndimage.gaussian_filter(detail, 2.0)).ravel()
    index = rng.choice(weight.size, size=shards, replace=False, p=weight / weight.sum())
    points = np.column_stack([index % width, index // width]).astype(float)
    points += rng.random(points.shape)

    # Kleur per scherf: het gemiddelde van de pixels die het dichtst bij dat punt liggen
    grid = np.column_stack([a.ravel() for a in np.mgrid[0:height, 0:width][::-1]]) + 0.5
    _, label = cKDTree(points).query(grid)
    counts = np.bincount(label, minlength=shards)
    colors = np.stack([np.bincount(label, small[..., c].ravel(), minlength=shards) for c in range(3)], axis=1)
    colors = colors / np.maximum(counts, 1)[:, None]

    # Glas is feller en heeft per scherf een iets andere helderheid
    colors = saturate(colors, 1.5) * rng.uniform(0.85, 1.12, (shards, 1))
    colors = np.clip(colors, 0, 1)

    scale = OUTPUT_SIZE / max(width, height)
    size = (round(width * scale), round(height * scale))
    canvas = Image.new("RGB", size, LEAD)
    draw = ImageDraw.Draw(canvas)
    lead = max(2, round(OUTPUT_SIZE / 450))

    # Voronoi-vlakken, met vier verre punten erbij zodat ook de randscherven gesloten zijn
    far = 10 * max(width, height)
    vor = Voronoi(np.vstack([points, [[-far, -far], [far, -far], [far, far], [-far, far]]]))

    for i in range(shards):
        region = vor.regions[vor.point_region[i]]

        if not region or -1 in region:
            continue

        polygon = [tuple(v) for v in vor.vertices[region] * scale]
        draw.polygon(polygon, fill=tuple(int(v * 255) for v in colors[i]), outline=LEAD, width=lead)

    # Een vleugje licht dat door het glas valt
    glow = canvas.filter(ImageFilter.GaussianBlur(OUTPUT_SIZE / 120))
    return Image.blend(canvas, Image.composite(glow, canvas, Image.new("L", size, 90)), 0.5)

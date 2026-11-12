"""Flow Strokes: de foto opnieuw geschilderd met duizenden penseelstreken die de vormen van het
gezicht volgen, zoals bij Van Gogh. Eerst brede streken voor de ondergrond, dan fijne voor de details.
Elke keer net anders.

length (1-10): hoe lang de penseelstreken zijn.
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from src.helper_functions.arrays import fit, luminance, saturate, stretch, to_array

OUTPUT_SIZE = 1600
FIELD_SIZE = 400


def image_to_flow_strokes(image, length=5, seed=None):
    rng = np.random.default_rng(seed)
    photo = fit(image, OUTPUT_SIZE)
    pixels = saturate(to_array(photo), 1.35)
    height, width = pixels.shape[:2]

    # De richting van de vormen (structuurtensor), op een kleine versie
    small = to_array(fit(image, FIELD_SIZE))
    lum = ndimage.gaussian_filter(luminance(small), 1.5)
    gx, gy = ndimage.sobel(lum, 1), ndimage.sobel(lum, 0)
    jxx = ndimage.gaussian_filter(gx * gx, 4)
    jyy = ndimage.gaussian_filter(gy * gy, 4)
    jxy = ndimage.gaussian_filter(gx * gy, 4)
    edge_angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2       # langs de randen, niet eroverheen
    detail = stretch(ndimage.gaussian_filter(np.hypot(gx, gy), 2), 5, 99)
    field_scale = small.shape[1] / width

    # Ondergrond: de vage foto
    canvas = Image.fromarray((ndimage.gaussian_filter(pixels, (12, 12, 0)) * 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)
    longest = max(width, height)
    steps = int(4 + 2.4 * length)

    # Drie lagen: breed en overal, middel, en fijn alleen waar veel detail is
    for brush, count, detail_only in ((0.018, 1300, False), (0.009, 3000, False), (0.0045, 4500, True)):
        points = rng.random((count, 2)) * [width, height]

        if detail_only:
            keep = sample(detail, points * field_scale) > rng.random(count) * 0.8
            points = points[keep]

        step = brush * longest * 0.9
        paths = trace(points, edge_angle, field_scale, step, steps, width, height, rng)
        colors = pixels[paths[:, 0, 1].astype(int).clip(0, height - 1), paths[:, 0, 0].astype(int).clip(0, width - 1)]
        colors = np.clip(colors * rng.uniform(0.9, 1.1, (len(colors), 1)), 0, 1)
        stroke_width = max(1, round(brush * longest))

        for path, color in zip(paths, colors):
            draw.line([tuple(p) for p in path], fill=tuple(int(v * 255) for v in color),
                      width=stroke_width, joint="curve")

    return canvas


def trace(points, angle, field_scale, step, steps, width, height, rng):
    """Volgt de richting vanaf elk startpunt: alle streken tegelijk (numpy), steps stapjes lang."""
    position = points.copy()
    direction = None
    paths = [position.copy()]
    jitter = rng.normal(0, 0.15, len(points))

    for _ in range(steps):
        a = sample(angle, position * field_scale, order=0) + jitter
        new = np.column_stack([np.cos(a), np.sin(a)])

        # Een richting heeft twee kanten: blijf dezelfde kant op gaan als de vorige stap
        if direction is not None:
            flip = (new * direction).sum(axis=1) < 0
            new[flip] *= -1

        direction = new
        position = position + new * step
        position[:, 0] = position[:, 0].clip(0, width - 1)
        position[:, 1] = position[:, 1].clip(0, height - 1)
        paths.append(position.copy())

    return np.stack(paths, axis=1)


def sample(field, points, order=1):
    return ndimage.map_coordinates(field, [points[:, 1], points[:, 0]], order=order, mode="nearest")

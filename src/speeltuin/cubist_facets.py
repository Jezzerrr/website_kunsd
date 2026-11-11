"""Cubist Facets (Speeltuin): de foto gebroken langs rechte lijnen, als een kubistisch schilderij. Elk vlak
laat het gezicht net anders zien: iets gedraaid, verschoven, groter of kleiner, en in een eigen tint.
Elke keer andere breuken (toeval).

cuts (3-14): het aantal breuklijnen.

Begonnen in de Proeftuin (2026-11-11), daarna verhuisd naar de Speeltuin.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

OUTPUT_SIZE = 1600
TINTS = np.array([[1.20, 0.92, 0.75], [0.78, 0.92, 1.22], [1.10, 1.08, 0.72],
                  [0.95, 0.78, 1.12], [1.0, 1.0, 1.0], [0.82, 1.12, 0.92]], dtype=np.float32)


def image_to_cubist_facets(image, cuts=8, seed=None):
    rng = np.random.default_rng(seed)
    cuts = int(cuts)

    scale = OUTPUT_SIZE / max(image.size)
    image = image.convert("RGB").resize((round(image.width * scale), round(image.height * scale)),
                                         Image.Resampling.LANCZOS)
    pixels = np.asarray(image, dtype=np.float32) / 255
    height, width = pixels.shape[:2]
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)

    # Willekeurige rechte lijnen door de foto (door een punt dicht bij het midden, onder een willekeurige hoek).
    # Per pixel: aan welke kant van elke lijn hij ligt. Die combinatie is het vlak.
    label = np.zeros((height, width), dtype=np.int64)
    edge = np.full((height, width), np.inf, dtype=np.float32)

    for i in range(cuts):
        px, py = width * rng.uniform(0.2, 0.8), height * rng.uniform(0.2, 0.8)
        angle = rng.uniform(0, np.pi)
        side = (x - px) * np.sin(angle) - (y - py) * np.cos(angle)
        label |= (side > 0).astype(np.int64) << i
        edge = np.minimum(edge, np.abs(side))

    _, label = np.unique(label, return_inverse=True)
    label = label.reshape(height, width)
    count = label.max() + 1

    # Per vlak een eigen kijk: draaien en schalen rond het midden van het vlak, en een beetje verschuiven
    centers_x = np.asarray(ndimage.mean(x, label, np.arange(count)))
    centers_y = np.asarray(ndimage.mean(y, label, np.arange(count)))
    rotation = rng.normal(0, 0.16, count)
    zoom = rng.uniform(0.8, 1.4, count)
    shift = rng.normal(0, 0.03 * max(width, height), (count, 2))

    cx, cy = centers_x[label], centers_y[label]
    cos, sin, s = np.cos(rotation)[label], np.sin(rotation)[label], zoom[label]
    dx, dy = x - cx, y - cy
    source_x = cx + (cos * dx - sin * dy) / s + shift[label, 0]
    source_y = cy + (sin * dx + cos * dy) / s + shift[label, 1]

    channels = [ndimage.map_coordinates(pixels[..., c], [source_y, source_x], order=1, mode="mirror")
                for c in range(3)]
    out = np.clip(np.stack(channels, axis=-1) * TINTS[rng.integers(0, len(TINTS), count)][label], 0, 1)

    # Iets fellere kleuren
    grey = (out[..., 0] * 0.299 + out[..., 1] * 0.587 + out[..., 2] * 0.114)[..., None]
    out = np.clip(grey + (out - grey) * 1.15, 0, 1)

    # Dunne donkere breuklijnen
    line = max(1.0, max(width, height) / 900)
    alpha = np.clip(line + 0.5 - edge, 0, 1)[..., None] * 0.8
    out = out * (1 - alpha) + 0.08 * alpha

    return Image.fromarray((out * 255 + 0.5).astype(np.uint8))

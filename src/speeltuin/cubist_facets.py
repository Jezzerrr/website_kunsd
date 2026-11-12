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
    pixels = np.asarray(image)                               # hele getallen 0-255: zuinig met geheugen
    height, width = pixels.shape[:2]
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)

    # Willekeurige rechte lijnen door de foto (door een punt dicht bij het midden, onder een willekeurige hoek).
    # Per pixel: aan welke kant van elke lijn hij ligt. Die combinatie is het vlak.
    # (Overal float32 en int32 in plaats van de standaard 64 bits: dat halveert het geheugen. Op het
    # Render free plan is er maar 512 MB; met een telefoonfoto liep dit eerder vol.)
    code = np.zeros((height, width), dtype=np.int32)
    edge = np.full((height, width), np.inf, dtype=np.float32)

    for i in range(cuts):
        px, py = width * rng.uniform(0.2, 0.8), height * rng.uniform(0.2, 0.8)
        angle = rng.uniform(0, np.pi)
        side = (x - np.float32(px)) * np.float32(np.sin(angle)) - (y - np.float32(py)) * np.float32(np.cos(angle))
        code |= (side > 0).astype(np.int32) << i
        np.minimum(edge, np.abs(side), out=edge)

    del side

    # De codes die voorkomen omnummeren tot 0, 1, 2, ...
    present = np.zeros(1 << cuts, dtype=bool)
    present[code] = True
    label = (np.cumsum(present) - 1).astype(np.int32)[code]
    count = int(present.sum())
    del code

    # Per vlak een eigen kijk: draaien en schalen rond het midden van het vlak, en een beetje verschuiven
    numbers = np.arange(count)
    centers_x = np.asarray(ndimage.mean(x, label, numbers), dtype=np.float32)
    centers_y = np.asarray(ndimage.mean(y, label, numbers), dtype=np.float32)
    rotation = rng.normal(0, 0.16, count)
    zoom = rng.uniform(0.8, 1.4, count)
    shift = rng.normal(0, 0.03 * max(width, height), (count, 2)).astype(np.float32)
    cos = (np.cos(rotation) / zoom).astype(np.float32)
    sin = (np.sin(rotation) / zoom).astype(np.float32)

    # Bronpositie per pixel: x en y worden hier ter plekke omgerekend (geen extra kopieën)
    x -= centers_x[label]
    y -= centers_y[label]
    source_x = cos[label] * x
    source_x -= sin[label] * y
    source_x += (centers_x + shift[:, 0])[label]
    source_y = sin[label] * x
    source_y += cos[label] * y
    source_y += (centers_y + shift[:, 1])[label]
    del x, y

    # Per kleurkanaal: de foto ophalen op de bronpositie, en de tint van het vlak erover
    tints = TINTS[rng.integers(0, len(TINTS), count)]
    out = np.empty((height, width, 3), dtype=np.float32)

    for c in range(3):
        channel = ndimage.map_coordinates(pixels[..., c], [source_y, source_x], order=1, mode="mirror",
                                          output=np.float32)
        channel *= tints[:, c][label] / 255
        out[..., c] = channel

    del source_x, source_y, label, channel
    np.clip(out, 0, 1, out=out)

    # Iets fellere kleuren
    grey = (out[..., 0] * 0.299 + out[..., 1] * 0.587 + out[..., 2] * 0.114)[..., None]
    out -= grey
    out *= 1.15
    out += grey
    del grey

    # Dunne donkere breuklijnen
    line = max(1.0, max(width, height) / 900)
    alpha = np.clip(line + 0.5 - edge, 0, 1)[..., None] * np.float32(0.8)
    out *= 1 - alpha
    out += np.float32(0.08) * alpha
    np.clip(out, 0, 1, out=out)
    out *= 255

    return Image.fromarray((out + 0.5).astype(np.uint8))

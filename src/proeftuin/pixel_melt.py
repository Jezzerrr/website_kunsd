"""Pixel Melt: de foto smelt naar beneden, als was die te warm is geworden. Elke plek smelt een beetje,
sommige plekken heel erg: daar rekt de foto uit en druipt hij in lange slierten omlaag.

Het loopt niet overal recht naar beneden uit: een onzichtbare stroming stuurt het hier naar links en daar
naar rechts, in bochten (zie flow_paths).

Twee stappen, allebei langs die stroomlijnen:
1. Uitrekken: een smeltkaart (vloeiende ruis) zegt per plek hoe hard hij smelt. Waar het hard smelt, wordt
   de foto naar beneden uitgerekt; zo zakken ogen en mond weg.
2. Druipen: stukken van elke kolom worden op helderheid gesorteerd (pixel sorting), donker boven en licht
   onder. Waar het hard smelt zijn die stukken lang (druppels), elders heel kort (alleen wat ruis).
Elke keer smelt het ergens anders (toeval).

melt (10-100): hoe hard alles smelt.
"""
import numpy as np
from scipy import ndimage

from ._common import fit, luminance, to_array, to_image

WORK_SIZE = 1400
LEAN = 0.8               # de grootste schuinte van het uitlopen (0.8 is ongeveer 40 graden)


def image_to_pixel_melt(image, melt=60, seed=None):
    melt = melt / 100
    rng = np.random.default_rng(seed)
    pixels = to_array(fit(image, WORK_SIZE))
    height, width = pixels.shape[:2]

    # Het smelt niet recht naar beneden: een stroming (vloeiende ruis) zegt per plek hoe schuin het
    # wegloopt, hier naar links, daar naar rechts, in bochten. We volgen vanaf de bovenrand een stroomlijn
    # per kolom (paths[y, k] is de x-positie van stroomlijn k op rij y), trekken de foto langs die lijnen
    # recht, laten hem dan gewoon per kolom smelten, en buigen het resultaat weer terug.
    paths = flow_paths(rng, height, width)
    rows = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], paths.shape)
    pixels = np.stack([ndimage.map_coordinates(pixels[..., c], [rows, paths], order=1, mode="mirror")
                       for c in range(3)], axis=-1)

    pixels = melt_down(pixels, rng, melt)

    # Terugbuigen: voor elke pixel de stroomlijn opzoeken die erdoorheen loopt
    lanes = np.arange(paths.shape[1], dtype=np.float32)
    columns = np.arange(width, dtype=np.float32)
    lane = np.stack([np.interp(columns, paths[y], lanes) for y in range(height)]).astype(np.float32)
    rows = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], lane.shape)
    del paths

    return to_image(np.stack([ndimage.map_coordinates(pixels[..., c], [rows, lane], order=1, mode="nearest")
                              for c in range(3)], axis=-1))


def flow_paths(rng, height, width):
    """De stroomlijnen: een beeld van height bij ongeveer 1.6 x width, met per rij de x-positie van elke lijn.
    De lijnen beginnen bovenaan naast elkaar (ook een stuk buiten de foto, zodat de randen gevuld blijven)
    en volgen rij voor rij de stroming. Ze kruisen elkaar nooit."""
    small = (max(4, height // 60), max(4, width // 60))
    lean = ndimage.gaussian_filter(rng.normal(size=small), 2.0)
    lean = LEAN * lean / (np.abs(lean).max() + 1e-9)                    # schuinte: pixels opzij per rij omlaag
    lean = ndimage.zoom(lean, (height / small[0], width / small[1]), order=1)[:height, :width]

    position = np.linspace(-0.3 * width, 1.3 * width, int(1.6 * width))
    columns = np.arange(lean.shape[1])
    paths = np.empty((height, len(position)), dtype=np.float32)

    for y in range(height):
        paths[y] = position
        position = position + np.interp(position, columns, lean[min(y, lean.shape[0] - 1)])
        position = np.maximum.accumulate(position + np.arange(len(position)) * 1e-4)      # blijven op volgorde

    return paths


def melt_down(pixels, rng, melt):
    """Laat een beeld recht naar beneden smelten (uitrekken en druipen, zie boven)."""
    height, width = pixels.shape[:2]
    heat = melt_map(rng, height, width, melt)

    # 1. Uitrekken. stretch is per pixel hoeveel de bronpositie achterblijft (0: niet, 0.9: bijna stilstaan).
    #    De bronpositie loopt per kolom op met (1 - stretch): waar stretch groot is, wordt de foto uitgerekt.
    stretch = 0.8 * heat ** 2.2
    source_y = np.cumsum(1 - stretch, axis=0) - (1 - stretch[:1])
    source_x = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width))
    pixels = np.stack([ndimage.map_coordinates(pixels[..., c], [source_y, source_x], order=1, mode="nearest")
                       for c in range(3)], axis=-1)

    # 2. Druipen: per kolom (na transponeren is elke rij een kolom)
    columns = np.ascontiguousarray(pixels.transpose(1, 0, 2))
    lum = luminance(columns)
    heat_t = heat.T

    # Een stuk breekt vaker af waar het weinig smelt: daar blijven de druppels kort
    breaks = rng.random(lum.shape, dtype=np.float32) < 0.3 * (1 - heat_t) ** 3 + 0.002

    # Heel lichte en heel donkere pixels druipen alleen mee waar het echt heet is
    middle = np.abs(lum - np.median(lum)) < 0.08 + 0.45 * heat_t
    new_piece = np.ones_like(breaks)
    new_piece[:, 1:] = breaks[:, 1:] | (middle[:, 1:] != middle[:, :-1]) | ~middle[:, 1:]
    piece = np.cumsum(new_piece, axis=1, dtype=np.int32)
    del breaks, middle, new_piece

    # (float32 en int32: de helft van het geheugen van de standaard 64 bits; Render heeft maar 512 MB)
    key = piece.astype(np.float32)
    key *= 2
    key += lum
    del piece, lum
    order = np.argsort(key, axis=1, kind="stable").astype(np.int32)
    del key
    columns = np.take_along_axis(columns, order[..., None], axis=1)

    return columns.transpose(1, 0, 2)


def melt_map(rng, height, width, melt):
    """Hoe hard elke plek smelt (0-1): grote vloeiende vlekken plus smalle verticale slierten,
    en naar beneden toe iets heter. Nergens helemaal 0."""
    small = (max(4, height // 40), max(4, width // 40))
    blobs = ndimage.gaussian_filter(rng.normal(size=small), 2.5)
    blobs = ndimage.zoom((blobs - blobs.min()) / (np.ptp(blobs) + 1e-9), (height / small[0], width / small[1]), order=1)
    blobs = blobs[:height, :width]

    streaks = ndimage.gaussian_filter1d(rng.random(width), 1.5)
    streaks = (streaks - streaks.min()) / (np.ptp(streaks) + 1e-9)

    down = np.linspace(0, 1, height)[:, None]
    heat = 0.55 * blobs + 0.3 * streaks[None, :] + 0.25 * down
    heat = np.clip((heat - 0.25) * (0.3 + 1.3 * melt), 0, 1)

    return np.clip(0.12 + 0.88 * heat, 0, 1).astype(np.float32)

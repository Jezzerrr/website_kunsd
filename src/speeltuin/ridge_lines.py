"""Ridge Lines: je foto als een stapel witte golflijnen op zwart, zoals het signaal van een pulsar.
Elke lijn schiet omhoog waar de foto donker is en verbergt de lijnen erachter. De pieken zijn hoog en
de randen blijven vlak, dus je gezicht wordt een bergketen in het midden van het blad: abstract, je
herkent hooguit nog een silhouet.

lines (30-120): het aantal lijnen.
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from src.helper_functions.arrays import fit, luminance, stretch, to_array

OUTPUT_SIZE = 2000
SUPERSAMPLE = 2          # twee keer zo groot tekenen en verkleinen: gladde lijnen
HEIGHT = 7.0             # hoe hoog een piek wordt, in lijnafstanden
POINTS_ACROSS = 360      # punten per lijn
SIDE = 0.16              # zo breed (fractie) blijft links en rechts een vlakke rand
BACKGROUND = (10, 10, 12)
INK = (242, 238, 228)


def image_to_ridge_lines(image, lines=64, seed=None):
    rng = np.random.default_rng(seed)
    lines = int(lines)
    pixels = to_array(fit(image, 500))
    darkness = 1 - stretch(ndimage.gaussian_filter(luminance(pixels), 2.0))
    height, width = darkness.shape

    out_w, out_h = (round(OUTPUT_SIZE * width / max(width, height)),
                    round(OUTPUT_SIZE * height / max(width, height)))
    s = SUPERSAMPLE
    canvas = Image.new("RGB", (out_w * s, out_h * s), BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    top, bottom = 0.16 * out_h * s, 0.94 * out_h * s         # boven ruimte voor de hoogste pieken
    spacing = (bottom - top) / lines
    margin = 0.07 * out_w * s
    xs = np.linspace(margin, out_w * s - margin, POINTS_ACROSS)
    sample_x = np.linspace(0, width - 1, POINTS_ACROSS)
    line_width = max(2, round(out_h * s / 620))

    # De randen vlak, het midden vol: de pieken groeien pas vanaf SIDE naar binnen
    position = np.linspace(0, 1, POINTS_ACROSS)
    envelope = np.clip(np.minimum(position, 1 - position) / SIDE - 0.25, 0, 1)
    envelope = envelope * envelope * (3 - 2 * envelope)

    for i in range(lines):
        base = top + (i + 1) * spacing
        sample_y = np.full(POINTS_ACROSS, (i + 0.5) / lines * (height - 1))
        value = ndimage.map_coordinates(darkness, [sample_y, sample_x], order=1)

        # Grillige pieken: de donkerte, sterk aangezet, maal een toevallig bergprofiel. Daardoor volgt een
        # lijn de foto niet braaf, maar breekt hij op in toppen en dalen.
        crags = ndimage.gaussian_filter1d(rng.random(POINTS_ACROSS), 2.5)
        crags = 0.35 + 1.3 * (crags - crags.min()) / (np.ptp(crags) + 1e-9)
        value = value ** 2.2 * crags * envelope
        value += np.abs(rng.normal(0, 0.012, POINTS_ACROSS))                 # ruis op de vlakke stukken
        ys = base - ndimage.gaussian_filter1d(value, 1.2) * HEIGHT * spacing

        points = list(zip(xs, ys))
        # Eerst de ruimte onder de lijn zwart maken (verbergt de lijnen erachter), dan de lijn zelf
        draw.polygon(points + [(xs[-1], out_h * s), (xs[0], out_h * s)], fill=BACKGROUND)
        draw.line(points, fill=INK, width=line_width, joint="curve")

    return canvas.resize((out_w, out_h), Image.Resampling.LANCZOS)

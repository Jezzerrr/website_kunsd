"""Kaleido Face: in het midden je gezicht zoals het is, en naar buiten toe valt het uiteen in een
caleidoscoop van je eigen ogen, haar en mond. Het gezicht lost op in een mandala.
Elke keer een ander stuk van je foto in de caleidoscoop (toeval).

mirrors (3-12): het aantal spiegelingen rondom.
"""
import numpy as np
from scipy import ndimage

from ._common import fit, saturate, to_array, to_image

OUTPUT_SIZE = 1400
WORK_SIZE = 1400
FACE_RADIUS = 0.40       # tot hier is het gezicht ongeschonden (fractie van de halve breedte)
BLEND = 0.05             # over deze afstand gaat het gezicht over in de caleidoscoop


def image_to_kaleido_face(image, mirrors=6, seed=None):
    rng = np.random.default_rng(seed)
    mirrors = int(mirrors)
    pixels = to_array(fit(image, WORK_SIZE))
    height, width = pixels.shape[:2]

    size = OUTPUT_SIZE
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    x -= size / 2
    y -= size / 2
    radius = np.hypot(x, y) / (size / 2)
    angle = np.arctan2(y, x)

    # Vouwen: elke hoek naar de eerste taartpunt, met elke tweede punt gespiegeld
    wedge = np.pi / mirrors
    folded = np.mod(angle, 2 * wedge)
    folded = np.where(folded > wedge, 2 * wedge - folded, folded)
    kaleido_angle = folded + rng.uniform(0, 2 * np.pi) + rng.uniform(-0.5, 0.5) * radius

    # Buiten het gezicht spiegelt ook de afstand tot het midden heen en weer (een zigzag): zo komen
    # ogen, mond en haar in ringen terug. Op de rand van het gezicht sluit het precies aan.
    period = 0.75 * FACE_RADIUS
    phase = np.maximum(radius - FACE_RADIUS, 0) / period
    zigzag = np.abs(np.mod(phase + 1, 2) - 1)
    kaleido_radius = FACE_RADIUS * (1 - 0.8 * (1 - zigzag))
    kaleido_radius = np.where(radius > FACE_RADIUS, kaleido_radius, radius)
    del x, y, folded, phase, zigzag                          # opruimen: Render heeft maar 512 MB

    # Het gezicht zit meestal iets boven het midden; de rand van het gezicht valt op 0.4 van de foto
    reach = 0.5 * min(width, height) * 0.95 / FACE_RADIUS * 0.45
    center_x, center_y = width / 2, height * 0.45

    def sample(r, a):
        sx = center_x + np.cos(a) * r * reach
        sy = center_y + np.sin(a) * r * reach
        return np.stack([ndimage.map_coordinates(pixels[..., c], [sy, sx], order=1, mode="mirror")
                         for c in range(3)], axis=-1)

    face = sample(radius, angle)
    del angle
    kaleido = saturate(sample(kaleido_radius, kaleido_angle), 1.5)
    del kaleido_radius, kaleido_angle, pixels

    # Zachte overgang van gezicht naar caleidoscoop
    t = np.clip((radius - FACE_RADIUS) / BLEND, 0, 1)[..., None]
    t = t * t * (3 - 2 * t)
    face *= 1 - t
    kaleido *= t
    face += kaleido
    return to_image(face)

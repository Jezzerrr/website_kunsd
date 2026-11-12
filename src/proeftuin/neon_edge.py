"""Neon Edge: je portret in een donkere kamer, alleen verlicht door zijn eigen omtrek. De belangrijkste
lijnen van je gezicht worden neonbuizen in roze, blauw en geel (de kleur volgt de richting van de lijn),
en hun gloed valt op je gezicht: je ziet jezelf zoals naast een lichtreclame.

glow (0-100): hoeveel licht de buizen op je gezicht werpen.
"""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from ._common import fit, hex_colors, luminance, to_array, to_image

OUTPUT_SIZE = 1400
PINK, BLUE, YELLOW = hex_colors("#ff2d95", "#19d3ff", "#ffe345")


def image_to_neon_edge(image, glow=50):
    glow = glow / 100
    pixels = to_array(fit(image, OUTPUT_SIZE))
    longest = max(pixels.shape)
    lum = luminance(pixels)

    # Alleen de grote lijnen: eerst flink vervagen, dan de randen, en daarvan alleen de sterkste
    smooth = ndimage.gaussian_filter(lum, longest / 260)
    gx, gy = ndimage.sobel(smooth, 1), ndimage.sobel(smooth, 0)
    strength = np.hypot(gx, gy)
    tube = np.clip((strength / np.float32(np.percentile(strength, 99.3)) - 0.28) * 2.2, 0, 1)

    # Dun maken: een buis is de kam van de randsterkte (plaatselijk maximum dwars op de rand)
    ridge = strength >= ndimage.maximum_filter(strength, size=max(3, int(longest / 230))) * 0.86
    tube = blur(tube * ridge, longest / 900)
    tube = np.clip(tube / np.float32(np.percentile(tube, 99.7) + 1e-6), 0, 1) ** 0.8
    del ridge, smooth

    # Kleur van de buis: naar de richting van de rand, rond over roze, blauw en geel. Zo heeft de
    # linkerkant van je gezicht een andere kleur dan de rechterkant, zoals bij een echte lichtreclame.
    # (Vervaagd, zodat één buis niet steeds van kleur verspringt.)
    # (Tussenresultaten worden steeds met del opgeruimd: Render heeft maar 512 MB geheugen.)
    direction_x = blur01(gx / (strength + 1e-6), longest / 60)
    direction_y = blur01(gy / (strength + 1e-6), longest / 60)
    del gx, gy, strength
    turn = (np.arctan2(direction_y, direction_x) / np.float32(2 * np.pi)) % 1 * 3
    del direction_x, direction_y
    palette = np.stack([PINK, BLUE, YELLOW, PINK])
    index = np.minimum(turn.astype(np.int8), 2)
    mix = (turn - index)[..., None]
    del turn
    tubes = palette[index] * (1 - mix)
    tubes += palette[index + 1] * mix
    tubes *= tube[..., None]
    del index, mix

    # Het licht van de buizen: dichtbij fel, verder weg zacht
    near = blur(tubes, longest / 220)
    far = blur(tubes, longest / 45)
    far *= 2 + 7 * glow
    far += near * 2.5                                                  # far is nu het strooilicht (spill)

    # De kamer: de foto zelf, bijna zwart, en alleen zichtbaar waar het neonlicht erop valt
    room = lum[..., None] ** 1.3
    del pixels, lum
    far *= 0.6 + 1.6 * glow
    far += 0.03
    far *= room                                                        # far is nu het licht in de kamer (lit)
    del room

    far += tubes * 2.2
    del tubes
    far += near * 1.2
    del near
    far += np.clip(tube - 0.55, 0, 1)[..., None] * 1.6                 # wit hart van de buis
    np.negative(far, out=far)
    np.exp(far, out=far)
    return to_image(1 - far)


def blur(array, radius):
    """Vervagen met Pillow: veel sneller dan scipy voor grote stralen. Werkt voor 1 of 3 kanalen."""
    image = Image.fromarray((np.clip(array, 0, 1) * 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255


def blur01(array, radius):
    """Vervagen van waarden tussen -1 en 1."""
    return blur((array + 1) / 2, radius) * 2 - 1

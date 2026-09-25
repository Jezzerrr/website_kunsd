import numpy as np
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
from pypalettes import load_cmap


def preview_palette(colors, radius=10, spacing=20, background="white"):
    """Return an image showing one dot for each color."""
    diameter = radius * 2
    width = len(colors) * diameter + (len(colors) + 1) * spacing
    height = diameter + 2 * spacing
    output = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(output)

    for i, color in enumerate(colors):
        cx = spacing + radius + i * (diameter + spacing)
        cy = spacing + radius
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)

    return output


def get_palette(name, n_colors, add_white=False, sort_by_darkness=False):
    try:
        # Try matplotlib first
        cmap = plt.get_cmap(name)

    except ValueError:
        # Fall back to custom colormaps
        cmap = load_cmap(name, cmap_type="continuous")

    colors = [
        tuple(int(x * 255) for x in cmap(x)[:3])
        for x in np.linspace(0, 1, n_colors)
    ]

    if add_white:
        colors.append((255, 255, 255))

    if sort_by_darkness:
        colors = sort_colors_by_darkness(colors)

    return colors


def sort_colors_by_darkness(colors, dark_to_light=True):
    """
    Sort a list of RGB colors by perceived darkness.

    dark_to_light : bool
        True  -> darkest first
        False -> lightest first
    """
    colors_sorted = sorted(
        colors,
        key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2],
        reverse=not dark_to_light
    )

    return colors_sorted

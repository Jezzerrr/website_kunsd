"""Gedeelde hulpjes voor de experimenten in de Proeftuin (verborgen pagina /proeftuin).

Elk experiment staat in een eigen bestand, zodat je het makkelijk naar de echte Speeltuin kunt
verhuizen als het goed bevalt. Alles werkt met float32-arrays tussen 0 en 1 (zuinig met geheugen).
"""
import numpy as np
from PIL import Image


def fit(image, side):
    """Schaalt de foto zodat de langste zijde precies side pixels is."""
    scale = side / max(image.size)

    if abs(scale - 1) < 1e-3:
        return image

    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    method = Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.BICUBIC

    return image.resize(size, method)


def to_array(image):
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255


def to_image(array):
    return Image.fromarray((np.clip(array, 0, 1) * 255 + 0.5).astype(np.uint8))


def luminance(array):
    return array[..., 0] * 0.299 + array[..., 1] * 0.587 + array[..., 2] * 0.114


def stretch(values, low=1, high=99):
    """Rekt de waarden op tot 0-1, met de uitersten (1% aan elke kant) afgekapt."""
    lo, hi = np.percentile(values, [low, high])
    return np.clip((values - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32)


def saturate(array, amount):
    """Maakt de kleuren feller (amount > 1) of grijzer (amount < 1)."""
    grey = luminance(array)[..., None]
    return np.clip(grey + (array - grey) * amount, 0, 1)


def hex_colors(*codes):
    return np.array([[int(code[i:i + 2], 16) / 255 for i in (1, 3, 5)] for code in codes], dtype=np.float32)

"""Bladen als pdf, zonder kwaliteitsverlies.

Pillow slaat een kleurenplaatje in een pdf op als JPEG. Bij foto's merk je dat niet, maar bij dunne
lijntjes, puntjes en letters op wit zie je ingezoomd "wolkjes" van pixels eromheen (JPEG-ruis).
Daarom schrijven we de pdf hier zelf: elk blad zit erin als verliesvrij gecomprimeerd plaatje, met
precies dezelfde compressie als een PNG (dus ook ongeveer even klein als de PNG).

Hoe: we laten Pillow het blad als PNG opslaan en halen de gecomprimeerde beelddata (de IDAT-blokken)
eruit. Een pdf kan die data direct lezen (FlateDecode met "PNG-predictor"), dus er wordt niets
opnieuw gecomprimeerd of omgerekend.
"""

import io
import struct

import numpy as np
from PIL import Image


def pages_to_pdf(pages, dpi=300):
    """Maak van een lijst PIL Images een pdf (bytes), elk plaatje een eigen pagina van dpi punten per inch."""
    objects = []    # inhoud van object 1, 2, 3, ... (bytes)

    def add(content):
        objects.append(content)
        return len(objects)

    catalog = add(b"")      # wordt hieronder ingevuld, als bekend is welke pagina's er zijn
    page_tree = add(b"")
    page_ids = []

    for page in pages:
        data, color_space, colors = _png_data(page)
        width_px, height_px = page.size
        width_pt = width_px / dpi * 72
        height_pt = height_px / dpi * 72

        image = add(
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s /BitsPerComponent 8"
            b" /Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors %d /BitsPerComponent 8 /Columns %d >>"
            b" /Length %d >>\nstream\n" % (width_px, height_px, color_space, colors, width_px, len(data))
            + data + b"\nendstream"
        )
        drawing = b"q %.4f 0 0 %.4f 0 0 cm /Blad Do Q" % (width_pt, height_pt)
        content = add(b"<< /Length %d >>\nstream\n" % len(drawing) + drawing + b"\nendstream")
        page_ids.append(add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.4f %.4f] /Resources << /XObject << /Blad %d 0 R >> >>"
            b" /Contents %d 0 R >>" % (page_tree, width_pt, height_pt, image, content)
        ))

    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % page_tree
    objects[page_tree - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % number for number in page_ids), len(page_ids))

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []

    for number, content in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(b"%d 0 obj\n" % number + content + b"\nendobj\n")

    table = output.tell()
    output.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))

    for offset in offsets:
        output.write(b"%010d 00000 n \n" % offset)

    output.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog, table))

    return output.getvalue()


def _png_data(page):
    """De gecomprimeerde beelddata van het blad als PNG, plus kleurruimte en aantal kleurkanalen.

    Een blad met alleen grijstinten wordt grijs opgeslagen: een derde van de data.
    """
    page = page.convert("RGB")
    pixels = np.asarray(page)

    if np.array_equal(pixels[..., 0], pixels[..., 1]) and np.array_equal(pixels[..., 1], pixels[..., 2]):
        page, color_space, colors = page.convert("L"), b"DeviceGray", 1
    else:
        color_space, colors = b"DeviceRGB", 3

    png = io.BytesIO()
    page.save(png, format="PNG", compress_level=6)
    png = png.getvalue()

    # De PNG bestaat uit blokken: lengte (4 bytes), soort (4 bytes), inhoud, controlegetal (4 bytes)
    data, position = [], 8

    while position < len(png):
        length, kind = struct.unpack(">I4s", png[position:position + 8])

        if kind == b"IDAT":
            data.append(png[position + 8:position + 8 + length])

        position += 12 + length

    return b"".join(data), color_space, colors

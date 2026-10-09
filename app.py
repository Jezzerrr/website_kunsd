import base64
import io
import os
import re

from PIL import Image, ImageOps
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, jsonify

from src.color_page import image_to_color_page, suggest_palette
from src.dotty_affair import image_to_dots, image_to_ranked_dots
from src.shape_division import image_to_shapes
from src.shape_numbers import (
    image_to_numbered_shapes,
    image_to_palette_shapes,
    side_for_equal_area,
    suggest_shape_palette,
)
from src.helper_functions.color_helpers import get_palette

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

app = Flask(__name__)

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# Langste zijde (in pixels) van het resultaat bij Shape division. Houdt het snel en de download klein.
MAX_SHAPE_SIZE = 2000

# Kleine foto's (bijv. een klein stukje uit een grote foto) worden opgeschaald tot minstens dit
# aantal pixels op de langste zijde, zodat het resultaat altijd scherp is.
MIN_IMAGE_SIZE = 1600

# De vormen die de website aanbiedt (shape_division.py kan er meer, maar die tonen we niet)
SHAPE_CHOICES = {"brick", "triangles", "hexagons", "cubes", "octagons_squares", "crosses"}


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/ranked-dots", methods=["POST"])
def ranked_dots():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    try:
        # input_image = Image.open(request.files["image"]).convert("RGB")
        input_image = load_input_image()
        input_image, grid_size = snap_to_dot_grid(input_image, get_grid_size(input_image))
        colors = get_palette(
            "gist_heat",
            3,
            add_white=True,
            sort_by_darkness=True
        )

        result_image = image_to_ranked_dots(
            input_image,
            colors=colors,
            grid_size=grid_size,
            balance=0.5
        )

        return image_to_json(result_image)

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/dots", methods=["POST"])
def dots():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    try:
        # input_image = Image.open(request.files["image"]).convert("RGB")
        input_image = load_input_image()
        input_image, grid_size = snap_to_dot_grid(input_image, get_grid_size(input_image))
        fill = request.form.get("fill", "false").lower() == "true"

        result_image = image_to_dots(
            input_image,
            grid_size=grid_size,
            color=False,
            fill=fill
        )

        return image_to_json(result_image)

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/shape-division", methods=["POST"])
def shape_division():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    shape = request.form.get("shape", "hexagons")

    if shape not in SHAPE_CHOICES:
        return jsonify({"error": "Onbekende vorm"}), 400

    # Eigen kleuren (bijv. "#ff0000,#00aa55"); anders komen de kleuren uit de foto
    colors = read_colors()

    if "colors" in request.form and len(colors) < 2:
        return jsonify({"error": "Kies minstens 2 kleuren."}), 400

    try:
        input_image = limit_size(load_input_image(), MAX_SHAPE_SIZE)

        # De grootte is de zijde van een vierkant (als percentage van de breedte) met dezelfde
        # oppervlakte als één vorm. Zo is elke vorm bij dezelfde instelling even gedetailleerd.
        grid_size_percent = read_number("grid_size_percent", 4, 1.5, 10)
        square_side = input_image.width * grid_size_percent / 100
        grid_size = side_for_equal_area(shape, square_side)

        max_colors = int(read_number("max_colors", 8, 2, 12))
        fill = request.form.get("fill", "true").lower() == "true"

        if not fill:
            # Lege variant: lijntjes, een nummer in elke vorm en een legenda
            result_image = image_to_numbered_shapes(
                input_image,
                grid_size=grid_size,
                max_colors=max_colors,
                shape=shape,
                legend=True,
                colors=colors or None
            )
        elif colors:
            result_image = image_to_palette_shapes(
                input_image,
                grid_size=grid_size,
                shape=shape,
                colors=colors
            )
        else:
            result_image = image_to_shapes(
                input_image,
                grid_size=grid_size,
                max_colors=max_colors,
                shape=shape,
                fill=True
            )

        return image_to_json(result_image)

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/shape-division-palette", methods=["POST"])
def shape_division_palette():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    shape = request.form.get("shape", "hexagons")

    if shape not in SHAPE_CHOICES:
        return jsonify({"error": "Onbekende vorm"}), 400

    try:
        input_image = limit_size(load_input_image(), MAX_SHAPE_SIZE)

        square_side = input_image.width * read_number("grid_size_percent", 4, 1.5, 10) / 100
        grid_size = side_for_equal_area(shape, square_side)
        n_colors = int(read_number("n_colors", 6, 2, 12))

        return jsonify({"colors": suggest_shape_palette(input_image, grid_size, shape, n_colors)})

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/color-page", methods=["POST"])
def color_page():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    try:
        input_image = load_input_image()

        n_colors = int(read_number("n_colors", 6, 2, 12))
        smoothness = read_number("smoothness", 1, 0, 5)
        min_region_size = read_number("min_region_size", 0.1, 0.05, 1)
        detail = read_number("detail", 0.6, 0, 1)

        # Eigen kleuren (bijv. "#ff0000,#00aa55"); anders bepaalt het algoritme ze zelf
        colors = read_colors()

        if "colors" in request.form and len(colors) < 2:
            return jsonify({"error": "Kies minstens 2 kleuren."}), 400

        fill = request.form.get("fill", "true").lower() == "true"

        result_image = image_to_color_page(
            input_image,
            n_colors=n_colors,
            colors=colors or None,
            smoothness=smoothness,
            min_region_size=min_region_size,
            detail=detail,
            fill=fill,
            legend=not fill
        )

        return image_to_json(result_image)

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/color-page-palette", methods=["POST"])
def color_page_palette():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    try:
        input_image = load_input_image()
        n_colors = int(read_number("n_colors", 6, 2, 12))

        return jsonify({"colors": suggest_palette(input_image, n_colors)})

    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(".", filename)


def load_input_image():
    image = Image.open(request.files["image"])

    # Draai de foto zoals de browser hem toont (telefoonfoto's hebben vaak
    # een rotatie-tag). Zo kloppen de coördinaten van de uitsnede.
    image = ImageOps.exif_transpose(image)

    return ensure_min_size(apply_crop(image.convert("RGB")), MIN_IMAGE_SIZE)


def ensure_min_size(image, min_side):
    """Schaalt een kleine foto op, zodat de langste zijde minstens min_side pixels is.

    De algoritmes tekenen hun resultaat op de grootte van de foto. Bij een klein plaatje zijn
    de stippen en lijntjes dan grof en hoekig. Eerst opschalen geeft een gladde, scherpe uitvoer.
    """
    longest = max(image.size)

    if longest >= min_side:
        return image

    scale = min_side / longest
    new_size = (round(image.width * scale), round(image.height * scale))

    return image.resize(new_size, Image.Resampling.BICUBIC)


def limit_size(image, max_side):
    """Verkleint de foto zodat de langste zijde hoogstens max_side pixels is."""
    longest = max(image.size)

    if longest <= max_side:
        return image

    scale = max_side / longest
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))

    return image.resize(new_size, Image.Resampling.LANCZOS)


def apply_crop(image):
    """Snijdt de foto bij als de browser een uitsnede heeft meegestuurd.

    De uitsnede komt binnen als fracties van de foto (0 t/m 1):
    crop_x en crop_y zijn de linkerbovenhoek, crop_w en crop_h de afmetingen.
    """
    if "crop_x" not in request.form:
        return image

    try:
        x = float(request.form["crop_x"])
        y = float(request.form["crop_y"])
        w = float(request.form["crop_w"])
        h = float(request.form["crop_h"])
    except (KeyError, ValueError):
        return image

    left = max(0, min(image.width - 1, round(x * image.width)))
    top = max(0, min(image.height - 1, round(y * image.height)))
    right = max(left + 1, min(image.width, round((x + w) * image.width)))
    bottom = max(top + 1, min(image.height, round((y + h) * image.height)))

    return image.crop((left, top, right, bottom))


def read_colors():
    """Leest de gekozen kleuren ("#rrggbb", gescheiden door komma's); onbruikbare delen worden genegeerd."""
    parts = request.form.get("colors", "").split(",")
    colors = [part.strip() for part in parts if HEX_COLOR.fullmatch(part.strip())]

    return colors[:12]


def read_number(name, default, minimum, maximum):
    """Leest een getal uit het formulier en houdt het binnen de grenzen."""
    try:
        value = float(request.form.get(name, default))
    except ValueError:
        value = default

    return max(minimum, min(maximum, value))


def snap_to_dot_grid(image, grid_size):
    """Maakt van de foto een rooster van precies gelijke hokjes, voor de stippen-algoritmes.

    De algoritmes verdelen de foto in hokjes en zetten in elk hokje een stip. Als de foto
    niet precies een heel aantal hokjes breed of hoog is, krijgen de hokjes verschillende
    afmetingen van hele pixels (bijv. 16 pixels, en ergens één rij van 15). Waar twee rijen
    stippen 1 pixel dichter bij elkaar liggen, zie je een dunne streep door het plaatje.

    Daarom: hokjes van een heel aantal pixels, en de foto net zo veel uitgerekt of ingekrompen
    (hoogstens een halve hokjesbreedte) dat er precies een heel aantal hokjes in past.
    """
    cell = max(2, round(grid_size))
    columns = max(1, round(image.width / cell))
    rows = max(1, round(image.height / cell))

    size = (columns * cell, rows * cell)

    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)

    return image, cell


def get_grid_size(input_image):
    grid_size_percent = float(request.form.get("grid_size_percent", 3))
    grid_size_percent = max(0.5, min(5, grid_size_percent))
    return input_image.width * grid_size_percent / 100


def image_to_json(image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    image_base64 = base64.b64encode(output.read()).decode("utf-8")

    return jsonify({
        "image": f"data:image/png;base64,{image_base64}"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )

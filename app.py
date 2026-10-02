import base64
import io
import os

from PIL import Image, ImageOps
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, jsonify

from src.dotty_affair import image_to_dots, image_to_ranked_dots
from src.helper_functions.color_helpers import get_palette

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

app = Flask(__name__)


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
        grid_size = get_grid_size(input_image)
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
        grid_size = get_grid_size(input_image)
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


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(".", filename)


def load_input_image():
    image = Image.open(request.files["image"])

    # Draai de foto zoals de browser hem toont (telefoonfoto's hebben vaak
    # een rotatie-tag). Zo kloppen de coördinaten van de uitsnede.
    image = ImageOps.exif_transpose(image)

    return apply_crop(image.convert("RGB"))


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

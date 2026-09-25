import os
import io
import base64

from flask import Flask, request, send_from_directory, jsonify
from PIL import Image

from src.dotty_affair import image_to_ranked_dots
from src.helper_functions.color_helpers import get_palette


app = Flask(__name__)


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(".", filename)


@app.route("/api/ranked-dots", methods=["POST"])
def ranked_dots():

    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen"}), 400

    file = request.files["image"]

    try:
        input_image = Image.open(file).convert("RGB")

        # Percentage van de afbeeldingsbreedte
        grid_size_percent = float(request.form.get("grid_size_percent", 3))

        # Beperk de waarde tot 0.5% - 5%
        grid_size_percent = max(
            0.5,
            min(5, grid_size_percent)
        )

        # Bereken de daadwerkelijke grid size in pixels
        grid_size = input_image.width * grid_size_percent / 100

        # Kleurenpalet
        colors = get_palette(
            "gist_heat",
            3,
            add_white=True,
            sort_by_darkness=True
        )

        # Maak de dot-afbeelding
        color_image = image_to_ranked_dots(
            input_image,
            colors=colors,
            grid_size=grid_size,
            balance=0.5
        )

        # Zet het resultaat om naar PNG
        output = io.BytesIO()

        color_image.save(output, format="PNG")

        output.seek(0)

        image_base64 = base64.b64encode(output.read()).decode("utf-8")

        return jsonify({
            "image": f"data:image/png;base64,{image_base64}"
        })

    except Exception as error:
        return jsonify({"error": str(error)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )

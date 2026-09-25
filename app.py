import os
import io
import base64

from flask import Flask, request, send_from_directory, jsonify
from PIL import Image


app = Flask(__name__)


# ========================================
# Website-bestanden
# ========================================

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(".", filename)


# ========================================
# Python-afbeeldingsbewerking
# ========================================

@app.route("/api/python-bewerking", methods=["POST"])
def python_bewerking():

    # Controleer of er een afbeelding is meegestuurd
    if "image" not in request.files:
        return jsonify({
            "error": "Geen afbeelding ontvangen"
        }), 400


    file = request.files["image"]


    try:

        # Open de afbeelding
        image = Image.open(file)

        # --------------------------------
        # Python-bewerking
        # --------------------------------

        # Voorlopig maken we hem grijswaarden.
        # Hier kunnen we later jouw eigen
        # kunst-algoritmes neerzetten.

        result = image.convert("L")

        # --------------------------------
        # Resultaat opslaan in geheugen
        # --------------------------------

        output = io.BytesIO()

        result.save(
            output,
            format="PNG"
        )

        output.seek(0)

        # --------------------------------
        # Omzetten naar base64
        # --------------------------------

        image_base64 = base64.b64encode(
            output.read()
        ).decode("utf-8")


        return jsonify({
            "image": f"data:image/png;base64,{image_base64}"
        })

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500


# ========================================
# Start server
# ========================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )

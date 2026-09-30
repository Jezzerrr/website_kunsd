import base64
import io
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from PIL import Image
from flask import Flask, request, send_from_directory, jsonify
from texts.email_templates import make_contact_email

from src.dotty_affair import image_to_dots, image_to_ranked_dots
from src.helper_functions.color_helpers import get_palette

from dotenv import load_dotenv

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
        input_image = Image.open(request.files["image"]).convert("RGB")
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
        input_image = Image.open(request.files["image"]).convert("RGB")
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


@app.route("/contact", methods=["POST"])
def contact():
    subject = request.form["subject"]
    sender_email = request.form["email"]
    message = request.form["message"]

    email_message = MIMEMultipart()

    email_message["Subject"] = f"[Kunsd Website] {subject}"
    email_message["From"] = GMAIL_ADDRESS
    email_message["To"] = GMAIL_ADDRESS

    email_message.attach(
        MIMEText(make_contact_email(subject, sender_email, message), "plain")
    )

    try:
        print("1")
        with smtplib.SMTP("smtp.gmail.com",587) as server:
            server.starttls()
            print("2")

            server.ehlo()

            print("3")

            server.starttls()

            print("4")

            server.ehlo()

            print("5")

            server.login(
                GMAIL_ADDRESS,
                GMAIL_APP_PASSWORD
            )

            print("6")

            server.send_message(email_message)

            print("7")

        return """
            <h1>Bedankt!</h1>
            <p>Je bericht is verzonden.</p>
            <a href="index.html">Terug naar home</a>
        """
    except Exception as error:
        print(error)
        return str(error)


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

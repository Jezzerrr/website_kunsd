import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from functools import wraps
from html import escape
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFilter, ImageOps, UnidentifiedImageError
from flask import Flask, abort, jsonify, redirect, request, send_from_directory

from src.dotty_affair import image_to_dots, image_to_ranked_dots
from src.helper_functions.color_helpers import get_palette
from src.shape_division import image_to_shapes
from src.shape_numbers import (
    image_to_numbered_shapes,
    image_to_palette_shapes,
    side_for_equal_area,
    suggest_shape_palette,
)
from src.chordinates import image_to_chordinates
from src.hatchwork import image_to_hatchwork
from src.penpath import image_to_penpath
from src.negative_circles import image_to_negative_circles
from src.square_drift import image_to_square_drift

app = Flask(__name__)


def load_env_file(path):
    """Lokaal testen: zet de regels NAAM=waarde uit .env in de omgeving.

    Op Render staan deze waarden in de instellingen (Environment) en is er geen .env.
    Wat al in de omgeving staat, wordt niet overschreven.
    """
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_env_file(Path(app.root_path) / ".env")

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# Foto's worden opgeschaald tot minstens MIN_IMAGE_SIZE pixels op de langste zijde (een klein
# stukje uit een grote foto geeft anders een grof resultaat) en verkleind tot hoogstens
# MAX_IMAGE_SIZE (houdt het snel en het geheugen van de server beperkt).
MIN_IMAGE_SIZE = 1600
MAX_IMAGE_SIZE = 3000

# Langste zijde van het resultaat bij de stippen (Coloring Dots en RedBlack Dots). Stippen tekenen
# kost bijna niets, dus we maken ze groot: scherp bij printen (A4 ongeveer 300 dpi).
DOT_IMAGE_SIZE = 3600

# Uitknippen: hoogstens zoveel punten in de getekende vorm, en de zachte rand
# als fractie van de langste zijde (0.0015 is 3 pixels bij 2000 pixels).
MAX_CUT_POINTS = 2000
CUT_FEATHER = 0.0015

# Draaien en spiegelen: JPEG-kwaliteit van de teruggestuurde foto (hoog, want hij wordt daarna nog bewerkt).
ORIENT_JPEG_QUALITY = 95

# Langste zijde van het resultaat bij Shape Division: houdt het snel en de download klein.
MAX_SHAPE_SIZE = 2000

# De vormen die de website aanbiedt (shape_division.py kan er meer, maar die tonen we niet)
SHAPE_CHOICES = {"brick", "triangles", "hexagons", "cubes", "octagons_squares", "crosses"}

# Wat de server als bestand mag uitleveren. Alles anders (app.py, src/, .env, .git, ...) niet.
STATIC_FOLDERS = {"css", "js", "mijn_kunsd"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
STATIC_EXTENSIONS = IMAGE_EXTENSIONS | {".css", ".js", ".ico"}

# De pagina's met een net adres: /mijn_kunst toont mijn_kunst.html. De homepagina (index.html) staat op /.
PAGES = {"mijn_kunst", "jouw_kunst", "speeltuin", "muziek", "contact", "bedankt"}

# Verhuisde pagina's: oud adres -> nieuw adres. "Over mij" en "Kunsd" zijn samen "Mijn Kunsd" geworden.
MOVED_PAGES = {"over-mij": "mijn_kunst", "kunst": "mijn_kunst"}

# De map met foto's voor de diavoorstelling op "Mijn Kunsd"
SLIDE_SHOW_FOLDER = "mijn_kunsd/slide_show"

# Contactformulier met foto's of pdf's (zonder bijlage gaat het via Web3Forms, zie contact.html).
# De mail gaat via Resend (resend.com), want het Render free plan blokkeert gewone e-mail (SMTP).
# Nodig in de omgeving (Render: Environment; lokaal: .env):
#   RESEND_API_KEY  de sleutel van je Resend-account
#   CONTACT_EMAIL   waar de mail heen gaat: het e-mailadres van je Resend-account
RESEND_URL = "https://api.resend.com/emails"
CONTACT_FROM = "KUNSD Website <onboarding@resend.dev>"     # afzender die Resend zonder eigen domein toestaat
CONTACT_MAX_IMAGES = 3              # bijlagen (foto's en pdf's samen); gelijk houden met MAX_IMAGES in js/contact.js
CONTACT_MAX_FILE_MB = 15            # gelijk houden met MAX_FILE_MB in js/contact.js
CONTACT_MAX_PDF_MB = 8              # pdf's gaan onverkleind mee; Resend staat in totaal 40 MB per mail toe (na base64)
CONTACT_IMAGE_SIZE = 2000           # foto's worden verkleind tot hoogstens zoveel pixels: kleine mail
CONTACT_MAX_PER_HOUR = 10           # spamrem: zoveel berichten per uur per bezoeker
EMAIL_ADDRESS = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# Wanneer elke bezoeker (IP-adres) iets verstuurde, voor de spamrem. Leeg na een herstart; dat is goed genoeg.
contact_log = {}


# ---------------------------------------------------------------------------
# Pagina's en bestanden
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def serve_file(filename):
    path = PurePosixPath(filename)
    parts = path.parts
    suffix = path.suffix.lower()
    name = str(path).lower()

    # Een pagina met een net adres, zoals /kunst
    if filename in PAGES:
        return send_from_directory(".", f"{filename}.html")

    # Bijna goede adressen doorsturen naar het nette adres: /Contact, /contact.html en /index.
    # Oude adressen van verhuisde pagina's (/over-mij, /kunst.html, ...) naar hun nieuwe adres.
    # Code 301 betekent "permanent verhuisd": browsers, Google en oude gedeelde links gaan zo
    # vanzelf goed.
    stem = name.removesuffix(".html")
    if stem in MOVED_PAGES:
        return redirect(f"/{MOVED_PAGES[stem]}", code=301)
    if stem in PAGES:
        return redirect(f"/{stem}", code=301)
    if stem == "index":
        return redirect("/", code=301)

    # Bestanden: favicon.ico en alles in css/, js/ en mijn_kunsd/ met een toegestane extensie.
    # Bestaat zo'n bestand niet, dan geeft send_from_directory een 404.
    is_hidden = any(part.startswith(".") for part in parts)
    is_icon = name == "favicon.ico"
    is_asset = len(parts) > 1 and parts[0] in STATIC_FOLDERS and suffix in STATIC_EXTENSIONS

    if is_icon or (is_asset and not is_hidden):
        return send_from_directory(".", filename)

    # Een ontbrekend plaatje of script blijft een 404 (een doorverwijzing naar de homepagina
    # zou daar een html-pagina teruggeven in plaats van een plaatje).
    if parts and parts[0] in STATIC_FOLDERS:
        abort(404)

    # Al het andere (bijv. een verkeerd getypt adres): naar de homepagina. Code 302 betekent
    # "tijdelijk": zoekmachines onthouden die doorverwijzing niet als het echte adres.
    return redirect("/", code=302)


@app.route("/api/slide-show")
def slide_show():
    """De foto's in de map slide_show. Een nieuwe foto in die map verschijnt vanzelf op de site."""
    folder = Path(app.root_path) / SLIDE_SHOW_FOLDER

    if not folder.is_dir():
        return jsonify([])

    names = sorted(
        path.name for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    return jsonify([f"{SLIDE_SHOW_FOLDER}/{name}" for name in names])


@app.route("/api/wakker")
def wakker():
    """Een licht adres voor cron-job.org: elke paar minuten even aankloppen houdt de site op
    Render wakker (anders valt hij na 15 minuten in slaap en duurt het openen lang).
    no-store: niet bewaren in een cache, zodat elk verzoek echt de server bereikt."""
    response = jsonify(status="ok")
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Contactformulier met foto's
# ---------------------------------------------------------------------------

@app.route("/api/contact", methods=["POST"])
def contact():
    form = request.form

    # Het onzichtbare vinkje is aangevinkt: een bot. Doe alsof het gelukt is.
    if form.get("botcheck"):
        return jsonify({"ok": True})

    api_key = os.environ.get("RESEND_API_KEY")
    to_address = os.environ.get("CONTACT_EMAIL")

    if not api_key or not to_address:
        app.logger.error("Contactformulier: RESEND_API_KEY of CONTACT_EMAIL ontbreekt")
        return jsonify({"error": "Bijlagen meesturen lukt nu even niet. Stuur je bericht zonder bijlage, "
                                 "of probeer het later nog eens."}), 503

    name = form.get("name", "").strip()[:100]
    email = form.get("email", "").strip()[:200]
    subject = form.get("onderwerp", "").strip()[:150]
    message = form.get("message", "").strip()[:10000]

    if not EMAIL_ADDRESS.fullmatch(email):
        return jsonify({"error": "Vul een geldig e-mailadres in."}), 400

    if not subject or not message:
        return jsonify({"error": "Vul een onderwerp en een bericht in."}), 400

    if too_many_messages():
        return jsonify({"error": "Je hebt net al een paar berichten gestuurd. Probeer het later nog eens."}), 429

    try:
        attachments = read_contact_images()
    except UserError as error:
        return jsonify({"error": str(error)}), 400

    text = (
        f"Naam: {name or '(niet ingevuld)'}\n"
        f"E-mail: {email}\n"
        f"Onderwerp: {subject}\n"
        f"Bijlagen: {len(attachments)}\n\n"
        f"{message}\n"
    )

    try:
        send_email(api_key, {
            "from": CONTACT_FROM,
            "to": [to_address],
            "reply_to": email,
            "subject": f"[Kunsd Website] {subject} (met bijlage)",
            "text": text,
            "html": contact_email_html(name, email, subject, message, attachments),
            "attachments": attachments,
        })
    except urllib.error.URLError as error:
        detail = error.read().decode("utf-8", "replace") if isinstance(error, urllib.error.HTTPError) else error
        app.logger.error("Contactformulier: versturen via Resend mislukt: %s", detail)
        return jsonify({"error": "Versturen is niet gelukt. Probeer het nog eens, of stuur je bericht zonder bijlage."}), 502

    return jsonify({"ok": True})


def contact_email_html(name, email, subject, message, attachments):
    """De opgemaakte mail: een wit kaartje met de velden onder elkaar en de foto's erin (pdf's alleen als bijlage).

    Mailprogramma's ondersteunen weinig CSS, daarom staat alle opmaak per element (style="...").
    """
    def field(label, value_html):
        return (
            f'<p style="margin:0 0 4px;color:#3b3fd8;font-weight:bold;font-size:14px;">{label}</p>'
            f'<p style="margin:0 0 22px;font-size:16px;line-height:1.5;">{value_html}</p>'
        )

    photos = "".join(
        f'<img src="cid:{attachment["content_id"]}" alt="Foto {number}" width="480" '
        f'style="display:block;width:100%;max-width:480px;height:auto;margin:0 0 12px;'
        f'border:1px solid #dddddd;border-radius:8px;">'
        for number, attachment in enumerate(
            [attachment for attachment in attachments if "content_id" in attachment], start=1
        )
    )

    pdfs = "".join(
        f'<p style="margin:0 0 8px;font-size:15px;">&#128196; {escape(attachment["filename"])} (zie bijlage)</p>'
        for attachment in attachments
        if attachment["content_type"] == "application/pdf"
    )

    return f"""\
<div style="margin:0;padding:32px 12px;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;color:#171717;">
  <div style="max-width:560px;margin:0 auto;padding:28px;background:#ffffff;border:1px solid #e3e3e3;border-radius:10px;">
    <p style="margin:0 0 6px;font-size:16px;">Hallo Jesse,</p>
    <p style="margin:0 0 26px;font-size:16px;">Er is een nieuw bericht verstuurd via je website, met bijlage. Hieronder de details.</p>
    {field("Naam", escape(name) or "(niet ingevuld)")}
    {field("E-mail", f'<a href="mailto:{escape(email)}" style="color:#1a56db;">{escape(email)}</a>')}
    {field("Onderwerp", escape(subject))}
    {field("Bericht", escape(message).replace(chr(10), "<br>"))}
    <p style="margin:0 0 10px;color:#3b3fd8;font-weight:bold;font-size:14px;">Bijlagen ({len(attachments)})</p>
    {pdfs}
    {photos}
    <p style="margin:24px 0 0;color:#888888;font-size:13px;">Antwoorden kan direct: je antwoord gaat naar de afzender.</p>
  </div>
</div>"""


def too_many_messages():
    """Eenvoudige spamrem: hoogstens CONTACT_MAX_PER_HOUR berichten per uur per IP-adres."""
    # Render zet het echte adres van de bezoeker vooraan in X-Forwarded-For
    visitor = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    now = time.time()
    recent = [moment for moment in contact_log.get(visitor, []) if now - moment < 3600]

    if len(recent) >= CONTACT_MAX_PER_HOUR:
        return True

    contact_log[visitor] = recent + [now]
    return False


def read_contact_images():
    """De meegestuurde bijlagen voor Resend, in base64: foto's verkleind tot JPEG, pdf's zoals ze zijn."""
    files = [file for file in request.files.getlist("images") if file.filename]

    if len(files) > CONTACT_MAX_IMAGES:
        raise UserError(f"Je kunt maximaal {CONTACT_MAX_IMAGES} bestanden meesturen.")

    attachments = []

    for number, file in enumerate(files, start=1):
        data = file.read()

        # Een pdf herken je aan de eerste bytes; de naam en het type van de browser zijn niet te vertrouwen.
        if data.startswith(b"%PDF-"):
            if len(data) > CONTACT_MAX_PDF_MB * 1024 * 1024:
                raise UserError(f"Een pdf is groter dan {CONTACT_MAX_PDF_MB} MB. Kies een kleinere pdf.")

            attachments.append({
                "filename": f"kunsd-bijlage-{number}.pdf",
                "content": base64.b64encode(data).decode("ascii"),
                "content_type": "application/pdf",
            })
            continue

        if len(data) > CONTACT_MAX_FILE_MB * 1024 * 1024:
            raise UserError(f"Een foto is groter dan {CONTACT_MAX_FILE_MB} MB. Kies een kleinere foto.")

        try:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise UserError(f"\"{file.filename}\" kan ik niet openen als foto of pdf.")

        output = io.BytesIO()
        limit_size(image, CONTACT_IMAGE_SIZE).save(output, format="JPEG", quality=88)

        # content_id: zo staat de foto ook in de mail zelf (zie contact_email_html)
        attachments.append({
            "filename": f"kunsd-foto-{number}.jpg",
            "content": base64.b64encode(output.getvalue()).decode("ascii"),
            "content_type": "image/jpeg",
            "content_id": f"kunsd-foto-{number}",
        })

    return attachments


def send_email(api_key, payload):
    """Verstuurt een mail via Resend (een gewoon HTTPS-verzoek; dat mag wel op het Render free plan)."""
    email_request = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "kunsd-website",
        },
        method="POST",
    )

    with urllib.request.urlopen(email_request, timeout=30):
        pass


# ---------------------------------------------------------------------------
# De algoritmes
# ---------------------------------------------------------------------------

class UserError(Exception):
    """Een fout door wat de bezoeker heeft ingevuld; de tekst wordt aan hem getoond."""


def image_endpoint(function):
    """Gemeenschappelijk voor alle routes die een foto bewerken: controle op de foto en foutafhandeling."""

    @wraps(function)
    def wrapper():
        if "image" not in request.files:
            return jsonify({"error": "Geen afbeelding ontvangen"}), 400

        try:
            return function()
        except UserError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return jsonify({"error": str(error)}), 500

    return wrapper


@app.route("/api/ranked-dots", methods=["POST"])
@image_endpoint
def ranked_dots():
    input_image, grid_size = snap_to_dot_grid(load_dot_image())
    colors = get_palette("gist_heat", 3, add_white=True, sort_by_darkness=True)

    return image_to_json(image_to_ranked_dots(
        input_image,
        colors=colors,
        grid_size=grid_size,
        balance=0.5
    ))


@app.route("/api/dots", methods=["POST"])
@image_endpoint
def dots():
    input_image, grid_size = snap_to_dot_grid(load_dot_image())

    return image_to_json(image_to_dots(
        input_image,
        grid_size=grid_size,
        color=False,
        fill=read_flag("fill", default=False),
        # Omtrekjes even dik als vroeger op 1600 pixels (1 pixel), anders worden ze te dun bij printen
        outline_width=max(1, round(max(input_image.size) / MIN_IMAGE_SIZE))
    ))


@app.route("/api/shape-division", methods=["POST"])
@image_endpoint
def shape_division():
    shape = read_shape()
    colors = read_custom_colors()
    input_image = limit_size(load_input_image(), MAX_SHAPE_SIZE)
    grid_size = shape_grid_size(input_image, shape)
    max_colors = int(read_number("max_colors", 8, 2, 12))

    if not read_flag("fill", default=True):
        # Lege variant: lijntjes, een nummer in elke vorm en een legenda
        result = image_to_numbered_shapes(
            input_image,
            grid_size=grid_size,
            max_colors=max_colors,
            shape=shape,
            legend=True,
            colors=colors or None
        )
    elif colors:
        result = image_to_palette_shapes(input_image, grid_size=grid_size, shape=shape, colors=colors)
    else:
        result = image_to_shapes(
            input_image,
            grid_size=grid_size,
            max_colors=max_colors,
            shape=shape,
            fill=True
        )

    return image_to_json(result)


@app.route("/api/shape-division-palette", methods=["POST"])
@image_endpoint
def shape_division_palette():
    shape = read_shape()
    input_image = limit_size(load_input_image(), MAX_SHAPE_SIZE)
    n_colors = int(read_number("n_colors", 6, 2, 12))

    return jsonify({
        "colors": suggest_shape_palette(input_image, shape_grid_size(input_image, shape), shape, n_colors)
    })


@app.route("/api/chordinates", methods=["POST"])
@image_endpoint
def chordinates():
    # Zonder "fill" krijg je het tekenvel: twee A4-bladen (de cirkel, en de lijst met lijnen)
    template = not read_flag("fill", default=True)
    result = image_to_chordinates(
        load_input_image(),
        n_lines=int(read_number("n_lines", 600, 250, 800)),
        template=template
    )

    return pages_to_json(result) if template else image_to_json(result)


@app.route("/api/penpath", methods=["POST"])
@image_endpoint
def penpath():
    # Zonder "fill" krijg je het tekenvel: twee A4-bladen (het puntenraster, en de routes)
    template = not read_flag("fill", default=True)
    result = image_to_penpath(
        load_input_image(),
        n_lines=int(read_number("n_lines", 800, 400, 1000)),
        template=template
    )

    return pages_to_json(result) if template else image_to_json(result)


@app.route("/api/hatchwork", methods=["POST"])
@image_endpoint
def hatchwork():
    # Zonder "fill" krijg je het tekenvel: twee A4-bladen (het ruitjesraster, en de lijst per ronde)
    template = not read_flag("fill", default=True)
    result = image_to_hatchwork(
        load_input_image(),
        columns=int(read_number("columns", 70, 50, 110)),
        template=template
    )

    return pages_to_json(result) if template else image_to_json(result)


@app.route("/api/negative-circles", methods=["POST"])
@image_endpoint
def negative_circles():
    # Speeltuin: vol cirkels, ertussen het negatief, en het geheel als rondje (PNG, doorzichtig erbuiten).
    # Het rondje is het grootste vierkant in het midden van de uitsnede ("Kies Het Rondje" stuurt een vierkant mee).
    return image_to_json(image_to_negative_circles(
        load_input_image(),
        circles_across=int(read_number("circles", 11, 3, 20)),
        gray=read_flag("gray", default=False)
    ))


@app.route("/api/square-drift", methods=["POST"])
@image_endpoint
def square_drift():
    # Speeltuin: rechthoekjes die van het midden naar buiten verschoven zijn. Elke keer anders (toeval).
    # Een foto vol kleurverloop: als JPEG veel kleiner dan als PNG.
    return photo_to_json(image_to_square_drift(
        load_input_image(),
        strength=read_number("strength", 60, 20, 100) / 100
    ))


@app.route("/api/orient", methods=["POST"])
@image_endpoint
def orient():
    """De knoppen "Draaien" en "Spiegelen" op Jouw Kunsd: geeft de foto gedraaid en/of gespiegeld terug.

    Eerst spiegelen (flip, links-rechts), dan rotate graden rechtsom (0, 90, 180 of 270). De browser
    gebruikt het resultaat daarna als de foto, dus de uitsnede en alle bewerkingen gaan vanzelf mee.
    Dit gebeurt hier en niet in de browser, omdat sommige browsers een canvas bewust verstoren.
    """
    image = ImageOps.exif_transpose(Image.open(request.files["image"])).convert("RGB")

    if read_flag("flip", default=False):
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    rotate = int(read_number("rotate", 0, 0, 270)) // 90 * 90

    if rotate:
        # Pillow draait linksom: 270 graden linksom is 90 graden rechtsom
        image = image.transpose({
            90: Image.Transpose.ROTATE_270,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }[rotate])

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=ORIENT_JPEG_QUALITY)

    return jsonify({"image": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")})


# ---------------------------------------------------------------------------
# De foto en de instellingen inlezen
# ---------------------------------------------------------------------------

def load_input_image():
    """De geüploade foto, bijgesneden als de bezoeker dat wilde, en op een bruikbare grootte gebracht."""
    image = Image.open(request.files["image"])

    # Draai de foto zoals de browser hem toont (telefoonfoto's hebben vaak
    # een rotatie-tag). Zo kloppen de coördinaten van de uitsnede.
    image = ImageOps.exif_transpose(image).convert("RGB")

    original_size = image.size
    box = read_crop_box(original_size)

    if box:
        image = image.crop(box)
    else:
        box = (0, 0) + original_size

    image = ensure_min_size(limit_size(image, MAX_IMAGE_SIZE), MIN_IMAGE_SIZE)

    # Uitgeknipt? Dan wordt alles buiten de getekende vorm wit. Pas na het schalen,
    # zodat het masker niet groter is dan nodig en de rand scherp blijft.
    return apply_cutout(image, original_size, box)


def load_dot_image():
    """De foto voor de stippen: altijd DOT_IMAGE_SIZE pixels op de langste zijde."""
    return limit_size(ensure_min_size(load_input_image(), DOT_IMAGE_SIZE), DOT_IMAGE_SIZE)


def read_crop_box(size):
    """De uitsnede die de browser heeft meegestuurd, als (left, top, right, bottom) in pixels, of None.

    De uitsnede komt binnen als fracties van de foto (0 t/m 1):
    crop_x en crop_y zijn de linkerbovenhoek, crop_w en crop_h de afmetingen.
    """
    if "crop_x" not in request.form:
        return None

    try:
        x, y, w, h = (float(request.form[name]) for name in ("crop_x", "crop_y", "crop_w", "crop_h"))
    except (KeyError, ValueError):
        return None

    width, height = size
    left = max(0, min(width - 1, round(x * width)))
    top = max(0, min(height - 1, round(y * height)))
    right = max(left + 1, min(width, round((x + w) * width)))
    bottom = max(top + 1, min(height, round((y + h) * height)))

    return left, top, right, bottom


def apply_cutout(image, original_size, box):
    """Maakt alles buiten de uitgeknipte vorm wit (de knop "Uitknippen" op Jouw Kunsd).

    De vorm komt binnen als cut_shape: een JSON-lijst met punten [x, y], als fracties van de
    originele foto. box is de uitsnede in pixels van het origineel; image is die uitsnede,
    eventueel geschaald. De rand wordt een heel klein beetje zacht gemaakt, zodat er geen
    trapjes in komen.
    """
    try:
        points = json.loads(request.form.get("cut_shape", "null"))
    except ValueError:
        return image

    if not isinstance(points, list) or not 3 <= len(points) <= MAX_CUT_POINTS:
        return image

    left, top, right, bottom = box
    scale_x = image.width / (right - left)
    scale_y = image.height / (bottom - top)

    try:
        polygon = [
            ((float(x) * original_size[0] - left) * scale_x, (float(y) * original_size[1] - top) * scale_y)
            for x, y in points
        ]
    except (TypeError, ValueError):
        return image

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)

    feather = max(1.0, max(image.size) * CUT_FEATHER)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))

    white = Image.new("RGB", image.size, (255, 255, 255))
    return Image.composite(image, white, mask)


def ensure_min_size(image, min_side):
    """Schaalt een kleine foto op, zodat de langste zijde minstens min_side pixels is.

    De algoritmes tekenen hun resultaat op de grootte van de foto. Bij een klein plaatje zijn
    de stippen en lijntjes dan grof en hoekig. Eerst opschalen geeft een gladde, scherpe uitvoer.
    """
    longest = max(image.size)

    if longest >= min_side:
        return image

    scale = min_side / longest

    return image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.BICUBIC
    )


def limit_size(image, max_side):
    """Verkleint de foto zodat de langste zijde hoogstens max_side pixels is."""
    longest = max(image.size)

    if longest <= max_side:
        return image

    scale = max_side / longest

    return image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS
    )


def read_number(name, default, minimum, maximum):
    """Leest een getal uit het formulier en houdt het binnen de grenzen."""
    try:
        value = float(request.form.get(name, default))
    except ValueError:
        value = default

    return max(minimum, min(maximum, value))


def read_flag(name, default):
    """Leest een ja/nee-keuze ("true" of "false") uit het formulier."""
    return request.form.get(name, str(default)).lower() == "true"


def read_shape():
    shape = request.form.get("shape", "hexagons")

    if shape not in SHAPE_CHOICES:
        raise UserError("Onbekende vorm")

    return shape


def read_custom_colors():
    """Eigen kleuren ("#rrggbb", gescheiden door komma's); een lege lijst als de bezoeker er geen koos.

    Onbruikbare delen worden genegeerd. Wie kleuren meestuurt moet er minstens 2 hebben.
    """
    parts = request.form.get("colors", "").split(",")
    colors = [part.strip() for part in parts if HEX_COLOR.fullmatch(part.strip())][:12]

    if "colors" in request.form and len(colors) < 2:
        raise UserError("Kies minstens 2 kleuren.")

    return colors


def shape_grid_size(image, shape):
    """De zijde van een vorm bij Shape Division.

    De slider geeft de oppervlakte van één vorm: die van een vierkant waarvan de zijde dit
    percentage van de breedte is. Zo is elke vorm bij dezelfde instelling even gedetailleerd.
    """
    percent = read_number("grid_size_percent", 4, 1.5, 10)

    return side_for_equal_area(shape, image.width * percent / 100)


def snap_to_dot_grid(image):
    """Maakt van de foto een rooster van precies gelijke hokjes, voor de stippen-algoritmes.

    De algoritmes verdelen de foto in hokjes en zetten in elk hokje een stip. Als de foto
    niet precies een heel aantal hokjes breed of hoog is, krijgen de hokjes verschillende
    afmetingen van hele pixels (bijv. 16 pixels, en ergens één rij van 15). Waar twee rijen
    stippen 1 pixel dichter bij elkaar liggen, zie je een dunne streep door het plaatje.

    Daarom: hokjes van een heel aantal pixels, en de foto net zo veel uitgerekt of ingekrompen
    (hoogstens een halve hokjesbreedte) dat er precies een heel aantal hokjes in past.

    Geeft de bijgestelde foto en de hokjesgrootte (in pixels) terug.
    """
    percent = read_number("grid_size_percent", 3, 0.5, 5)
    cell = max(2, round(image.width * percent / 100))

    size = (
        max(1, round(image.width / cell)) * cell,
        max(1, round(image.height / cell)) * cell,
    )

    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)

    return image, cell


def image_to_json(image):
    output = io.BytesIO()
    image.save(output, format="PNG")

    image_base64 = base64.b64encode(output.getvalue()).decode("utf-8")

    return jsonify({"image": f"data:image/png;base64,{image_base64}"})


def photo_to_json(image):
    """Als image_to_json, maar als JPEG: voor resultaten die eruitzien als een foto."""
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)

    return jsonify({"image": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")})


def pages_to_json(pages):
    """Een resultaat van meerdere bladen: elk blad als PNG (om te tonen en te printen), alle bladen
    naast elkaar in één PNG (om als afbeelding te downloaden) en samen als pdf.
    In de pdf wordt een te lang blad verkleind tot het op A4 past."""
    page_width = pages[0].width
    a4 = (page_width, round(page_width * 297 / 210))
    pdf_pages = []

    for page in pages:
        if page.height > a4[1]:
            scale = a4[1] / page.height
            small = page.resize((round(page.width * scale), a4[1]), Image.Resampling.LANCZOS)
            page = Image.new("RGB", a4, "white")
            page.paste(small, ((a4[0] - small.width) // 2, 0))

        pdf_pages.append(page.convert("RGB"))

    pdf = io.BytesIO()
    pdf_pages[0].save(pdf, format="PDF", save_all=True, append_images=pdf_pages[1:], resolution=300)

    images = [image_to_data_url(page) for page in pages]

    # Alle bladen naast elkaar, met een grijs streepje ertussen
    gap = 40
    combined = Image.new("RGB", (sum(page.width for page in pages) + gap * (len(pages) - 1),
                                 max(page.height for page in pages)), "white")
    x = 0

    for page in pages:
        if x > 0:
            combined.paste((210, 210, 210), (x - gap, 0, x, combined.height))

        combined.paste(page, (x, 0))
        x += page.width + gap

    return jsonify({
        "image": images[0],
        "pages": images,
        "combined": image_to_data_url(combined),
        "pdf": "data:application/pdf;base64," + base64.b64encode(pdf.getvalue()).decode("ascii"),
    })


def image_to_data_url(image):
    output = io.BytesIO()
    image.save(output, format="PNG")

    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("utf-8")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True      # herstart de server vanzelf als je een .py-bestand opslaat (alleen lokaal; Render gebruikt gunicorn)
    )

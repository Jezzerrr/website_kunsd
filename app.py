import base64
import io
import os
import re
from functools import wraps
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps
from flask import Flask, abort, jsonify, redirect, request, send_from_directory

from src.color_page import image_to_color_page, suggest_palette
from src.dotty_affair import image_to_dots, image_to_ranked_dots
from src.helper_functions.color_helpers import get_palette
from src.shape_division import image_to_shapes
from src.shape_numbers import (
    image_to_numbered_shapes,
    image_to_palette_shapes,
    side_for_equal_area,
    suggest_shape_palette,
)

app = Flask(__name__)

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# Foto's worden opgeschaald tot minstens MIN_IMAGE_SIZE pixels op de langste zijde (een klein
# stukje uit een grote foto geeft anders een grof resultaat) en verkleind tot hoogstens
# MAX_IMAGE_SIZE (houdt het snel en het geheugen van de server beperkt).
MIN_IMAGE_SIZE = 1600
MAX_IMAGE_SIZE = 3000

# Langste zijde van het resultaat bij Shape Division: houdt het snel en de download klein.
MAX_SHAPE_SIZE = 2000

# De vormen die de website aanbiedt (shape_division.py kan er meer, maar die tonen we niet)
SHAPE_CHOICES = {"brick", "triangles", "hexagons", "cubes", "octagons_squares", "crosses"}

# Wat de server als bestand mag uitleveren. Alles anders (app.py, src/, .env, .git, ...) niet.
STATIC_FOLDERS = {"css", "js", "mijn_kunsd"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
STATIC_EXTENSIONS = IMAGE_EXTENSIONS | {".css", ".js", ".ico"}

# De pagina's met een net adres: /mijn_kunst toont mijn_kunst.html. De homepagina (index.html) staat op /.
PAGES = {"mijn_kunst", "jouw_kunst", "muziek", "contact", "bedankt"}

# Verhuisde pagina's: oud adres -> nieuw adres. "Over mij" en "Kunsd" zijn samen "Mijn Kunsd" geworden.
MOVED_PAGES = {"over-mij": "mijn_kunst", "kunst": "mijn_kunst"}

# De map met foto's voor de diavoorstelling op "Mijn Kunsd"
SLIDE_SHOW_FOLDER = "mijn_kunsd/slide_show"


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
    input_image, grid_size = snap_to_dot_grid(load_input_image())
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
    input_image, grid_size = snap_to_dot_grid(load_input_image())

    return image_to_json(image_to_dots(
        input_image,
        grid_size=grid_size,
        color=False,
        fill=read_flag("fill", default=False)
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


@app.route("/api/color-page", methods=["POST"])
@image_endpoint
def color_page():
    colors = read_custom_colors()
    fill = read_flag("fill", default=True)

    return image_to_json(image_to_color_page(
        load_input_image(),
        n_colors=int(read_number("n_colors", 6, 2, 12)),
        colors=colors or None,
        smoothness=read_number("smoothness", 1, 0, 5),
        min_region_size=read_number("min_region_size", 0.1, 0.05, 1),
        detail=read_number("detail", 0.6, 0, 1),
        fill=fill,
        legend=not fill
    ))


@app.route("/api/color-page-palette", methods=["POST"])
@image_endpoint
def color_page_palette():
    n_colors = int(read_number("n_colors", 6, 2, 12))

    return jsonify({"colors": suggest_palette(load_input_image(), n_colors)})


# ---------------------------------------------------------------------------
# De foto en de instellingen inlezen
# ---------------------------------------------------------------------------

def load_input_image():
    """De geüploade foto, bijgesneden als de bezoeker dat wilde, en op een bruikbare grootte gebracht."""
    image = Image.open(request.files["image"])

    # Draai de foto zoals de browser hem toont (telefoonfoto's hebben vaak
    # een rotatie-tag). Zo kloppen de coördinaten van de uitsnede.
    image = ImageOps.exif_transpose(image).convert("RGB")

    image = apply_crop(image)
    image = limit_size(image, MAX_IMAGE_SIZE)

    return ensure_min_size(image, MIN_IMAGE_SIZE)


def apply_crop(image):
    """Snijdt de foto bij als de browser een uitsnede heeft meegestuurd.

    De uitsnede komt binnen als fracties van de foto (0 t/m 1):
    crop_x en crop_y zijn de linkerbovenhoek, crop_w en crop_h de afmetingen.
    """
    if "crop_x" not in request.form:
        return image

    try:
        x, y, w, h = (float(request.form[name]) for name in ("crop_x", "crop_y", "crop_w", "crop_h"))
    except (KeyError, ValueError):
        return image

    left = max(0, min(image.width - 1, round(x * image.width)))
    top = max(0, min(image.height - 1, round(y * image.height)))
    right = max(left + 1, min(image.width, round((x + w) * image.width)))
    bottom = max(top + 1, min(image.height, round((y + h) * image.height)))

    return image.crop((left, top, right, bottom))


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True      # herstart de server vanzelf als je een .py-bestand opslaat (alleen lokaal; Render gebruikt gunicorn)
    )

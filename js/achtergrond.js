// Achtergrond Weghalen: de knop zoekt zelf de persoon op de foto en knipt die uit.
//
// Zo werkt het:
// - Alles gebeurt in de browser van de bezoeker, met het rekenmodel MODNet (licentie Apache-2.0,
//   gemaakt voor portretten) en de bibliotheek transformers.js. De foto gaat hiervoor dus nergens
//   heen, en de server (Render, 512 MB) hoeft niets te rekenen. Dat houdt het gratis, ook bij veel
//   bezoekers.
// - Het model (± 7 MB) en de bibliotheek worden pas geladen bij de eerste klik, niet bij het openen
//   van de pagina. Daarna bewaart de browser ze, dus een volgende keer gaat het sneller.
// - Het model geeft per pixel hoe zeker het is dat die bij de persoon hoort. Daar maken we een
//   omtrek van (js/omtrek.js): dezelfde soort vorm als bij "Uitknippen" (punten als fracties van de foto).
//   Daarna gaat alles zoals na Uitknippen: de server maakt alles buiten de vorm wit, en wie de rand
//   wil bijwerken klikt op Uitknippen.
// - Is er bijgesneden, dan zoekt het model alleen binnen de uitsnede. Zo kun je bij een foto met
//   meer mensen eerst één persoon kiezen.
//
// Gebruikt uit js/jouw_kunst.js: originalDataUrl, appliedCrop, applyShape, track, en het element
// imageUpload. Uit js/omtrek.js: outlineFromMask. De vorm draait mee met Draaien en wordt
// bewaard zoals elke uitgeknipte vorm.

const backgroundButton = document.getElementById("background-remove-button");
const backgroundStatus = document.getElementById("background-status");
const backgroundResetButton = document.getElementById("crop-reset-button");

// Vaste versie, zodat een nieuwe versie van de bibliotheek de site niet ongemerkt verandert.
const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.2/dist/transformers.min.js";
const BACKGROUND_MODEL = "Xenova/modnet";

// Het model werkt intern op 512 pixels (korte zijde); groter aanleveren heeft geen zin.
const BACKGROUND_WORK_SIZE = 1024;

// Vanaf welke zekerheid (0 t/m 1) een pixel bij de persoon hoort.
const BACKGROUND_THRESHOLD = 0.5;

// Kleiner dan dit deel van het beeld: dan is er geen persoon gevonden.
const BACKGROUND_MIN_AREA = 0.02;

// Het masker eerst wat vervagen (als deel van de langste zijde): dan wordt de rand rustig,
// zonder rafels en dunne uitsteeksels (bijv. stukjes bank of raam naast een jas).
const BACKGROUND_SMOOTH = 0.008;

// Hoe ver (in pixels van het masker) de omtrek mag afwijken bij het vereenvoudigen,
// en hoeveel punten de vorm hoogstens krijgt. Weinig punten: dan blijft bijwerken overzichtelijk.
const BACKGROUND_SIMPLIFY = 1.5;
const BACKGROUND_MAX_POINTS = 400;

const BACKGROUND_BUTTON_TEXT = "Achtergrond Weghalen";

// Het model en de voorbewerking, één keer geladen (een Promise, zodat twee snelle klikken
// niet twee keer laden).
let backgroundModel = null;


backgroundButton.addEventListener("click", async function () {
    if (!originalDataUrl) {
        return;
    }

    track("achtergrond-weghalen");

    const photo = originalDataUrl;
    const area = appliedCrop ? { ...appliedCrop } : { x: 0, y: 0, w: 1, h: 1 };

    setBackgroundBusy(true);

    try {
        const pixels = await readPhotoPixels(photo, area);
        const matte = await findPerson(pixels);

        // Intussen een andere foto gekozen: dit resultaat hoort daar niet bij.
        if (photo !== originalDataUrl) {
            return;
        }

        const outline = outlineFromMask(matte.values, matte.width, matte.height, {
            threshold: BACKGROUND_THRESHOLD,
            minArea: BACKGROUND_MIN_AREA,
            smooth: BACKGROUND_SMOOTH * Math.max(matte.width, matte.height),
            tolerance: BACKGROUND_SIMPLIFY,
            maxPoints: BACKGROUND_MAX_POINTS
        });

        if (!outline) {
            track("achtergrond-geen-persoon");
            showBackgroundStatus(
                "Er is geen persoon gevonden op deze foto. Met Uitknippen kun je zelf een vorm tekenen."
            );
            return;
        }

        // Van fracties van het masker naar fracties van de hele foto
        applyShape(outline.map(function (point) {
            return [area.x + point[0] * area.w, area.y + point[1] * area.h];
        }));

        showBackgroundStatus(
            "Klaar: alles om de persoon heen is nu wit. Niet helemaal goed? Klik op Uitknippen: " +
            "met Stuk Wegknippen en Stuk Toevoegen werk je de rand bij."
        );
    } catch (error) {
        console.error(error);
        track("achtergrond-mislukt");
        showBackgroundStatus(
            "Achtergrond weghalen is niet gelukt. Probeer het nog eens, of gebruik Uitknippen."
        );
    } finally {
        setBackgroundBusy(false);
    }
});


// Een nieuwe foto, "Originele Foto Herstellen" of Uitknippen: de melding hoort daar niet meer bij.
imageUpload.addEventListener("change", hideBackgroundStatus);
backgroundResetButton.addEventListener("click", hideBackgroundStatus);
document.getElementById("cutout-start-button").addEventListener("click", hideBackgroundStatus);


function setBackgroundBusy(isBusy) {
    backgroundButton.disabled = isBusy;
    backgroundButton.textContent = isBusy ? "Even Bezig..." : BACKGROUND_BUTTON_TEXT;

    if (isBusy) {
        showBackgroundStatus(backgroundModel
            ? "Even geduld, de achtergrond wordt weggehaald..."
            : "Even geduld, de achtergrond wordt weggehaald. De eerste keer haalt je browser eerst " +
              "het rekenmodel op (± 7 MB); je foto blijft gewoon op je eigen apparaat."
        );
    }
}


function showBackgroundStatus(text) {
    backgroundStatus.textContent = text;
    backgroundStatus.classList.remove("hidden");
}


function hideBackgroundStatus() {
    backgroundStatus.classList.add("hidden");
}


// De pixels van (de uitsnede van) de foto, verkleind tot hoogstens BACKGROUND_WORK_SIZE.
// Hier is een canvas geen probleem: kleine verstoringen (sommige browsers doen dat tegen het
// volgen van bezoekers) maken voor het vinden van de omtrek niets uit.
function readPhotoPixels(dataUrl, area) {
    return new Promise(function (resolve, reject) {
        const image = new Image();

        image.onload = function () {
            const sourceX = area.x * image.naturalWidth;
            const sourceY = area.y * image.naturalHeight;
            const sourceW = Math.max(1, area.w * image.naturalWidth);
            const sourceH = Math.max(1, area.h * image.naturalHeight);
            const scale = Math.min(1, BACKGROUND_WORK_SIZE / Math.max(sourceW, sourceH));

            const canvas = document.createElement("canvas");
            canvas.width = Math.max(1, Math.round(sourceW * scale));
            canvas.height = Math.max(1, Math.round(sourceH * scale));

            const context = canvas.getContext("2d", { willReadFrequently: true });
            context.fillStyle = "#ffffff";
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, sourceX, sourceY, sourceW, sourceH, 0, 0, canvas.width, canvas.height);

            resolve(context.getImageData(0, 0, canvas.width, canvas.height));
        };
        image.onerror = function () {
            reject(new Error("De foto kon niet gelezen worden."));
        };
        image.src = dataUrl;
    });
}


function loadBackgroundModel() {
    if (!backgroundModel) {
        backgroundModel = (async function () {
            const library = await import(TRANSFORMERS_URL);
            const [model, processor] = await Promise.all([
                library.AutoModel.from_pretrained(BACKGROUND_MODEL, { dtype: "q8" }),
                library.AutoProcessor.from_pretrained(BACKGROUND_MODEL)
            ]);

            return { library: library, model: model, processor: processor };
        })();

        // Mislukt (bijv. geen internet): de volgende klik probeert het opnieuw.
        backgroundModel.catch(function () {
            backgroundModel = null;
        });
    }

    return backgroundModel;
}


// Per pixel hoe zeker het model is dat die bij de persoon hoort (0 t/m 1).
async function findPerson(pixels) {
    const { library, model, processor } = await loadBackgroundModel();

    const image = new library.RawImage(
        new Uint8ClampedArray(pixels.data), pixels.width, pixels.height, 4
    ).rgb();

    const { pixel_values } = await processor(image);
    const { output } = await model({ input: pixel_values });

    const dims = output.dims;

    return {
        values: output.data,
        width: dims[dims.length - 1],
        height: dims[dims.length - 2]
    };
}

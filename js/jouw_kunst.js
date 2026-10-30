const imageUpload = document.getElementById("image-upload");
const uploadedImage = document.getElementById("uploaded-image");
const originalContainer = document.getElementById("original-container");
const originalTitle = document.getElementById("original-title");
const originalView = document.getElementById("original-view");
const croppedPreview = document.getElementById("cropped-preview");
const croppedPreviewFrame = document.getElementById("cropped-preview-frame");
const croppedPreviewImage = document.getElementById("cropped-preview-image");
const algorithmSection = document.getElementById("algorithm-section");
const algorithmButtons = document.querySelectorAll(".algorithm-button");
const algorithmSettings = document.querySelectorAll(".algorithm-settings");
const dotsGridSizeSlider = document.getElementById("dots-grid-size-slider");
const dotsFill = document.getElementById("dots-fill");
const shapeSelect = document.getElementById("shape-select");
const shapeGridSizeSlider = document.getElementById("shape-grid-size-slider");
const shapeColorsSlider = document.getElementById("shape-colors-slider");
const shapeFill = document.getElementById("shape-fill");
const shapeButton = document.getElementById("shape-button");
const dotsButton = document.getElementById("dots-button");
const chordinatesCountSlider = document.getElementById("chordinates-count-slider");
const chordinatesFill = document.getElementById("chordinates-fill");
const chordinatesButton = document.getElementById("chordinates-button");
const penpathCountSlider = document.getElementById("penpath-count-slider");
const penpathFill = document.getElementById("penpath-fill");
const penpathButton = document.getElementById("penpath-button");
const hatchworkColumnsSlider = document.getElementById("hatchwork-columns-slider");
const hatchworkFill = document.getElementById("hatchwork-fill");
const hatchworkButton = document.getElementById("hatchwork-button");
const statusMessage = document.getElementById("status-message");
const resultContainer = document.getElementById("result-container");
const resultImage = document.getElementById("result-image");

// Onder het resultaat: aanbod om het tekenvel te maken, en printen
const diyOffer = document.getElementById("diy-offer");
const diyOfferText = document.getElementById("diy-offer-text");
const diyOfferButton = document.getElementById("diy-offer-button");
const printButton = document.getElementById("print-button");

// "Probeer Deze" zonder foto: uitleg bij de knop "Kies Een Foto"
const tryHint = document.getElementById("try-hint");
const mainUploadLabel = document.getElementById("main-upload-label");

// Bijsnijden
const cropContainer = document.getElementById("crop-container");
const cropStage = document.getElementById("crop-stage");
const cropImage = document.getElementById("crop-image");
const cropBox = document.getElementById("crop-box");
const cropStartButton = document.getElementById("crop-start-button");
const cropResetButton = document.getElementById("crop-reset-button");
const cropOkButton = document.getElementById("crop-ok-button");
const cropCancelButton = document.getElementById("crop-cancel-button");
const cropTitle = document.getElementById("crop-title");
const cropHint = document.getElementById("crop-hint");

// Chordinates: het rondje van de foto dat de cirkel wordt, en de knop om het zelf te kiezen
const circlePreviewImage = document.getElementById("circle-preview-image");
const circleChooseButton = document.getElementById("circle-choose-button");

// De gewone teksten van de bijsnijder; bij "Kies Het Rondje" staan er andere
const CROP_TITLE = cropTitle.textContent;
const CROP_HINT = cropHint.textContent;
const CIRCLE_TITLE = "Kies Het Rondje";
const CIRCLE_HINT =
    "Sleep het rondje naar het gezicht en maak het groter of kleiner met de hoekjes. " +
    "Laat het gezicht het rondje zo goed als vullen. Klik daarna op OK.";

// Er is een downloadknop bij elk algoritme; ze delen dezelfde status.
const downloadButtons = document.querySelectorAll(".download-button");

const DOWNLOAD_HINT_DISABLED = "Maak eerst een afbeelding om te kunnen downloaden";
const DOWNLOAD_HINT_ENABLED = "Sla je kunsd op als afbeelding";

// Bestandsnaam bij downloaden en delen. Er komt altijd vanzelf een naam in met de bewerking
// en het tijdstip, zodat een telefoon geen "mijn-kunsd (1)", "(2)", ... hoeft te maken.
const fileNameInput = document.getElementById("file-name");
const pdfButton = document.getElementById("pdf-button");
const printText = document.getElementById("print-text");
const PRINT_TEXT = printText.textContent;
const shareButton = document.getElementById("share-button");

const FILE_NAMES = {
    "shape-division-settings": "shape-division",
    "chordinates-settings": "chordinates",
    "dots-settings": "coloring-dots",
    "penpath-settings": "penpath",
    "hatchwork-settings": "hatchwork"
};

// Kleinste toegestane uitsnede, als fractie van de afbeelding (0.08 = 8%).
const MIN_CROP_SIZE = 0.08;

// De uitsnede als fracties van de afbeelding (0 t/m 1), zodat het
// ook klopt als het scherm van grootte verandert.
const DEFAULT_CROP = { x: 0.05, y: 0.05, w: 0.9, h: 0.9 };

// Eigen kleuren (Shape Division): minimaal en maximaal aantal, en een beginkeuze.
const MIN_CUSTOM_COLORS = 2;
const MAX_CUSTOM_COLORS = 12;
const START_COLORS = ["#2b2d42", "#d62839", "#f9c22e", "#3a86ff", "#f4f1de"];
const EXTRA_COLORS = ["#2a9d8f", "#f4a261", "#8ecae6", "#9b5de5", "#e76f51", "#6a994e"];

// Bevat het laatste resultaat, of null als er (nog) niets te downloaden is.
let resultSource = null;

// Bij een resultaat van meerdere bladen (het tekenvel van Chordinates, Penpath en Hatchwork): alle bladen, alle
// bladen naast elkaar in één afbeelding (voor "Download Afbeelding"), en samen als pdf. Anders null.
let resultPages = null;
let resultCombined = null;
let resultPdf = null;

// Staat de bijsnijder in de stand "Kies Het Rondje" (vierkant, met een rond kader)?
let cropIsCircle = false;

// De foto waar de bewerkingen mee werken. Dit gaat altijd ongewijzigd naar de server.
// Na "Draaien" of "Spiegelen" (js/draaien.js) is dit de gedraaide foto.
let originalFile = null;
let originalDataUrl = null;

// Het bestand precies zoals geüpload, en hoe originalFile daaruit gedraaid is:
// eerst gespiegeld (flip), dan rotate graden rechtsom. Voor "Originele Foto Herstellen".
let sourceFile = null;
let orientation = { rotate: 0, flip: false };

// De gekozen uitsnede (of null als er niet is bijgesneden).
// De server snijdt de foto zelf bij; de browser hoeft dus niets te bewerken.
let appliedCrop = null;

// De uitgeknipte vorm (zie js/uitknippen.js): een lijst punten [x, y] als fracties van de
// foto, of null. Alles daarbuiten maakt de server wit. Staat los van de uitsnede hierboven.
let appliedShape = null;

// Na "Uitknippen" wordt de uitsnede de vorm plus een klein randje (fractie van de vorm).
const SHAPE_MARGIN = 0.05;

// De rechthoek die nu in de bewerker staat.
let cropRect = { ...DEFAULT_CROP };
let dragState = null;

// De bewerking die iemand bij de voorbeelden koos ("Probeer Deze") voordat er een foto was.
// Na het uploaden gaat die bewerking vanzelf open.
let pendingAlgorithm = null;

// De laatst uitgevoerde bewerking: de "Tekenvel"-schakelaar en de "Maak ..."-knop ervan.
let lastFillSwitch = null;
let lastCreateButton = null;


// Tellen mag nooit iets stukmaken (bijv. als analytics.js niet laadt).
function track(name) {
    if (typeof trackEvent === "function") {
        trackEvent(name);
    }
}


imageUpload.addEventListener("change", async function () {
    const file = imageUpload.files[0];

    if (!file) {
        return;
    }

    track("afbeelding-gekozen");

    sourceFile = file;
    orientation = { rotate: 0, flip: false };
    await showPhoto(file);

    // Nieuwe foto: het vorige resultaat en de bewerking zijn niet meer van toepassing.
    clearResult();
    closeAlgorithmSettings();

    if (pendingAlgorithm) {
        selectAlgorithm(pendingAlgorithm);
        pendingAlgorithm = null;
    }

    tryHint.classList.add("hidden");
    mainUploadLabel.classList.remove("attention");

    saveProgress();

    // De knop bovenaan de pagina staat ver weg van de foto: scroll ernaartoe.
    originalContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
});


// Toont een foto (net gekozen, of teruggezet uit de bewaarde voortgang) zonder uitsnede.
function showPhoto(file) {
    return new Promise(function (resolve, reject) {
        const reader = new FileReader();

        reader.onload = function (event) {
            originalFile = file;
            originalDataUrl = event.target.result;
            appliedCrop = null;
            appliedShape = null;

            uploadedImage.src = originalDataUrl;
            setCroppedState(false);

            cropContainer.classList.add("hidden");
            originalContainer.classList.remove("hidden");
            algorithmSection.classList.remove("hidden");
            resultContainer.classList.add("hidden");
            statusMessage.classList.add("hidden");

            resolve();
        };

        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}


/* ---------- Bijsnijden ---------- */

cropStartButton.addEventListener("click", function () {
    track("bijsnijden-start");
    openCropEditor(false);
});


// "Kies Het Rondje" bij Chordinates: dezelfde bijsnijder, maar altijd vierkant en met een rond kader.
circleChooseButton.addEventListener("click", function () {
    track("kies-het-rondje");
    openCropEditor(true);
});


function openCropEditor(isCircle) {
    if (!originalDataUrl) {
        return;
    }

    cropIsCircle = isCircle;
    cropBox.classList.toggle("crop-box-round", isCircle);
    cropTitle.textContent = isCircle ? CIRCLE_TITLE : CROP_TITLE;
    cropHint.textContent = isCircle ? CIRCLE_HINT : CROP_HINT;

    // We snijden altijd bij vanaf het origineel, zodat je een eerdere
    // uitsnede opnieuw kunt aanpassen.
    cropImage.src = originalDataUrl;
    cropImage.style.clipPath = shapeClipPath(appliedShape);

    const startRect = appliedCrop ? { ...appliedCrop } : { ...DEFAULT_CROP };
    setCropRect(isCircle ? centerSquare(startRect, uploadedImage.naturalWidth, uploadedImage.naturalHeight) : startRect);

    originalContainer.classList.add("hidden");
    algorithmSection.classList.add("hidden");
    cropContainer.classList.remove("hidden");

    cropContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


cropCancelButton.addEventListener("click", function () {
    track("bijsnijden-annuleren");
    closeCropEditor();
});


cropOkButton.addEventListener("click", function () {
    const naturalWidth = cropImage.naturalWidth;
    const naturalHeight = cropImage.naturalHeight;

    // De foto is niet geladen: er valt niets bij te snijden.
    if (!naturalWidth || !naturalHeight) {
        closeCropEditor();
        showError("Bijsnijden is mislukt. Probeer het opnieuw.");
        return;
    }

    track("bijsnijden-ok");

    appliedCrop = { ...cropRect };
    closeCropEditor();
    showNewInput();
});


// Na "Uitknippen" (js/uitknippen.js): de vorm, en een uitsnede er net omheen.
function applyShape(points) {
    appliedShape = points;
    appliedCrop = shapeBounds(points, SHAPE_MARGIN);
    showNewInput();
}


// De kleinste rechthoek om de vorm, met een randje erbij (maar niet buiten de foto).
function shapeBounds(points, margin) {
    const xs = points.map(function (point) { return point[0]; });
    const ys = points.map(function (point) { return point[1]; });

    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    const left = clamp(minX - margin * (maxX - minX), 0, 1);
    const top = clamp(minY - margin * (maxY - minY), 0, 1);
    const right = clamp(maxX + margin * (maxX - minX), 0, 1);
    const bottom = clamp(maxY + margin * (maxY - minY), 0, 1);

    return { x: left, y: top, w: right - left, h: bottom - top };
}


// Een nieuwe uitsnede of vorm tonen. Het vorige resultaat hoort er dan niet meer bij.
function showNewInput() {
    renderCroppedPreview(appliedCrop, uploadedImage.naturalWidth, uploadedImage.naturalHeight);
    setCroppedState(true);
    renderCirclePreview();

    clearResult();
    resultContainer.classList.add("hidden");
    statusMessage.classList.add("hidden");

    saveProgress();
}


// De vorm als CSS clip-path: alles erbuiten wordt doorzichtig, dus wit op een witte achtergrond.
// Zo zie je het uitgeknipte stuk zonder canvas. Zonder vorm: geen clip-path.
function shapeClipPath(points) {
    if (!points) {
        return "";
    }

    const corners = points.map(function (point) {
        return `${(point[0] * 100).toFixed(3)}% ${(point[1] * 100).toFixed(3)}%`;
    });

    return `polygon(evenodd, ${corners.join(", ")})`;
}


cropResetButton.addEventListener("click", async function () {
    if (!originalFile) {
        return;
    }

    track("bijsnijden-herstel");

    appliedCrop = null;
    appliedShape = null;

    // Gedraaid of gespiegeld: terug naar het bestand zoals het geüpload is
    if (isOriented()) {
        orientation = { rotate: 0, flip: false };
        await showPhoto(sourceFile);
    }

    setCroppedState(false);
    renderCirclePreview();

    clearResult();
    resultContainer.classList.add("hidden");
    statusMessage.classList.add("hidden");
    saveProgress();
});


function closeCropEditor() {
    dragState = null;

    cropContainer.classList.add("hidden");
    originalContainer.classList.remove("hidden");
    algorithmSection.classList.remove("hidden");

    originalContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


// Toont alleen het gekozen stuk van de foto, met gewone CSS-posities
// (dus zonder canvas, dat sommige browsers of extensies blokkeren).
function renderCroppedPreview(rect, naturalWidth, naturalHeight) {
    const ratio = (rect.h * naturalHeight) / (rect.w * naturalWidth);

    croppedPreviewImage.src = originalDataUrl;
    croppedPreviewImage.style.clipPath = shapeClipPath(appliedShape);
    croppedPreviewFrame.style.paddingBottom = `${ratio * 100}%`;
    croppedPreviewImage.style.width = `${100 / rect.w}%`;
    croppedPreviewImage.style.left = `${-(rect.x / rect.w) * 100}%`;
    croppedPreviewImage.style.top = `${-(rect.y / rect.h) * 100}%`;
}


// Het grootste vierkant (in pixels) in het midden van een uitsnede, als fracties van de foto.
// Dat vierkant gebruikt Chordinates voor de cirkel (zie _center_square in chordinates.py).
function centerSquare(rect, naturalWidth, naturalHeight) {
    if (!naturalWidth || !naturalHeight) {
        return rect;
    }

    const side = Math.min(rect.w * naturalWidth, rect.h * naturalHeight);
    const w = side / naturalWidth;
    const h = side / naturalHeight;

    return {
        x: rect.x + (rect.w - w) / 2,
        y: rect.y + (rect.h - h) / 2,
        w: w,
        h: h
    };
}


// Het rondje bij Chordinates: hetzelfde stuk van de foto als de server gebruikt.
function renderCirclePreview() {
    const naturalWidth = uploadedImage.naturalWidth;
    const naturalHeight = uploadedImage.naturalHeight;

    if (!originalDataUrl || !naturalWidth || !naturalHeight) {
        return;
    }

    const square = centerSquare(appliedCrop || { x: 0, y: 0, w: 1, h: 1 }, naturalWidth, naturalHeight);

    circlePreviewImage.src = originalDataUrl;
    circlePreviewImage.style.clipPath = shapeClipPath(appliedShape);
    circlePreviewImage.style.width = `${100 / square.w}%`;
    circlePreviewImage.style.left = `${-(square.x / square.w) * 100}%`;
    circlePreviewImage.style.top = `${-(square.y / square.h) * 100}%`;
}


// Na het laden van een (nieuwe) foto kennen we pas de afmetingen voor het rondje.
uploadedImage.addEventListener("load", renderCirclePreview);


function setCroppedState(isCropped) {
    originalTitle.textContent = isCropped ? "Uitsnede" : "Origineel";
    originalView.classList.toggle("hidden", isCropped);
    croppedPreview.classList.toggle("hidden", !isCropped);
    cropResetButton.classList.toggle("hidden", !isCropped && !isOriented());
}


function isOriented() {
    return orientation.rotate !== 0 || orientation.flip;
}


function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}


function setCropRect(rect) {
    cropRect = rect;

    cropBox.style.left = `${rect.x * 100}%`;
    cropBox.style.top = `${rect.y * 100}%`;
    cropBox.style.width = `${rect.w * 100}%`;
    cropBox.style.height = `${rect.h * 100}%`;
}


// Muispositie als fractie van de afbeelding (kan buiten 0-1 vallen).
function getPointerFraction(event) {
    const bounds = cropStage.getBoundingClientRect();

    return {
        x: (event.clientX - bounds.left) / bounds.width,
        y: (event.clientY - bounds.top) / bounds.height
    };
}


cropStage.addEventListener("pointerdown", function (event) {
    // Alleen de linkermuisknop (of een aanraking).
    if (event.button !== undefined && event.button !== 0) {
        return;
    }

    const handle = event.target.closest(".crop-handle, .crop-edge");
    const insideBox = event.target.closest("#crop-box");
    const point = getPointerFraction(event);

    let mode;

    if (handle) {
        mode = handle.dataset.handle;   // hoek: "nw", "ne", "sw", "se"; zijkant: "n", "e", "s", "w"
    } else if (insideBox) {
        mode = "move";
    } else {
        mode = "draw";                  // nieuwe rechthoek tekenen
    }

    dragState = {
        pointerId: event.pointerId,
        mode: mode,
        startPoint: point,
        startRect: { ...cropRect }
    };

    if (mode === "draw") {
        const x = clamp(point.x, 0, 1);
        const y = clamp(point.y, 0, 1);

        dragState.anchor = { x: x, y: y };
        setCropRect({ x: x, y: y, w: 0, h: 0 });
    }

    // Blijf de beweging volgen, ook als de muis buiten de foto komt.
    cropStage.setPointerCapture(event.pointerId);
    event.preventDefault();
});


cropStage.addEventListener("pointermove", function (event) {
    if (!dragState || event.pointerId !== dragState.pointerId) {
        return;
    }

    const point = getPointerFraction(event);
    const dx = point.x - dragState.startPoint.x;
    const dy = point.y - dragState.startPoint.y;
    const start = dragState.startRect;

    if (dragState.mode === "move") {
        setCropRect({
            x: clamp(start.x + dx, 0, 1 - start.w),
            y: clamp(start.y + dy, 0, 1 - start.h),
            w: start.w,
            h: start.h
        });
        return;
    }

    if (dragState.mode === "draw") {
        const x = clamp(point.x, 0, 1);
        const y = clamp(point.y, 0, 1);
        const anchor = dragState.anchor;

        if (cropIsCircle) {
            setCropRect(squareFromCorner(anchor, x >= anchor.x ? 1 : -1, y >= anchor.y ? 1 : -1,
                Math.abs(x - anchor.x), Math.abs(y - anchor.y)));
            return;
        }

        setCropRect({
            x: Math.min(anchor.x, x),
            y: Math.min(anchor.y, y),
            w: Math.abs(x - anchor.x),
            h: Math.abs(y - anchor.y)
        });
        return;
    }

    // Een hoekje of zijkant verslepen: de tegenoverliggende hoek (of zijkant) blijft staan.
    let left = start.x;
    let top = start.y;
    let right = start.x + start.w;
    let bottom = start.y + start.h;

    if (dragState.mode.includes("w")) {
        left = clamp(start.x + dx, 0, right - MIN_CROP_SIZE);
    }

    if (dragState.mode.includes("e")) {
        right = clamp(start.x + start.w + dx, left + MIN_CROP_SIZE, 1);
    }

    if (dragState.mode.includes("n")) {
        top = clamp(start.y + dy, 0, bottom - MIN_CROP_SIZE);
    }

    if (dragState.mode.includes("s")) {
        bottom = clamp(start.y + start.h + dy, top + MIN_CROP_SIZE, 1);
    }

    if (cropIsCircle) {
        setCropRect(squareResize(dragState.mode, start, left, top, right, bottom));
        return;
    }

    setCropRect({
        x: left,
        y: top,
        w: right - left,
        h: bottom - top
    });
});


// "Kies Het Rondje": de uitsnede blijft een vierkant (in pixels, dus niet in fracties: de foto is
// meestal niet vierkant). Een vierkant vanaf een vaste hoek (anchor) in de richting dirX, dirY,
// zo groot als de grootste van de twee gesleepte maten, maar nooit buiten de foto.
function squareFromCorner(anchor, dirX, dirY, w, h) {
    const naturalWidth = cropImage.naturalWidth || 1;
    const naturalHeight = cropImage.naturalHeight || 1;

    const maxW = (dirX > 0 ? 1 - anchor.x : anchor.x) * naturalWidth;
    const maxH = (dirY > 0 ? 1 - anchor.y : anchor.y) * naturalHeight;
    const minSide = MIN_CROP_SIZE * Math.min(naturalWidth, naturalHeight);
    const side = Math.max(minSide, Math.min(Math.max(w * naturalWidth, h * naturalHeight), maxW, maxH));

    const squareW = side / naturalWidth;
    const squareH = side / naturalHeight;

    return {
        x: dirX > 0 ? anchor.x : anchor.x - squareW,
        y: dirY > 0 ? anchor.y : anchor.y - squareH,
        w: squareW,
        h: squareH
    };
}


// Een hoekje of zijkant verslepen in de stand "Kies Het Rondje".
function squareResize(mode, start, left, top, right, bottom) {
    const naturalWidth = cropImage.naturalWidth || 1;
    const naturalHeight = cropImage.naturalHeight || 1;

    // Hoekje: de tegenoverliggende hoek blijft staan
    if (mode.length === 2) {
        const anchor = {
            x: mode.includes("w") ? start.x + start.w : start.x,
            y: mode.includes("n") ? start.y + start.h : start.y
        };

        return squareFromCorner(anchor, mode.includes("w") ? -1 : 1, mode.includes("n") ? -1 : 1,
            right - left, bottom - top);
    }

    // Zijkant: de tegenoverliggende zijkant blijft staan, het vierkant blijft in het midden
    const isVertical = mode === "n" || mode === "s";
    let side = isVertical ? (bottom - top) * naturalHeight : (right - left) * naturalWidth;
    side = Math.min(side, naturalWidth, naturalHeight);

    const w = side / naturalWidth;
    const h = side / naturalHeight;

    if (isVertical) {
        const centerX = start.x + start.w / 2;
        return { x: clamp(centerX - w / 2, 0, 1 - w), y: mode === "n" ? bottom - h : top, w: w, h: h };
    }

    const centerY = start.y + start.h / 2;
    return { x: mode === "w" ? right - w : left, y: clamp(centerY - h / 2, 0, 1 - h), w: w, h: h };
}


function endCropDrag(event) {
    if (!dragState || event.pointerId !== dragState.pointerId) {
        return;
    }

    // Een klik zonder slepen (of een te kleine rechthoek): terug naar de vorige uitsnede.
    if (dragState.mode === "draw" &&
        (cropRect.w < MIN_CROP_SIZE || cropRect.h < MIN_CROP_SIZE)) {
        setCropRect(dragState.startRect);
    }

    dragState = null;
}


cropStage.addEventListener("pointerup", endCropDrag);
cropStage.addEventListener("pointercancel", endCropDrag);


/* ---------- Algoritmes kiezen en uitvoeren ---------- */

algorithmButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        track("kies-" + button.dataset.settings);
        selectAlgorithm(button.dataset.settings);
    });
});


// Opent de instellingen van één bewerking (bijv. "chordinates-settings") en sluit de andere.
function selectAlgorithm(settingsId) {
    algorithmButtons.forEach(function (button) {
        button.classList.toggle("active", button.dataset.settings === settingsId);
    });

    algorithmSettings.forEach(function (settings) {
        settings.classList.toggle("hidden", settings.id !== settingsId);
    });

    saveProgress();
}


/* ---------- Voorbeelden ---------- */

// Wisselen tussen "Zo Wordt Het" en het tekenvel om te printen.
document.querySelectorAll(".example-card").forEach(function (card) {
    const image = card.querySelector(".example-image img");

    card.querySelectorAll(".view-toggle button").forEach(function (button) {
        button.addEventListener("click", function () {
            image.src = image.dataset[button.dataset.view];

            card.querySelectorAll(".view-toggle button").forEach(function (other) {
                other.classList.toggle("active", other === button);
            });
        });
    });
});


// "Probeer Deze": met een foto gaat de bewerking meteen open. Zonder foto gaan we naar "Aan De Slag",
// met uitleg bij de knop "Kies Een Foto"; na het uploaden gaat de gekozen bewerking vanzelf open.
document.querySelectorAll(".try-button[data-algorithm]").forEach(function (button) {
    button.addEventListener("click", function () {
        if (originalFile) {
            selectAlgorithm(button.dataset.algorithm);

            algorithmSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
            return;
        }

        pendingAlgorithm = button.dataset.algorithm;

        tryHint.textContent =
            `Leuk, je kiest ${button.dataset.name}! Kies eerst een foto van je computer of telefoon. ` +
            `Daarna staat ${button.dataset.name} meteen voor je klaar.`;
        tryHint.classList.remove("hidden");

        // De knop even laten oplichten (opnieuw starten als hij al oplichtte)
        mainUploadLabel.classList.remove("attention");
        void mainUploadLabel.offsetWidth;
        mainUploadLabel.classList.add("attention");

        document.getElementById("aan-de-slag").scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    });
});


// Elke slider laat zijn waarde zien in het bijbehorende <output> (met een % als daar al een % staat).
document.querySelectorAll(".art-slider").forEach(function (slider) {
    const output = document.querySelector(`output[for="${slider.id}"]`);
    const unit = output.textContent.trim().endsWith("%") ? "%" : "";

    slider.addEventListener("input", function () {
        output.textContent = slider.value + unit;
    });
});


shapeSelect.addEventListener("change", function () {
    track("kies-vorm-" + shapeSelect.value);
});


shapeButton.addEventListener("click", async function () {
    track("maak-shape-division");
    rememberAlgorithm(shapeFill, shapeButton);

    const fields = {
        shape: shapeSelect.value,
        grid_size_percent: shapeGridSizeSlider.value,
        fill: !shapeFill.checked
    };

    if (!addColorFields(fields, shapePalette, "max_colors", shapeColorsSlider)) {
        return;
    }

    await runPythonAlgorithm("/api/shape-division", fields, shapeButton);
});


dotsButton.addEventListener("click", async function () {
    track("maak-dots");
    rememberAlgorithm(dotsFill, dotsButton);

    await runPythonAlgorithm(
        "/api/dots",
        {
            grid_size_percent: dotsGridSizeSlider.value,
            fill: !dotsFill.checked
        },
        dotsButton
    );
});


penpathButton.addEventListener("click", async function () {
    track("maak-penpath");
    rememberAlgorithm(penpathFill, penpathButton);

    await runPythonAlgorithm(
        "/api/penpath",
        {
            n_lines: penpathCountSlider.value,
            fill: !penpathFill.checked
        },
        penpathButton
    );
});


hatchworkButton.addEventListener("click", async function () {
    track("maak-hatchwork");
    rememberAlgorithm(hatchworkFill, hatchworkButton);

    await runPythonAlgorithm(
        "/api/hatchwork",
        {
            columns: hatchworkColumnsSlider.value,
            fill: !hatchworkFill.checked
        },
        hatchworkButton
    );
});


chordinatesButton.addEventListener("click", async function () {
    track("maak-chordinates");
    rememberAlgorithm(chordinatesFill, chordinatesButton);

    await runPythonAlgorithm(
        "/api/chordinates",
        {
            n_lines: chordinatesCountSlider.value,
            fill: !chordinatesFill.checked
        },
        chordinatesButton
    );
});


function rememberAlgorithm(fillSwitch, createButton) {
    lastFillSwitch = fillSwitch;
    lastCreateButton = createButton;
}


/* ---------- Na het resultaat: tekenvel maken, printen ---------- */

// "Maak Het Tekenvel": zet "Tekenvel" aan en maak dezelfde bewerking opnieuw.
diyOfferButton.addEventListener("click", function () {
    if (!lastFillSwitch || !lastCreateButton) {
        return;
    }

    track("maak-het-tekenvel");

    lastFillSwitch.checked = true;
    lastCreateButton.click();
});


// Printen: style.css zorgt dat alleen het resultaat op papier komt (zie "Printen").
printButton.addEventListener("click", function () {
    if (!resultSource) {
        return;
    }

    track("print");
    window.print();
});


// Bij "Opslaan als pdf" stelt de browser de titel van de pagina voor als bestandsnaam.
// Tijdens het printen is de titel daarom de naam uit "Naam Van Je Bestand".
const PAGE_TITLE = document.title;


// Vlak voor het printen (via de knop of Ctrl+P): A4 staand of liggend, net als het resultaat.
// Het resultaat krijgt de hele pagina (min een smalle marge) en wordt daarin zo groot mogelijk
// en in het midden gezet, zonder vervormen. Zo past het altijd op één pagina.
// Een tekenvel (meerdere bladen) heeft zijn eigen witte rand al: dat krijgt geen extra marge,
// zodat het precies even groot op papier komt als in de pdf van "Download Pdf".
const PRINT_MARGIN_MM = 7;
const printPageStyle = document.createElement("style");
document.head.appendChild(printPageStyle);

window.addEventListener("beforeprint", function () {
    if (resultSource) {
        document.title = fileBaseName();
    }

    const isLandscape = resultImage.naturalWidth > resultImage.naturalHeight;
    const margin = resultPages ? 0 : PRINT_MARGIN_MM;

    // A4 is 210 x 297 mm; min de marge aan twee kanten, en wat speling tegen een lege extra pagina
    const pageHeight = isLandscape ? 210 : 297;
    const imageHeight = pageHeight - 2 * margin - (resultPages ? 0.5 : 1);

    printPageStyle.textContent =
        `@page { size: A4 ${isLandscape ? "landscape" : "portrait"}; margin: ${margin}mm; } ` +
        // Alleen op papier: anders blijft het plaatje na het printen ook op het scherm uitgerekt
        `@media print { body.jouw-kunst-page.has-result .result-image { height: ${imageHeight}mm !important; max-height: none !important; } }`;

    // Een tekenvel met bladen van verschillende richting (liggend raster, staande lijst):
    // elk blad op een eigen pagina in zijn eigen richting (benoemde pagina's in CSS).
    if (resultPages) {
        resultContainer.querySelectorAll(".result-image").forEach(function (page) {
            const pageIsLandscape = page.naturalWidth > page.naturalHeight;
            page.classList.toggle("print-liggend", pageIsLandscape);
            page.classList.toggle("print-staand", !pageIsLandscape);
        });

        printPageStyle.textContent +=
            " @page staand { size: A4 portrait; margin: 0; } @page liggend { size: A4 landscape; margin: 0; }" +
            " @media print {" +
            " body.jouw-kunst-page.has-result .result-image.print-staand { page: staand; height: 296.5mm !important; }" +
            " body.jouw-kunst-page.has-result .result-image.print-liggend { page: liggend; height: 209.5mm !important; } }";
    }
});

window.addEventListener("afterprint", function () {
    document.title = PAGE_TITLE;
    printPageStyle.textContent = "";
});


// Het aanbod "Nu Zelf Tekenen?" alleen na "Zo Wordt Het" van een tekenpuzzel (niet na het tekenvel zelf).
function updateDiyOffer() {
    const showOffer = lastFillSwitch !== null && !lastFillSwitch.checked;

    diyOffer.classList.toggle("hidden", !showOffer);

    if (showOffer) {
        diyOfferText.textContent = lastFillSwitch.dataset.offer;
    }
}


/* ---------- Eigen kleuren kiezen (Shape Division) ---------- */

// Zet de kleurkeuze van een paneel in de velden die naar de server gaan: de eigen kleuren
// als die zijn aangezet, anders het aantal kleuren van de slider (onder de naam countField).
// Geeft false terug (met een melding) als er te weinig eigen kleuren zijn.
function addColorFields(fields, palette, countField, countSlider) {
    if (!palette.isCustom()) {
        fields[countField] = countSlider.value;
        return true;
    }

    const colors = palette.getColors();

    if (colors.length < MIN_CUSTOM_COLORS) {
        showError("Kies minstens 2 kleuren.");
        return false;
    }

    fields.colors = colors.join(",");
    return true;
}

// Maakt de kleurkiezer van één paneel: schakelaar, kleurvakjes, "+ Kleur toevoegen"
// en "Kleuren uit foto". Het geeft twee functies terug: isCustom() en getColors().
function createPaletteEditor(config) {
    const customSwitch = document.getElementById(config.switchId);
    const autoColors = document.getElementById(config.autoId);
    const customColors = document.getElementById(config.customId);
    const list = document.getElementById(config.listId);
    const addButton = document.getElementById(config.addId);
    const photoButton = document.getElementById(config.photoId);
    const defaultButton = document.getElementById(config.defaultId);

    function applyMode(isCustom) {
        autoColors.classList.toggle("hidden", isCustom);
        customColors.classList.toggle("hidden", !isCustom);
    }


    customSwitch.addEventListener("change", function () {
        const isCustom = customSwitch.checked;

        applyMode(isCustom);

        // De eerste keer beginnen met een handvol kleuren, zodat je iets hebt om aan te passen.
        if (isCustom && getColors().length === 0) {
            setColors(START_COLORS);
        }

        track(config.trackName + (isCustom ? "-eigen-kleuren-aan" : "-eigen-kleuren-uit"));
    });


    addButton.addEventListener("click", function () {
        const count = getColors().length;

        if (count >= MAX_CUSTOM_COLORS) {
            return;
        }

        addColor(EXTRA_COLORS[count % EXTRA_COLORS.length]);
        updateButtons();
    });


    // Terug naar de vijf kleuren waarmee je begon.
    defaultButton.addEventListener("click", function () {
        setColors(START_COLORS);
        track(config.trackName + "-standaardkleuren");
    });


    // Laat de server de kleuren uit de foto (of uitsnede) halen, als beginpunt om zelf aan te passen.
    photoButton.addEventListener("click", async function () {
        track(config.trackName + "-kleuren-uit-foto");

        if (!originalFile) {
            return;
        }

        const count = clamp(getColors().length || 6, MIN_CUSTOM_COLORS, MAX_CUSTOM_COLORS);
        const originalText = photoButton.textContent;

        photoButton.textContent = "Bezig...";
        photoButton.disabled = true;

        try {
            const fields = { n_colors: count };

            if (config.extraFields) {
                Object.assign(fields, config.extraFields());
            }

            const response = await fetch(config.paletteUrl, {
                method: "POST",
                body: buildFormData(fields)
            });

            const data = await readServerAnswer(response, "De kleuren ophalen is mislukt.");

            setColors(data.colors);
        } catch (error) {
            showError(friendlyError(error));
        } finally {
            photoButton.textContent = originalText;
            photoButton.disabled = false;
        }
    });


    function getColors() {
        return Array.from(list.querySelectorAll('input[type="color"]')).map(function (input) {
            return input.value;
        });
    }


    function setColors(colors) {
        list.textContent = "";

        colors.slice(0, MAX_CUSTOM_COLORS).forEach(addColor);
        updateButtons();
    }


    // Eén kleurvakje: de kleurkiezer van de browser, plus een kruisje om hem te verwijderen.
    function addColor(hex) {
        const swatch = document.createElement("div");
        swatch.className = "palette-swatch";

        const input = document.createElement("input");
        input.type = "color";
        input.value = hex;
        input.setAttribute("aria-label", "Kies een kleur");

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "palette-remove";
        removeButton.textContent = "×";
        removeButton.title = "Verwijder deze kleur";
        removeButton.setAttribute("aria-label", "Verwijder deze kleur");

        removeButton.addEventListener("click", function () {
            if (getColors().length <= MIN_CUSTOM_COLORS) {
                return;
            }

            swatch.remove();
            updateButtons();
        });

        swatch.append(input, removeButton);
        list.appendChild(swatch);
    }


    function updateButtons() {
        const count = getColors().length;

        addButton.disabled = count >= MAX_CUSTOM_COLORS;

        list.querySelectorAll(".palette-remove").forEach(function (button) {
            button.disabled = count <= MIN_CUSTOM_COLORS;
        });
    }


    return {
        isCustom: function () {
            return customSwitch.checked;
        },
        getColors: getColors,
        setColors: setColors,

        // Voor het terugzetten van bewaarde voortgang: zonder tellen en zonder beginkleuren.
        setCustom: function (isCustom) {
            customSwitch.checked = isCustom;
            applyMode(isCustom);
        }
    };
}


const shapePalette = createPaletteEditor({
    switchId: "shape-custom",
    autoId: "shape-auto-colors",
    customId: "shape-custom-colors",
    listId: "shape-palette-list",
    addId: "shape-palette-add-button",
    photoId: "shape-palette-from-photo-button",
    defaultId: "shape-palette-default-button",
    trackName: "shape-division",
    paletteUrl: "/api/shape-division-palette",
    extraFields: function () {
        return {
            shape: shapeSelect.value,
            grid_size_percent: shapeGridSizeSlider.value
        };
    }
});


downloadButtons.forEach(function (button) {
    button.addEventListener("click", downloadResult);
});

shareButton.addEventListener("click", shareResult);
pdfButton.addEventListener("click", downloadPdf);


// Het originele bestand, de instellingen van het gekozen algoritme en (als die er is) de uitsnede.
function buildFormData(fields) {
    const formData = new FormData();

    formData.append("image", originalFile);

    Object.entries(fields).forEach(function ([name, value]) {
        formData.append(name, value);
    });

    if (appliedCrop) {
        formData.append("crop_x", appliedCrop.x.toFixed(6));
        formData.append("crop_y", appliedCrop.y.toFixed(6));
        formData.append("crop_w", appliedCrop.w.toFixed(6));
        formData.append("crop_h", appliedCrop.h.toFixed(6));
    }

    if (appliedShape) {
        formData.append("cut_shape", JSON.stringify(appliedShape.map(function (point) {
            return [+point[0].toFixed(5), +point[1].toFixed(5)];
        })));
    }

    return formData;
}


async function runPythonAlgorithm(url, fields, button) {
    // Altijd het originele bestand; de uitsnede geven we apart mee.
    const file = originalFile;

    if (!file) {
        return;
    }

    const formData = buildFormData(fields);

    setLoadingState(button, true);

    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData
        });

        const data = await readServerAnswer(response, "De bewerking is mislukt.");

        showResult(data.image, true, data.pages || null, data.pdf || null, data.combined || null);
    } catch (error) {
        showError(friendlyError(error));
    } finally {
        setLoadingState(button, false);
    }
}


// Leest het antwoord van de server. Normaal is dat JSON, maar als de server vastloopt
// (bijv. te lang bezig op Render) komt er een HTML-foutpagina terug. Dan tonen we een
// begrijpelijke melding in plaats van "Unexpected token '<' ... is not valid JSON".
async function readServerAnswer(response, fallbackMessage) {
    let data = null;

    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (response.ok && data) {
        return data;
    }

    if (data && data.error) {
        throw new Error(data.error);
    }

    if ([502, 503, 504].includes(response.status) || !data) {
        throw new Error(
            "De server deed er te lang over of had het even te druk. " +
            "Probeer het nog eens, eventueel met een kleinere uitsnede."
        );
    }

    throw new Error(fallbackMessage);
}


// Netwerkfouten (geen internet, server onbereikbaar) geven een Engelse browsermelding.
function friendlyError(error) {
    if (error instanceof TypeError) {
        return "Er is geen verbinding met de server. Controleer je internet en probeer het opnieuw.";
    }

    return error.message;
}


// pages en pdf: bij een resultaat van meerdere bladen (zie resultPages). Blad 1 staat in resultImage,
// de volgende bladen komen eronder; printen zet elk blad op een eigen pagina.
function showResult(imageSource, scroll = true, pages = null, pdf = null, combined = null) {
    resultImage.src = imageSource;
    resultSource = imageSource;
    resultPages = pages && pages.length > 1 ? pages : null;
    resultPdf = resultPages ? pdf : null;
    resultCombined = resultPages ? combined : null;
    pdfButton.classList.toggle("hidden", !resultPdf);

    removeExtraPages();

    if (resultPages) {
        let previous = resultImage;

        resultPages.slice(1).forEach(function (pageSource, index) {
            const page = document.createElement("img");
            page.className = "result-image result-page";
            page.src = pageSource;
            page.alt = `Blad ${index + 2} van je tekenvel`;
            previous.after(page);
            previous = page;
        });
    }

    printText.textContent = resultPages
        ? `Je tekenvel heeft ${resultPages.length} bladen: printen zet elk blad op een eigen A4. ` +
          "\"Download Pdf\" geeft alle bladen klaar om te printen, \"Download Afbeelding\" " +
          "één afbeelding met de bladen naast elkaar."
        : PRINT_TEXT;

    setDownloadEnabled(true);
    fileNameInput.value = defaultFileName();
    updateShareButton();
    updateDiyOffer();
    document.body.classList.add("has-result");

    statusMessage.classList.add("hidden");
    resultContainer.classList.remove("hidden");

    if (scroll) {
        resultContainer.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    saveProgress();
}


function showError(message) {
    statusMessage.textContent = message;
    statusMessage.classList.remove("hidden");
}


function removeExtraPages() {
    resultContainer.querySelectorAll(".result-page").forEach(function (page) {
        page.remove();
    });
}


function clearResult() {
    resultSource = null;
    resultPages = null;
    resultPdf = null;
    resultCombined = null;
    pdfButton.classList.add("hidden");
    removeExtraPages();
    resultImage.removeAttribute("src");
    setDownloadEnabled(false);
    shareButton.classList.add("hidden");
    document.body.classList.remove("has-result");
}


function setDownloadEnabled(isEnabled) {
    downloadButtons.forEach(function (button) {
        button.disabled = !isEnabled;
        button.title = isEnabled ? DOWNLOAD_HINT_ENABLED : DOWNLOAD_HINT_DISABLED;
    });
}


// "Download Afbeelding": altijd een PNG. Bij een tekenvel staan de bladen daarin naast elkaar.
function downloadResult() {
    if (!resultSource) {
        return;
    }

    track("download");
    saveFile(resultCombined || resultSource, chosenFileName(".png"));
}


// "Download Pdf" (alleen bij een tekenvel): alle bladen, elk op een eigen A4.
function downloadPdf() {
    if (!resultPdf) {
        return;
    }

    track("download-pdf");
    saveFile(resultPdf, chosenFileName(".pdf"));
}


function saveFile(source, fileName) {
    const link = document.createElement("a");

    link.href = source;
    link.download = fileName;

    document.body.appendChild(link);
    link.click();
    link.remove();
}


// Bijvoorbeeld "kunsd-shape-division-tekenvel-2026-10-24-0739"
function defaultFileName() {
    const activeButton = document.querySelector(".algorithm-button.active");
    const parts = ["kunsd"];

    if (activeButton && FILE_NAMES[activeButton.dataset.settings]) {
        parts.push(FILE_NAMES[activeButton.dataset.settings]);
    }

    if (lastFillSwitch && lastFillSwitch.checked) {
        parts.push("tekenvel");
    }

    const now = new Date();
    const pad = function (number) {
        return String(number).padStart(2, "0");
    };

    parts.push(
        now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()) +
        "-" + pad(now.getHours()) + pad(now.getMinutes())
    );

    return parts.join("-");
}


// De naam uit het invulveld, zonder tekens die in bestandsnamen niet mogen. Leeg: de standaardnaam.
// Zonder extensie: die komt erachter bij downloaden (chosenFileName), en bij printen niet (de
// browser zet er zelf .pdf achter bij "Opslaan als pdf").
function fileBaseName() {
    let name = fileNameInput.value
        .trim()
        .replace(/\.(png|pdf)$/i, "")
        .replace(/[\\/:*?"<>|]+/g, "-")
        .replace(/^\.+/, "")
        .trim();

    if (!name) {
        name = defaultFileName();
        fileNameInput.value = name;
    }

    return name;
}


function chosenFileName(extension) {
    return fileBaseName() + extension;
}


// Telefoons (en sommige computers) kunnen een bestand delen: WhatsApp, mail, of bewaren bij je foto's.
function canShareFiles() {
    if (!navigator.canShare) {
        return false;
    }

    try {
        const testFile = new File([""], "test.png", { type: "image/png" });
        return navigator.canShare({ files: [testFile] });
    } catch (error) {
        return false;
    }
}


function updateShareButton() {
    shareButton.classList.toggle("hidden", !canShareFiles());
}


async function shareResult() {
    if (!resultSource) {
        return;
    }

    track("delen");

    try {
        const blob = await (await fetch(resultCombined || resultSource)).blob();
        const file = new File([blob], chosenFileName(".png"), { type: "image/png" });

        await navigator.share({ files: [file], title: "Mijn Kunsd" });
    } catch (error) {
        // Zelf geannuleerd: niets aan de hand. Anders lukt delen niet: dan maar gewoon downloaden.
        if (error.name !== "AbortError") {
            downloadResult();
        }
    }
}


function setLoadingState(button, isLoading) {
    if (isLoading) {
        button.dataset.originalText = button.textContent;
        button.textContent = "Kunsd wordt gemaakt...";
        button.disabled = true;
        statusMessage.classList.add("hidden");
    } else {
        button.textContent = button.dataset.originalText;
        button.disabled = false;
    }
}


function closeAlgorithmSettings() {
    algorithmButtons.forEach(function (button) {
        button.classList.remove("active");
    });

    algorithmSettings.forEach(function (settings) {
        settings.classList.add("hidden");
    });
}


/* ---------- Voortgang bewaren ----------
   Foto, uitsnede, instellingen en resultaat worden in de browser van de bezoeker bewaard
   (IndexedDB; niet op de server). Ga je naar een andere pagina en kom je terug, dan staat
   alles nog klaar, ook op dezelfde plek op de pagina.

   Dat geldt alleen binnen één bezoek. Sluit je het tabblad of de browser, of druk je op F5,
   dan begin je de volgende keer met een lege pagina en wordt de bewaarde foto gewist.
   Hoe: elk tabblad krijgt een eigen bezoek-code in sessionStorage (die verdwijnt als het
   tabblad sluit). De bewaarde voortgang hoort bij die code; past hij niet, dan wordt hij gewist.
   Na MAX_SAVE_AGE_MS wordt het hoe dan ook gewist.
   Lukt bewaren niet (bijv. een privévenster), dan werkt de pagina gewoon zoals altijd. */

const SAVE_DB_NAME = "kunsd";
const SAVE_STORE = "voortgang";
const SAVE_KEY = "jouw-kunst";
const MAX_SAVE_AGE_MS = 24 * 60 * 60 * 1000;   // 1 dag
const SCROLL_KEY = "jouw-kunst-scroll";
const VISIT_KEY = "jouw-kunst-bezoek";

// Tijdens het terugzetten niet tussendoor bewaren
let isRestoring = false;
let saveTimer = null;


// De code van dit bezoek (dit tabblad). Geen sessionStorage beschikbaar: null, dan bewaren we niets.
function getVisitId() {
    try {
        let visitId = sessionStorage.getItem(VISIT_KEY);

        if (!visitId) {
            visitId = Date.now() + "-" + Math.random().toString(36).slice(2);
            sessionStorage.setItem(VISIT_KEY, visitId);
        }
        return visitId;
    } catch (error) {
        return null;
    }
}


// Is de pagina net ververst (F5 of de herlaadknop)?
function isPageReload() {
    const navigation = performance.getEntriesByType("navigation")[0];
    return Boolean(navigation && navigation.type === "reload");
}


function openSaveDb() {
    return new Promise(function (resolve, reject) {
        const request = indexedDB.open(SAVE_DB_NAME, 1);

        request.onupgradeneeded = function () {
            request.result.createObjectStore(SAVE_STORE);
        };
        request.onsuccess = function () {
            resolve(request.result);
        };
        request.onerror = function () {
            reject(request.error);
        };
    });
}


// Eén handeling op de opslag: action krijgt de "store" en geeft een request terug.
async function useSaveStore(mode, action) {
    const db = await openSaveDb();

    return new Promise(function (resolve, reject) {
        const request = action(db.transaction(SAVE_STORE, mode).objectStore(SAVE_STORE));

        request.onsuccess = function () {
            resolve(request.result);
        };
        request.onerror = function () {
            reject(request.error);
        };
    });
}


// Bewaren gebeurt kort na de laatste wijziging, niet bij elke beweging van een slider.
function saveProgress() {
    if (isRestoring) {
        return;
    }

    clearTimeout(saveTimer);
    saveTimer = setTimeout(writeProgress, 300);
}


function writeProgress() {
    saveTimer = null;

    const visitId = getVisitId();

    if (!originalFile || !visitId) {
        return;
    }

    // Alle schuifjes, schakelaars en keuzelijsten van de bewerkingen
    const controls = {};

    algorithmSection.querySelectorAll("input[id], select[id]").forEach(function (control) {
        controls[control.id] = control.type === "checkbox" ? control.checked : control.value;
    });

    const activeButton = document.querySelector(".algorithm-button.active");

    const progress = {
        savedAt: Date.now(),
        visitId: visitId,
        file: originalFile,
        sourceFile: sourceFile,
        orientation: orientation,
        crop: appliedCrop,
        shape: appliedShape,
        algorithm: activeButton ? activeButton.dataset.settings : null,
        controls: controls,
        palettes: {
            shape: shapePalette.getColors()
        },
        result: resultSource,
        resultPages: resultPages,
        resultPdf: resultPdf,
        resultCombined: resultCombined,
        lastFillSwitch: lastFillSwitch ? lastFillSwitch.id : null,
        lastCreateButton: lastCreateButton ? lastCreateButton.id : null
    };

    useSaveStore("readwrite", function (store) {
        return store.put(progress, SAVE_KEY);
    }).catch(function () {
        // Bewaren lukt niet (privévenster, geen ruimte): geen probleem, de pagina werkt gewoon.
    });
}


function clearProgress() {
    clearTimeout(saveTimer);

    return useSaveStore("readwrite", function (store) {
        return store.delete(SAVE_KEY);
    }).catch(function () {});
}


async function restoreProgress() {
    let saved;

    // F5: opnieuw beginnen, met een lege pagina bovenaan
    if (isPageReload()) {
        try {
            sessionStorage.removeItem(SCROLL_KEY);
        } catch (error) {
            // Niet erg
        }
        clearProgress();
        return;
    }

    try {
        saved = await useSaveStore("readonly", function (store) {
            return store.get(SAVE_KEY);
        });
    } catch (error) {
        return;
    }

    // Niets bewaard, of iemand heeft intussen zelf al een foto gekozen
    if (!saved || !saved.file || originalFile) {
        return;
    }

    // Bewaard in een eerder bezoek (tabblad of browser intussen gesloten), of te oud: wissen
    if (saved.visitId !== getVisitId() || Date.now() - saved.savedAt > MAX_SAVE_AGE_MS) {
        clearProgress();
        return;
    }

    isRestoring = true;

    try {
        sourceFile = saved.sourceFile || saved.file;
        orientation = saved.orientation || { rotate: 0, flip: false };
        await showPhoto(saved.file);

        if (saved.crop) {
            appliedShape = saved.shape || null;
            await restoreCrop(saved.crop);
        }

        // Instellingen terugzetten; een "input"-event laat de getallen naast de sliders meelopen.
        Object.entries(saved.controls || {}).forEach(function ([id, value]) {
            const control = document.getElementById(id);

            if (!control) {
                return;
            }

            if (control.type === "checkbox") {
                control.checked = value;
            } else {
                control.value = value;
                control.dispatchEvent(new Event("input"));
            }
        });

        restorePalette(shapePalette, "shape-custom", saved.palettes && saved.palettes.shape);

        // Een bewerking die intussen van de pagina is gehaald, gaat niet meer open
        if (saved.algorithm && document.getElementById(saved.algorithm)) {
            selectAlgorithm(saved.algorithm);
        }

        lastFillSwitch = saved.lastFillSwitch ? document.getElementById(saved.lastFillSwitch) : null;
        lastCreateButton = saved.lastCreateButton ? document.getElementById(saved.lastCreateButton) : null;

        if (saved.result) {
            showResult(saved.result, false, saved.resultPages || null, saved.resultPdf || null,
                saved.resultCombined || null);
        }

        await restoreScrollPosition();
    } catch (error) {
        // Terugzetten mislukt: begin met een lege pagina.
        clearProgress();
    } finally {
        isRestoring = false;
    }
}


// De uitsnede tonen heeft de afmetingen van de foto nodig: wacht tot hij geladen is.
function restoreCrop(crop) {
    return new Promise(function (resolve) {
        const image = new Image();

        image.onload = function () {
            appliedCrop = crop;
            renderCroppedPreview(crop, image.naturalWidth, image.naturalHeight);
            setCroppedState(true);
            renderCirclePreview();
            resolve();
        };
        image.onerror = resolve;
        image.src = originalDataUrl;
    });
}


// Terug naar waar je was op de pagina, zodra de foto en het resultaat hun hoogte hebben.
async function restoreScrollPosition() {
    let scrollY = null;

    try {
        scrollY = sessionStorage.getItem(SCROLL_KEY);
    } catch (error) {
        return;
    }

    if (scrollY === null) {
        return;
    }

    const images = [uploadedImage, croppedPreviewImage, resultImage].filter(function (image) {
        return image.getAttribute("src");
    });

    await Promise.all(images.map(function (image) {
        return image.decode().catch(function () {});
    }));

    window.scrollTo(0, Number(scrollY));
}


function restorePalette(palette, switchId, colors) {
    if (colors && colors.length > 0) {
        palette.setColors(colors);
    }

    palette.setCustom(document.getElementById(switchId).checked);
}


// Elke wijziging aan de instellingen bewaren (schuifjes, schakelaars, kleuren, + en ×)
algorithmSection.addEventListener("input", saveProgress);
algorithmSection.addEventListener("change", saveProgress);
algorithmSection.addEventListener("click", saveProgress);

// Weggaan van de pagina: wat nog op bewaren wachtte meteen bewaren, en onthouden waar je was.
// De scrollpositie gaat in sessionStorage: dat schrijft direct, ook als de pagina al sluit.
window.addEventListener("pagehide", function () {
    try {
        sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
    } catch (error) {
        // Niet erg: dan begin je bovenaan de pagina.
    }

    if (saveTimer) {
        clearTimeout(saveTimer);
        writeProgress();
    }
});


restoreProgress();

// De Speeltuin: fotobewerkingen om alleen te bekijken en te downloaden.
// Bewust los van js/jouw_kunst.js: geen uitknippen, geen tekenvel, geen bewaarde voortgang.
//
// Eén foto bovenaan (eventueel bijgesneden), en daaronder een blok per bewerking (section.playground).
// Elk blok vertelt in zijn data-attributen naar welk adres de foto moet (data-endpoint), onder welke
// naam de slider-waarde meegaat (data-param), welke vaste waarden er nog bij moeten (data-extra,
// bijv. "fill=false"), hoe de bewerking heet (data-name), hoe de download heet (data-file) en of de
// bewerking een rondje uit de foto gebruikt (data-round, met de knop "Kies Het Rondje").
//
// De uitsnede gaat als fracties mee naar de server (crop_x, crop_y, crop_w, crop_h), net als op
// Jouw Kunsd; de server snijdt zelf bij. De voorbeeldjes in de browser zijn gewone CSS-posities.

const playgroundUpload = document.getElementById("playground-upload");
const uploadBox = document.querySelector(".playground-upload-box");
const photoFrame = document.getElementById("playground-photo");
const cropButton = document.getElementById("playground-crop-button");
const cropResetButton = document.getElementById("playground-crop-reset-button");
const playgroundTools = document.querySelectorAll("section.playground");

const cropContainer = document.getElementById("crop-container");
const cropStage = document.getElementById("crop-stage");
const cropImage = document.getElementById("crop-image");
const cropBox = document.getElementById("crop-box");
const cropHint = document.getElementById("crop-hint");
const cropOkButton = document.getElementById("crop-ok-button");
const cropCancelButton = document.getElementById("crop-cancel-button");

const CROP_HINT =
    "Sleep de hoekjes of de zijkanten om de uitsnede aan te passen. Je kunt ook de rechthoek zelf " +
    "verplaatsen, of over de foto slepen om een nieuwe uitsnede te tekenen. Klik daarna op OK.";
const CIRCLE_HINT =
    "Sleep het rondje naar het gezicht en maak het groter of kleiner met de hoekjes. " +
    "Klik daarna op OK.";

// Kleinste toegestane uitsnede, als fractie van de foto (0.08 = 8%)
const MIN_CROP_SIZE = 0.08;
const FULL_PHOTO = { x: 0, y: 0, w: 1, h: 1 };

// De foto (bestand en data-URL voor de voorbeeldjes) en zijn afmetingen in pixels
let photoFile = null;
let photoUrl = null;
let photoWidth = 1;
let photoHeight = 1;

// De uitsnede (null: de hele foto) en het zelf gekozen rondje (null: het grootste vierkant in het
// midden van de uitsnede). Allebei als fracties van de foto: { x, y, w, h }.
let appliedCrop = null;
let circleCrop = null;

// De bijsnijder: is hij in de stand "rondje", in welk blok staat hij, en de rechthoek nu
let cropIsCircle = false;
let cropReturnTo = null;
let cropRect = { ...FULL_PHOTO };
let dragState = null;


/* ---------- Foto kiezen ---------- */

playgroundUpload.addEventListener("change", function () {
    const file = playgroundUpload.files[0];

    if (!file) {
        return;
    }

    const reader = new FileReader();

    reader.onload = function (event) {
        const image = new Image();

        image.onload = function () {
            photoFile = file;
            photoUrl = event.target.result;
            photoWidth = image.naturalWidth;
            photoHeight = image.naturalHeight;
            appliedCrop = null;
            circleCrop = null;

            closeCropEditor();
            uploadBox.classList.remove("needs-photo");
            cropButton.classList.remove("hidden");

            playgroundTools.forEach(function (tool) {
                tool.classList.remove("locked");
                tool.querySelectorAll("button, input").forEach(function (control) {
                    control.disabled = false;
                });
            });

            showNewInput(true);
        };

        image.src = event.target.result;
    };

    reader.readAsDataURL(file);
});


// Na een nieuwe foto of uitsnede: overal de nieuwe invoer tonen
function showNewInput(isNewPhoto) {
    showPart(photoFrame, appliedCrop || FULL_PHOTO);
    cropResetButton.classList.toggle("hidden", !appliedCrop);

    playgroundTools.forEach(function (tool) {
        showToolInput(tool, isNewPhoto);
    });
}


// Een nieuwe foto: oude resultaten horen er niet meer bij, dus geen download. Een andere uitsnede:
// de download blijft staan, maar maakt eerst het nieuwe resultaat (zie "dirty" in setUpTool).
function showToolInput(tool, isNewPhoto) {
    tool.classList.add("has-photo");
    tool.classList.remove("has-result");
    tool.querySelector(".status-message").classList.add("hidden");
    tool.dirty = true;

    if (isNewPhoto) {
        tool.querySelector(".playground-download").classList.add("hidden");
    }

    showPart(tool.querySelector(".playground-input"), toolCrop(tool));

    if (tool.querySelector(".circles-preview")) {
        updateCirclesPreview(tool);
    }

    if (tool.querySelector(".stripes-preview")) {
        loadStripesMap(tool);
    }
}


// Het stuk van de foto dat een bewerking krijgt
function toolCrop(tool) {
    if (tool.dataset.round) {
        return circleCrop || centerSquare(appliedCrop || FULL_PHOTO);
    }

    return appliedCrop || FULL_PHOTO;
}


// Toont alleen het stuk rect van de foto in een kader: het kader krijgt de juiste verhouding (aspect-ratio),
// de foto erin wordt groter gemaakt en verschoven (zonder canvas, dat sommige browsers blokkeren).
function showPart(frame, rect) {
    frame.style.aspectRatio = `${rect.w * photoWidth} / ${rect.h * photoHeight}`;

    // Meestal één foto; bij de voorvertoning van Negative Circles twee lagen (negatief en foto)
    frame.querySelectorAll("img").forEach(function (image) {
        image.src = photoUrl;
        image.style.width = `${100 / rect.w}%`;
        image.style.left = `${-(rect.x / rect.w) * 100}%`;
        image.style.top = `${-(rect.y / rect.h) * 100}%`;
    });

    frame.classList.remove("hidden");
}


// Het grootste vierkant (in pixels) in het midden van een uitsnede, als fracties van de foto.
// Dat vierkant gebruikt Negative Circles ook op de server (zie square_photo in negative_circles.py).
function centerSquare(rect) {
    const side = Math.min(rect.w * photoWidth, rect.h * photoHeight);
    const w = side / photoWidth;
    const h = side / photoHeight;

    return { x: rect.x + (rect.w - w) / 2, y: rect.y + (rect.h - h) / 2, w: w, h: h };
}


/* ---------- Bijsnijden en "Kies Het Rondje" ---------- */

cropButton.addEventListener("click", function () {
    openCropEditor(false, uploadBox);
});


cropResetButton.addEventListener("click", function () {
    appliedCrop = null;
    circleCrop = null;
    showNewInput();
});


playgroundTools.forEach(function (tool) {
    const circleButton = tool.querySelector(".circle-choose-button");

    if (circleButton) {
        circleButton.addEventListener("click", function () {
            openCropEditor(true, tool);
        });
    }
});


function openCropEditor(isCircle, section) {
    if (!photoUrl) {
        return;
    }

    closeCropEditor();

    cropIsCircle = isCircle;
    cropReturnTo = section;
    cropBox.classList.toggle("crop-box-round", isCircle);
    cropHint.textContent = isCircle ? CIRCLE_HINT : CROP_HINT;
    cropImage.src = photoUrl;

    if (isCircle) {
        setCropRect(circleCrop || centerSquare(appliedCrop || FULL_PHOTO));
    } else {
        setCropRect(appliedCrop || { x: 0.05, y: 0.05, w: 0.9, h: 0.9 });
    }

    // De bijsnijder komt in het blok waar je op de knop drukte, in plaats van de foto daar
    section.appendChild(cropContainer);
    section.classList.add("is-cropping");
    cropContainer.classList.remove("hidden");
    cropContainer.scrollIntoView({ behavior: "smooth", block: "center" });
}


function closeCropEditor() {
    dragState = null;
    cropContainer.classList.add("hidden");

    if (cropReturnTo) {
        cropReturnTo.classList.remove("is-cropping");
        cropReturnTo = null;
    }
}


cropCancelButton.addEventListener("click", function () {
    const section = cropReturnTo;
    closeCropEditor();
    section.scrollIntoView({ behavior: "smooth", block: "start" });
});


cropOkButton.addEventListener("click", function () {
    const section = cropReturnTo;

    if (cropIsCircle) {
        circleCrop = { ...cropRect };
        closeCropEditor();
        showToolInput(section);
    } else {
        appliedCrop = { ...cropRect };
        circleCrop = null;      // het rondje volgt weer het midden van de nieuwe uitsnede
        closeCropEditor();
        showNewInput();
    }

    section.scrollIntoView({ behavior: "smooth", block: "start" });
});


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


// Muispositie als fractie van de foto (kan buiten 0-1 vallen)
function getPointerFraction(event) {
    const bounds = cropStage.getBoundingClientRect();

    return {
        x: (event.clientX - bounds.left) / bounds.width,
        y: (event.clientY - bounds.top) / bounds.height
    };
}


cropStage.addEventListener("pointerdown", function (event) {
    if (event.button !== undefined && event.button !== 0) {
        return;
    }

    const handle = event.target.closest(".crop-handle, .crop-edge");
    const insideBox = event.target.closest("#crop-box");
    const point = getPointerFraction(event);
    const mode = handle ? handle.dataset.handle : (insideBox ? "move" : "draw");

    dragState = { pointerId: event.pointerId, mode: mode, startPoint: point, startRect: { ...cropRect } };

    if (mode === "draw") {
        dragState.anchor = { x: clamp(point.x, 0, 1), y: clamp(point.y, 0, 1) };
        setCropRect({ x: dragState.anchor.x, y: dragState.anchor.y, w: 0, h: 0 });
    }

    // Blijf de beweging volgen, ook als de muis buiten de foto komt
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

    // Een hoekje of zijkant verslepen: de tegenoverliggende hoek (of zijkant) blijft staan
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

    setCropRect({ x: left, y: top, w: right - left, h: bottom - top });
});


// Het rondje blijft een vierkant in pixels (de foto zelf is meestal niet vierkant): vanaf een vaste
// hoek (anchor) in de richting dirX, dirY, zo groot als de grootste gesleepte maat, nooit buiten de foto.
function squareFromCorner(anchor, dirX, dirY, w, h) {
    const maxW = (dirX > 0 ? 1 - anchor.x : anchor.x) * photoWidth;
    const maxH = (dirY > 0 ? 1 - anchor.y : anchor.y) * photoHeight;
    const minSide = MIN_CROP_SIZE * Math.min(photoWidth, photoHeight);
    const side = Math.max(minSide, Math.min(Math.max(w * photoWidth, h * photoHeight), maxW, maxH));

    const squareW = side / photoWidth;
    const squareH = side / photoHeight;

    return {
        x: dirX > 0 ? anchor.x : anchor.x - squareW,
        y: dirY > 0 ? anchor.y : anchor.y - squareH,
        w: squareW,
        h: squareH
    };
}


// Een hoekje of zijkant verslepen in de stand "Kies Het Rondje"
function squareResize(mode, start, left, top, right, bottom) {
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
    let side = isVertical ? (bottom - top) * photoHeight : (right - left) * photoWidth;
    side = Math.min(side, photoWidth, photoHeight);

    const w = side / photoWidth;
    const h = side / photoHeight;

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

    // Een klik zonder slepen (of een te kleine rechthoek): terug naar de vorige uitsnede
    if (dragState.mode === "draw" && (cropRect.w < MIN_CROP_SIZE || cropRect.h < MIN_CROP_SIZE)) {
        setCropRect(dragState.startRect);
    }

    dragState = null;
}


cropStage.addEventListener("pointerup", endCropDrag);
cropStage.addEventListener("pointercancel", endCropDrag);


/* ---------- De bewerkingen ---------- */

playgroundTools.forEach(setUpTool);


function setUpTool(tool) {
    const slider = tool.querySelector(".art-slider");
    const value = tool.querySelector(".slider-header output");
    const button = tool.querySelector(".create-button");
    const output = tool.querySelector(".playground-output");
    const download = tool.querySelector(".playground-download");
    const status = tool.querySelector(".status-message");
    const name = tool.dataset.name;
    const buttonText = button.textContent.trim();

    download.download = tool.dataset.file;

    slider.addEventListener("input", function () {
        value.textContent = slider.value + (slider.dataset.unit || "");
        tool.dirty = true;
    });

    button.addEventListener("click", make);

    // "Download Afbeelding" blijft staan als je daarna iets verandert (de slider, de uitsnede, de cirkels
    // verschuiven). Dan is het resultaat verouderd ("dirty"): de knop maakt eerst het nieuwe resultaat
    // en downloadt dat. Zo download je altijd wat je ziet.
    download.addEventListener("click", async function (event) {
        if (!tool.dirty) {
            return;
        }

        event.preventDefault();

        if (await make()) {
            download.click();
        }
    });

    // Maakt het resultaat; geeft true als dat gelukt is
    async function make() {
        if (!photoFile || button.disabled) {
            return false;
        }

        const crop = toolCrop(tool);
        const formData = new FormData();
        formData.append("image", photoFile);
        formData.append(tool.dataset.param, slider.value);

        if (crop !== FULL_PHOTO) {
            formData.append("crop_x", crop.x.toFixed(6));
            formData.append("crop_y", crop.y.toFixed(6));
            formData.append("crop_w", crop.w.toFixed(6));
            formData.append("crop_h", crop.h.toFixed(6));
        }

        // Negative Circles: hoe ver het raster van cirkels verschoven is
        if (tool.circleShift) {
            formData.append("shift_x", tool.circleShift.x.toFixed(4));
            formData.append("shift_y", tool.circleShift.y.toFixed(4));
        }

        (tool.dataset.extra || "").split("&").filter(Boolean).forEach(function (pair) {
            const [key, val] = pair.split("=");
            formData.append(key, val);
        });

        // Bezig: de knop wordt grijs en zegt het zelf. Geen (rode) melding, want er is niets mis.
        // Shadow Stripes heeft geen Maak-knop (de voorvertoning is live): daar zegt de download-knop het.
        button.disabled = true;
        button.textContent = "Even Bezig...";
        status.classList.add("hidden");
        setDownloadBusy(download, true);

        try {
            const response = await fetch(tool.dataset.endpoint, { method: "POST", body: formData });
            let data = null;

            try {
                data = await response.json();
            } catch (error) {
                data = null;
            }

            if (!response.ok || !data || !data.image) {
                throw new Error((data && data.error) || "Er ging iets mis. Probeer het nog eens.");
            }

            output.src = data.image;
            output.alt = "Je foto als " + name;
            tool.classList.add("has-result");
            tool.dirty = false;
            download.href = data.image;
            download.classList.remove("hidden");
            return true;
        } catch (error) {
            // Alleen een echte fout krijgt een (rode) melding
            status.textContent = error.message;
            status.classList.remove("hidden");
            return false;
        } finally {
            button.disabled = false;
            button.textContent = buttonText;
            setDownloadBusy(download, false);
        }
    }
}


// De download-knop grijs met "Even Bezig..." (alleen bij Shadow Stripes, data-live)
function setDownloadBusy(download, busy) {
    const tool = download.closest("section.playground");

    if (!tool.dataset.live) {
        return;
    }

    download.classList.toggle("is-busy", busy);
    download.textContent = busy ? "Even Bezig..." : "Download Afbeelding";
}


/* ---------- Negative Circles: de cirkels verschuiven ---------- */

// De voorvertoning rekent hetzelfde raster uit als src/negative_circles.py: OUTER_MARGIN en een
// cirkel precies in het midden, verschoven met circleShift (fracties van de afstand tussen twee cirkels).
const CIRCLES_OUTER_MARGIN = 0.01;

document.querySelectorAll(".circles-preview").forEach(function (frame) {
    const tool = frame.closest("section.playground");
    const slider = tool.querySelector(".art-slider");
    const centerButton = tool.querySelector(".circle-center-button");
    let drag = null;

    tool.circleShift = { x: 0, y: 0 };

    // Meer of minder cirkels, of na een resultaat aan de cirkels schuiven: terug naar de voorvertoning
    slider.addEventListener("input", function () {
        backToPreview(tool);
    });

    frame.addEventListener("pointerdown", function (event) {
        if (event.button !== undefined && event.button !== 0) {
            return;
        }

        drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, start: { ...tool.circleShift } };
        frame.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    frame.addEventListener("pointermove", function (event) {
        if (!drag || event.pointerId !== drag.pointerId) {
            return;
        }

        const spacing = circleSpacing(tool);
        tool.dirty = true;
        tool.circleShift = {
            x: wrap(drag.start.x + (event.clientX - drag.x) / spacing),
            y: wrap(drag.start.y + (event.clientY - drag.y) / spacing)
        };
        updateCirclesPreview(tool);
    });

    function endDrag(event) {
        if (drag && event.pointerId === drag.pointerId) {
            drag = null;
        }
    }

    frame.addEventListener("pointerup", endDrag);
    frame.addEventListener("pointercancel", endDrag);

    // Een resultaat is er al: klikken op het resultaat brengt de voorvertoning terug om verder te schuiven
    tool.querySelector(".playground-output").addEventListener("pointerdown", function () {
        if (tool.classList.contains("has-result")) {
            backToPreview(tool);
        }
    });

    centerButton.addEventListener("click", function () {
        tool.circleShift = { x: 0, y: 0 };
        backToPreview(tool);
    });

    window.addEventListener("resize", function () {
        updateCirclesPreview(tool);
    });
});


function backToPreview(tool) {
    if (!photoUrl) {
        return;
    }

    tool.classList.remove("has-result");
    tool.dirty = true;
    updateCirclesPreview(tool);
}


// Afstand tussen twee cirkels in de voorvertoning, in pixels op het scherm
function circleSpacing(tool) {
    const frame = tool.querySelector(".circles-preview");
    const count = Number(tool.querySelector(".art-slider").value);

    return frame.clientWidth * (1 - 2 * CIRCLES_OUTER_MARGIN) / count;
}


// Het masker: een herhaald rondje per hokje, met een cirkel in het midden plus de verschuiving
function updateCirclesPreview(tool) {
    const frame = tool.querySelector(".circles-preview");
    const mask = frame.querySelector(".circles-mask");
    const spacing = circleSpacing(tool);
    const shift = tool.circleShift || { x: 0, y: 0 };

    if (!spacing) {
        return;
    }

    const x = frame.clientWidth / 2 + (shift.x - 0.5) * spacing;
    const y = frame.clientHeight / 2 + (shift.y - 0.5) * spacing;

    mask.style.webkitMaskSize = mask.style.maskSize = `${spacing}px ${spacing}px`;
    mask.style.webkitMaskPosition = mask.style.maskPosition = `${x}px ${y}px`;

    tool.querySelector(".circle-center-button").classList.toggle("hidden", !shift.x && !shift.y);
}


// Een verschuiving van een hele cirkel is hetzelfde als geen verschuiving: houd hem tussen 0 en 1
function wrap(value) {
    return ((value % 1) + 1) % 1;
}


/* ---------- Shadow Stripes: live voorvertoning ---------- */

// De server stuurt één keer een klein grijswaardenkaartje van de foto (/api/shadow-stripes-map, zie
// data-live). Daarmee rekent de browser bij elke stand van de slider de strepen uit en tekent ze als
// SVG (geen canvas, dat sommige browsers verstoren). De download maakt de server, met precies dezelfde
// berekening in src/shadow_stripes.py: pas de getallen hieronder ALLEEN samen met die daar aan.
const STRIPES = {
    across: 240,        // STRIPES_ACROSS
    light: 0.22,        // LIGHT
    dark: 0.78,         // DARK
    wave: 0.04,         // WAVE
    waveLength: 0.25,   // WAVE_LENGTH
    minLength: 2.5      // MIN_LENGTH
};
const GOLDEN = (Math.sqrt(5) - 1) / 2;

document.querySelectorAll(".stripes-preview").forEach(function (frame) {
    const tool = frame.closest("section.playground");
    const slider = tool.querySelector(".art-slider");
    let pending = false;

    // Bij het slepen: hoogstens één keer per beeldverversing tekenen
    slider.addEventListener("input", function () {
        if (!tool.stripesMap) {
            return;
        }

        tool.classList.remove("has-result");
        tool.dirty = true;

        if (!pending) {
            pending = true;
            requestAnimationFrame(function () {
                pending = false;
                drawStripes(tool);
            });
        }
    });

    // Na een download staat het (scherpere) resultaat er; klikken brengt de voorvertoning terug
    tool.querySelector(".playground-output").addEventListener("pointerdown", function () {
        if (tool.classList.contains("has-result") && tool.stripesMap) {
            tool.classList.remove("has-result");
            drawStripes(tool);
        }
    });
});


// Haalt het grijswaardenkaartje van de (bijgesneden) foto op en tekent de strepen
async function loadStripesMap(tool) {
    const frame = tool.querySelector(".stripes-preview");
    const download = tool.querySelector(".playground-download");
    const status = tool.querySelector(".status-message");
    const crop = toolCrop(tool);
    const request = {};
    const formData = new FormData();

    // Alleen het antwoord op de laatste vraag telt (bij snel na elkaar een andere uitsnede kiezen)
    tool.stripesRequest = request;
    tool.stripesMap = null;
    frame.classList.add("is-loading");
    frame.querySelector("path").setAttribute("d", "");
    download.classList.remove("hidden");
    setDownloadBusy(download, true);

    formData.append("image", photoFile);

    if (crop !== FULL_PHOTO) {
        formData.append("crop_x", crop.x.toFixed(6));
        formData.append("crop_y", crop.y.toFixed(6));
        formData.append("crop_w", crop.w.toFixed(6));
        formData.append("crop_h", crop.h.toFixed(6));
    }

    try {
        const response = await fetch(tool.dataset.live, { method: "POST", body: formData });
        let data = null;

        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }

        if (tool.stripesRequest !== request) {
            return;
        }

        if (!response.ok || !data || !data.map) {
            throw new Error((data && data.error) || "Er ging iets mis. Probeer het nog eens.");
        }

        const bytes = atob(data.map);
        const values = new Float32Array(bytes.length);

        for (let i = 0; i < bytes.length; i++) {
            values[i] = bytes.charCodeAt(i) / 255;
        }

        tool.stripesMap = { width: data.width, height: data.height, values: values };
        frame.querySelector("svg").setAttribute("viewBox", `0 0 ${data.width} ${data.height}`);
        frame.classList.remove("is-loading");
        drawStripes(tool);
        setDownloadBusy(download, false);
    } catch (error) {
        if (tool.stripesRequest !== request) {
            return;
        }

        download.classList.add("hidden");
        setDownloadBusy(download, false);
        status.textContent = error.message;
        status.classList.remove("hidden");
    }
}


// Tekent de strepen bij de hoek van de slider: zelfde berekening als stripe_segments in src/shadow_stripes.py
function drawStripes(tool) {
    const map = tool.stripesMap;
    const angle = Number(tool.querySelector(".art-slider").value);
    const path = tool.querySelector(".stripes-preview path");
    const width = map.width;
    const height = map.height;
    const longest = Math.max(width, height);
    const spacing = longest / STRIPES.across;
    const waveLength = longest * STRIPES.waveLength;
    const minLength = STRIPES.minLength * spacing;

    const theta = angle * Math.PI / 180;
    const ux = Math.cos(theta);
    const uy = -Math.sin(theta);
    const nx = -uy;
    const ny = ux;
    const reach = Math.hypot(width, height) / 2;
    const uMax = Math.ceil(reach);
    const nHalf = Math.floor(reach / spacing) + 1;
    const parts = [];

    for (let i = -nHalf; i <= nHalf; i++) {
        const ox = width / 2 + i * spacing * nx;
        const oy = height / 2 + i * spacing * ny;
        const base = STRIPES.light + (STRIPES.dark - STRIPES.light) * positiveFraction(i * GOLDEN);
        const phase = positiveFraction(i * 0.7548776662) * 2 * Math.PI;

        let previousExcess = 0;
        let start = null;

        // Langs de lijn: u is de afstand tot het midden van de lijn, in pixels van het kaartje
        for (let u = -uMax; u <= uMax; u++) {
            const x = ox + u * ux;
            const y = oy + u * uy;
            const inside = x >= 0 && x <= width - 1 && y >= 0 && y <= height - 1;
            const threshold = base + STRIPES.wave * Math.sin(u * 2 * Math.PI / waveLength + phase);
            const excess = (inside ? sampleMap(map, x, y) : 0) - threshold;

            if (excess > 0 && start === null) {
                // Begin precies waar de drempel gepasseerd wordt (behalve op het allereerste punt)
                start = u > -uMax ? crossingU(u - 1, u, previousExcess, excess) : u;
            } else if (excess <= 0 && start !== null) {
                addStripe(parts, ox, oy, ux, uy, start, crossingU(u - 1, u, previousExcess, excess), minLength);
                start = null;
            }

            previousExcess = excess;
        }

        // Een streep die tot het eind van de lijn doorloopt
        if (start !== null) {
            addStripe(parts, ox, oy, ux, uy, start, uMax, minLength);
        }
    }

    path.setAttribute("d", parts.join(""));
    path.setAttribute("stroke-width", (spacing * 1.05).toFixed(3));
}


function addStripe(parts, ox, oy, ux, uy, start, end, minLength) {
    if (end - start >= minLength) {
        parts.push(
            "M" + (ox + start * ux).toFixed(1) + " " + (oy + start * uy).toFixed(1) +
            "L" + (ox + end * ux).toFixed(1) + " " + (oy + end * uy).toFixed(1)
        );
    }
}


// Waar tussen u1 en u2 de drempel precies gepasseerd wordt (excess wisselt van teken)
function crossingU(u1, u2, excess1, excess2) {
    return u1 + (u2 - u1) * excess1 / (excess1 - excess2);
}


// Bilineair bemonsteren van het kaartje (x, y binnen het kaartje)
function sampleMap(map, x, y) {
    const width = map.width;
    const values = map.values;
    const x0 = Math.min(Math.floor(x), width - 2);
    const y0 = Math.min(Math.floor(y), map.height - 2);
    const fx = x - x0;
    const fy = y - y0;
    const i = y0 * width + x0;

    const top = values[i] * (1 - fx) + values[i + 1] * fx;
    const bottom = values[i + width] * (1 - fx) + values[i + width + 1] * fx;

    return top * (1 - fy) + bottom * fy;
}


// Het deel achter de komma, ook voor negatieve getallen (zoals % 1 in Python)
function positiveFraction(value) {
    return ((value % 1) + 1) % 1;
}

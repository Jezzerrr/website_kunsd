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

            showNewInput();
        };

        image.src = event.target.result;
    };

    reader.readAsDataURL(file);
});


// Na een nieuwe foto of uitsnede: overal de nieuwe invoer tonen; oude resultaten horen er niet meer bij
function showNewInput() {
    showPart(photoFrame, appliedCrop || FULL_PHOTO);
    cropResetButton.classList.toggle("hidden", !appliedCrop);

    playgroundTools.forEach(showToolInput);
}


function showToolInput(tool) {
    tool.classList.add("has-photo");
    tool.classList.remove("has-result");
    tool.querySelector(".playground-download").classList.add("hidden");
    tool.querySelector(".status-message").classList.add("hidden");

    showPart(tool.querySelector(".playground-input"), toolCrop(tool));
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
    const image = frame.querySelector("img");

    frame.style.aspectRatio = `${rect.w * photoWidth} / ${rect.h * photoHeight}`;
    image.src = photoUrl;
    image.style.width = `${100 / rect.w}%`;
    image.style.left = `${-(rect.x / rect.w) * 100}%`;
    image.style.top = `${-(rect.y / rect.h) * 100}%`;
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
    });

    button.addEventListener("click", async function () {
        if (!photoFile) {
            return;
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

        // Schakelaars (zoals Zwart-Wit) gaan mee onder hun name, als "true" of "false"
        tool.querySelectorAll('input[type="checkbox"][name]').forEach(function (checkbox) {
            formData.append(checkbox.name, checkbox.checked ? "true" : "false");
        });

        (tool.dataset.extra || "").split("&").filter(Boolean).forEach(function (pair) {
            const [key, val] = pair.split("=");
            formData.append(key, val);
        });

        // Bezig: de knop wordt grijs en zegt het zelf. Geen (rode) melding, want er is niets mis.
        button.disabled = true;
        button.textContent = "Even Bezig...";
        status.classList.add("hidden");

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
            download.href = data.image;
            download.classList.remove("hidden");
        } catch (error) {
            // Alleen een echte fout krijgt een (rode) melding
            status.textContent = error.message;
            status.classList.remove("hidden");
        } finally {
            button.disabled = false;
            button.textContent = buttonText;
        }
    });
}

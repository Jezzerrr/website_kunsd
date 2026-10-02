const imageUpload = document.getElementById("image-upload");
const uploadedImage = document.getElementById("uploaded-image");
const originalContainer = document.getElementById("original-container");
const originalTitle = document.getElementById("original-title");
const algorithmSection = document.getElementById("algorithm-section");
const algorithmButtons = document.querySelectorAll(".algorithm-button");
const algorithmSettings = document.querySelectorAll(".algorithm-settings");
const rankedGridSizeSlider = document.getElementById("ranked-grid-size-slider");
const rankedGridSizeValue = document.getElementById("ranked-grid-size-value");
const dotsGridSizeSlider = document.getElementById("dots-grid-size-slider");
const dotsGridSizeValue = document.getElementById("dots-grid-size-value");
const dotsFill = document.getElementById("dots-fill");
const rankedDotsButton = document.getElementById("ranked-dots-button");
const dotsButton = document.getElementById("dots-button");
const statusMessage = document.getElementById("status-message");
const resultContainer = document.getElementById("result-container");
const resultImage = document.getElementById("result-image");

// Bijsnijden
const cropContainer = document.getElementById("crop-container");
const cropStage = document.getElementById("crop-stage");
const cropImage = document.getElementById("crop-image");
const cropBox = document.getElementById("crop-box");
const cropStartButton = document.getElementById("crop-start-button");
const cropResetButton = document.getElementById("crop-reset-button");
const cropOkButton = document.getElementById("crop-ok-button");
const cropCancelButton = document.getElementById("crop-cancel-button");

// Er is een downloadknop bij elk algoritme; ze delen dezelfde status.
const downloadButtons = document.querySelectorAll(".download-button");

const DOWNLOAD_HINT_DISABLED = "Maak eerst een afbeelding om te kunnen downloaden";
const DOWNLOAD_HINT_ENABLED = "Sla je kunsd op als afbeelding";

// Kleinste toegestane uitsnede, als fractie van de afbeelding (0.08 = 8%).
const MIN_CROP_SIZE = 0.08;

// Maximaal aantal pixels van een uitsnede (16 megapixel), voor telefoons.
const MAX_CROP_PIXELS = 16000000;

// Bevat het laatste resultaat, of null als er (nog) niets te downloaden is.
let resultSource = null;

// Wat de gebruiker heeft geüpload.
let originalFile = null;
let originalDataUrl = null;

// Wat naar de algoritmes gaat: het origineel, of de uitsnede.
let currentFile = null;

// De uitsnede als fracties van de afbeelding (0 t/m 1), zodat het
// ook klopt als het scherm van grootte verandert.
let cropRect = { x: 0.05, y: 0.05, w: 0.9, h: 0.9 };
let dragState = null;


imageUpload.addEventListener("change", function () {
    const file = imageUpload.files[0];

    if (!file) {
        return;
    }

    const reader = new FileReader();

    reader.onload = function (event) {
        originalFile = file;
        originalDataUrl = event.target.result;
        currentFile = file;

        uploadedImage.src = originalDataUrl;
        setCroppedState(false);

        cropContainer.classList.add("hidden");
        originalContainer.classList.remove("hidden");
        algorithmSection.classList.remove("hidden");
        resultContainer.classList.add("hidden");
        statusMessage.classList.add("hidden");

        // Nieuwe foto: het vorige resultaat is niet meer van toepassing.
        clearResult();
        closeAlgorithmSettings();
    };

    reader.readAsDataURL(file);
});


/* ---------- Bijsnijden ---------- */

uploadedImage.addEventListener("error", function () {
    showError("De afbeelding kon niet worden getoond.");
});

cropStartButton.addEventListener("click", function () {
    if (!originalDataUrl) {
        return;
    }

    // We snijden altijd bij vanaf het origineel, zodat je een eerdere
    // uitsnede opnieuw kunt aanpassen.
    cropImage.src = originalDataUrl;
    setCropRect({ x: 0.05, y: 0.05, w: 0.9, h: 0.9 });

    originalContainer.classList.add("hidden");
    algorithmSection.classList.add("hidden");
    cropContainer.classList.remove("hidden");

    cropContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
});


cropCancelButton.addEventListener("click", function () {
    closeCropEditor();
});


cropOkButton.addEventListener("click", function () {
    const sourceWidth = cropImage.naturalWidth;
    const sourceHeight = cropImage.naturalHeight;

    // De foto is niet geladen: er valt niets bij te snijden.
    if (!sourceWidth || !sourceHeight) {
        closeCropEditor();
        showError("Bijsnijden is mislukt. Probeer het opnieuw.");
        return;
    }

    // Reken de fracties om naar echte pixels van de originele foto.
    const sx = Math.round(cropRect.x * sourceWidth);
    const sy = Math.round(cropRect.y * sourceHeight);
    const sw = Math.max(1, Math.min(Math.round(cropRect.w * sourceWidth), sourceWidth - sx));
    const sh = Math.max(1, Math.min(Math.round(cropRect.h * sourceHeight), sourceHeight - sy));

    // Heel grote uitsnedes verkleinen we iets, anders wordt het te traag
    // (vooral op telefoons).
    const scale = Math.min(1, Math.sqrt(MAX_CROP_PIXELS / (sw * sh)));
    const outWidth = Math.max(1, Math.round(sw * scale));
    const outHeight = Math.max(1, Math.round(sh * scale));

    setCropBusy(true);

    // Even wachten, zodat de browser "Bezig..." kan tonen voordat het zware werk begint.
    setTimeout(function () {
        try {
            const canvas = document.createElement("canvas");
            canvas.width = outWidth;
            canvas.height = outHeight;

            const context = canvas.getContext("2d");

            // Witte achtergrond, voor foto's met transparantie.
            context.fillStyle = "#ffffff";
            context.fillRect(0, 0, outWidth, outHeight);
            context.drawImage(cropImage, sx, sy, sw, sh, 0, 0, outWidth, outHeight);

            // JPEG is veel sneller en kleiner dan PNG en voor foto's ruim goed genoeg.
            canvas.toBlob(function (blob) {
                if (!blob) {
                    failCrop();
                    return;
                }

                const baseName = originalFile.name.replace(/\.[^.]+$/, "");
                const croppedFile = new File([blob], baseName + "-uitsnede.jpg", { type: "image/jpeg" });

                // Net als bij het uploaden: lees het bestand in als data-URL en toon die.
                const reader = new FileReader();

                reader.onload = function (event) {
                    currentFile = croppedFile;
                    uploadedImage.src = event.target.result;
                    setCroppedState(true);

                    // Nieuwe invoer: het vorige resultaat hoort er niet meer bij.
                    clearResult();
                    resultContainer.classList.add("hidden");
                    statusMessage.classList.add("hidden");

                    setCropBusy(false);
                    closeCropEditor();
                };

                reader.onerror = failCrop;
                reader.readAsDataURL(croppedFile);
            }, "image/jpeg", 0.92);
        } catch (error) {
            failCrop();
        }
    }, 50);
});


function failCrop() {
    setCropBusy(false);
    closeCropEditor();
    showError("Bijsnijden is mislukt. Probeer het opnieuw.");
}


function setCropBusy(isBusy) {
    cropOkButton.disabled = isBusy;
    cropCancelButton.disabled = isBusy;
    cropOkButton.textContent = isBusy ? "Bezig..." : "OK";
}


cropResetButton.addEventListener("click", function () {
    if (!originalFile) {
        return;
    }

    currentFile = originalFile;
    uploadedImage.src = originalDataUrl;
    setCroppedState(false);

    clearResult();
    resultContainer.classList.add("hidden");
    statusMessage.classList.add("hidden");
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


function setCroppedState(isCropped) {
    originalTitle.textContent = isCropped ? "Uitsnede" : "Origineel";
    cropResetButton.classList.toggle("hidden", !isCropped);
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

    const handle = event.target.closest(".crop-handle");
    const insideBox = event.target.closest("#crop-box");
    const point = getPointerFraction(event);

    let mode;

    if (handle) {
        mode = handle.dataset.handle;   // "nw", "ne", "sw" of "se"
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

        setCropRect({
            x: Math.min(anchor.x, x),
            y: Math.min(anchor.y, y),
            w: Math.abs(x - anchor.x),
            h: Math.abs(y - anchor.y)
        });
        return;
    }

    // Een hoekje verslepen: de tegenoverliggende hoek blijft staan.
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

    setCropRect({
        x: left,
        y: top,
        w: right - left,
        h: bottom - top
    });
});


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
        const settingsId = button.dataset.settings;
        const selectedSettings = document.getElementById(settingsId);

        algorithmButtons.forEach(function (otherButton) {
            otherButton.classList.remove("active");
        });

        algorithmSettings.forEach(function (settings) {
            settings.classList.add("hidden");
        });

        button.classList.add("active");
        selectedSettings.classList.remove("hidden");
    });
});


rankedGridSizeSlider.addEventListener("input", function () {
    rankedGridSizeValue.textContent = `${rankedGridSizeSlider.value}%`;
});


dotsGridSizeSlider.addEventListener("input", function () {
    dotsGridSizeValue.textContent = `${dotsGridSizeSlider.value}%`;
});


rankedDotsButton.addEventListener("click", async function () {
    await runPythonAlgorithm(
        "/api/ranked-dots",
        rankedGridSizeSlider.value,
        false,
        rankedDotsButton
    );
});


dotsButton.addEventListener("click", async function () {
    await runPythonAlgorithm(
        "/api/dots",
        dotsGridSizeSlider.value,
        !dotsFill.checked,
        dotsButton
    );
});


downloadButtons.forEach(function (button) {
    button.addEventListener("click", downloadResult);
});


async function runPythonAlgorithm(url, gridSizePercent, fill, button) {
    // Het origineel of de uitsnede, afhankelijk van wat de gebruiker koos.
    const file = currentFile;

    if (!file) {
        return;
    }

    const formData = new FormData();

    formData.append("image", file);
    formData.append("grid_size_percent", gridSizePercent);
    formData.append("fill", fill);

    setLoadingState(button, true);

    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "De bewerking is mislukt.");
        }

        showResult(data.image);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoadingState(button, false);
    }
}


function showResult(imageSource) {
    resultImage.src = imageSource;
    resultSource = imageSource;
    setDownloadEnabled(true);

    statusMessage.classList.add("hidden");
    resultContainer.classList.remove("hidden");

    resultContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


function showError(message) {
    statusMessage.textContent = message;
    statusMessage.classList.remove("hidden");
}


function clearResult() {
    resultSource = null;
    resultImage.removeAttribute("src");
    setDownloadEnabled(false);
}


function setDownloadEnabled(isEnabled) {
    downloadButtons.forEach(function (button) {
        button.disabled = !isEnabled;
        button.title = isEnabled ? DOWNLOAD_HINT_ENABLED : DOWNLOAD_HINT_DISABLED;
    });
}


function downloadResult() {
    if (!resultSource) {
        return;
    }

    const link = document.createElement("a");

    link.href = resultSource;
    link.download = "mijn-kunsd.png";

    document.body.appendChild(link);
    link.click();
    link.remove();
}


function setLoadingState(button, isLoading) {
    if (isLoading) {
        button.dataset.originalText = button.textContent;
        button.textContent = "Kunsd wordt gemaakt...";
        button.disabled = true;
        statusMessage.classList.add("hidden");
//        resultContainer.classList.add("hidden");
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

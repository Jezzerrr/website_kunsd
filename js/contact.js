// Het contactformulier.
//
// Zonder foto verstuurt de browser het formulier gewoon naar Web3Forms (zoals altijd).
// Met foto('s) sturen we alles naar de eigen server (/api/contact in app.py), die er een mail
// met bijlagen van maakt. Web3Forms kan alleen in het betaalde abonnement bijlagen meesturen.

const contactForm = document.getElementById("contact-form");
const subjectInput = document.getElementById("onderwerp");
const mailSubject = document.getElementById("mail-subject");
const imageInput = document.getElementById("contact-images");
const fileDrop = document.getElementById("file-drop");
const filePreviews = document.getElementById("file-previews");
const contactStatus = document.getElementById("contact-status");
const submitButton = document.getElementById("contact-submit");

// Moeten gelijk zijn aan CONTACT_MAX_IMAGES en CONTACT_MAX_FILE_MB in app.py
const MAX_IMAGES = 3;
const MAX_FILE_MB = 15;

// De gekozen foto's. We houden ze zelf bij, zodat je er meer kunt toevoegen of er een kunt weghalen.
let selectedImages = [];


// Tellen mag nooit iets stukmaken (bijv. als analytics.js niet laadt).
function track(name) {
    if (typeof trackEvent === "function") {
        trackEvent(name);
    }
}


// Een onderwerp in het adres invullen, bijv. /contact?onderwerp=Mijn%20Kunsd (vanaf "Jouw Kunsd").
const presetSubject = new URLSearchParams(window.location.search).get("onderwerp");

if (presetSubject && !subjectInput.value) {
    subjectInput.value = presetSubject.slice(0, 100);
}


/* ---------- Foto's kiezen ---------- */

imageInput.addEventListener("change", function () {
    addImages(imageInput.files);

    // Leegmaken, zodat je dezelfde foto na het weghalen opnieuw kunt kiezen.
    imageInput.value = "";
});


// Slepen en neerzetten op het vak
["dragenter", "dragover"].forEach(function (type) {
    fileDrop.addEventListener(type, function (event) {
        event.preventDefault();
        fileDrop.classList.add("dragging");
    });
});

["dragleave", "drop"].forEach(function (type) {
    fileDrop.addEventListener(type, function () {
        fileDrop.classList.remove("dragging");
    });
});

fileDrop.addEventListener("drop", function (event) {
    event.preventDefault();
    addImages(event.dataTransfer.files);
});


function addImages(files) {
    hideError();

    Array.from(files).forEach(function (file) {
        if (!file.type.startsWith("image/")) {
            showError(`"${file.name}" is geen afbeelding.`);
            return;
        }

        if (file.size > MAX_FILE_MB * 1024 * 1024) {
            showError(`"${file.name}" is groter dan ${MAX_FILE_MB} MB. Kies een kleinere foto.`);
            return;
        }

        if (selectedImages.length >= MAX_IMAGES) {
            showError(`Je kunt maximaal ${MAX_IMAGES} foto's meesturen.`);
            return;
        }

        selectedImages.push(file);
    });

    if (selectedImages.length > 0) {
        track("contact-foto-toegevoegd");
    }

    renderPreviews();
}


// Een klein voorbeeld van elke foto, met een kruisje om hem weg te halen.
function renderPreviews() {
    filePreviews.textContent = "";

    selectedImages.forEach(function (file, index) {
        const preview = document.createElement("div");
        preview.className = "file-preview";

        const image = document.createElement("img");
        image.src = URL.createObjectURL(file);
        image.alt = file.name;
        image.onload = function () {
            URL.revokeObjectURL(image.src);
        };

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "palette-remove";
        removeButton.textContent = "×";
        removeButton.title = "Haal deze foto weg";
        removeButton.setAttribute("aria-label", "Haal deze foto weg");
        removeButton.dataset.track = "contact-foto-weghalen";

        removeButton.addEventListener("click", function () {
            selectedImages.splice(index, 1);
            renderPreviews();
        });

        preview.append(image, removeButton);
        filePreviews.appendChild(preview);
    });

    fileDrop.classList.toggle("hidden", selectedImages.length >= MAX_IMAGES);
}


/* ---------- Versturen ---------- */

contactForm.addEventListener("submit", async function (event) {
    mailSubject.value = "[Kunsd Website] " + subjectInput.value.trim();

    // Zonder foto: de browser verstuurt het formulier zelf naar Web3Forms.
    if (selectedImages.length === 0) {
        return;
    }

    event.preventDefault();
    hideError();
    track("contact-verzonden-met-foto");

    const formData = new FormData();

    ["name", "email", "onderwerp", "message"].forEach(function (name) {
        formData.append(name, contactForm.elements[name].value);
    });

    formData.append("botcheck", contactForm.elements.botcheck.checked ? "on" : "");

    selectedImages.forEach(function (file) {
        formData.append("images", file);
    });

    submitButton.disabled = true;
    submitButton.textContent = "Bezig Met Versturen...";

    try {
        const response = await fetch("/api/contact", {
            method: "POST",
            body: formData
        });

        let data = null;

        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }

        if (!response.ok || !data) {
            throw new Error(
                (data && data.error) ||
                "Versturen is niet gelukt. Probeer het nog eens, of stuur je bericht zonder foto."
            );
        }

        window.location.href = "/bedankt";
    } catch (error) {
        showError(
            error instanceof TypeError
                ? "Er is geen verbinding met de server. Controleer je internet en probeer het opnieuw."
                : error.message
        );

        submitButton.disabled = false;
        submitButton.textContent = "Verzenden";
    }
});


function showError(message) {
    contactStatus.textContent = message;
    contactStatus.classList.remove("hidden");
}


function hideError() {
    contactStatus.classList.add("hidden");
}

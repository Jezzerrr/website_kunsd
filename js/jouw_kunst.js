const imageUpload = document.getElementById("image-upload");
const uploadedImage = document.getElementById("uploaded-image");
const originalContainer = document.getElementById("original-container");
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

// Er is een downloadknop bij elk algoritme; ze delen dezelfde status.
const downloadButtons = document.querySelectorAll(".download-button");

const DOWNLOAD_HINT_DISABLED = "Maak eerst een afbeelding om te kunnen downloaden";
const DOWNLOAD_HINT_ENABLED = "Sla je kunsd op als afbeelding";

// Bevat het laatste resultaat, of null als er (nog) niets te downloaden is.
let resultSource = null;


imageUpload.addEventListener("change", function () {
    const file = imageUpload.files[0];

    if (!file) {
        return;
    }

    const reader = new FileReader();

    reader.onload = function (event) {
        uploadedImage.src = event.target.result;

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
    const file = imageUpload.files[0];

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

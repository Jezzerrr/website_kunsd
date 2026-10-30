// De Speeltuin: fotobewerkingen om alleen te bekijken en te downloaden (nu: RedBlack Dots).
// Bewust los van js/jouw_kunst.js: geen bijsnijden, geen tekenvel, geen bewaarde voortgang.

const playgroundUpload = document.getElementById("playground-upload");
const playgroundSlider = document.getElementById("playground-dot-slider");
const playgroundValue = document.getElementById("playground-dot-value");
const playgroundButton = document.getElementById("playground-button");
const playgroundImage = document.getElementById("playground-image");
const playgroundDownload = document.getElementById("playground-download");
const playgroundStatus = document.getElementById("playground-status");

let playgroundFile = null;


playgroundSlider.addEventListener("input", function () {
    playgroundValue.textContent = playgroundSlider.value + "%";
});


playgroundUpload.addEventListener("change", function () {
    playgroundFile = playgroundUpload.files[0] || null;
    playgroundButton.disabled = !playgroundFile;
    playgroundDownload.classList.add("hidden");

    if (playgroundFile) {
        playgroundImage.src = URL.createObjectURL(playgroundFile);
        playgroundImage.alt = "Je foto";
        showStatus("Klik op \"Maak RedBlack Dots\".");
    }
});


playgroundButton.addEventListener("click", async function () {
    if (!playgroundFile) {
        return;
    }

    const formData = new FormData();
    formData.append("image", playgroundFile);
    formData.append("grid_size_percent", playgroundSlider.value);
    formData.append("fill", "false");

    playgroundButton.disabled = true;
    showStatus("Even geduld, je stippen worden gezet...");

    try {
        const response = await fetch("/api/ranked-dots", { method: "POST", body: formData });
        let data = null;

        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }

        if (!response.ok || !data || !data.image) {
            throw new Error((data && data.error) || "Er ging iets mis. Probeer het nog eens.");
        }

        playgroundImage.src = data.image;
        playgroundImage.alt = "Je foto als RedBlack Dots";
        playgroundDownload.href = data.image;
        playgroundDownload.classList.remove("hidden");
        hideStatus();
    } catch (error) {
        showStatus(error.message);
    } finally {
        playgroundButton.disabled = false;
    }
});


function showStatus(text) {
    playgroundStatus.textContent = text;
    playgroundStatus.classList.remove("hidden");
}


function hideStatus() {
    playgroundStatus.classList.add("hidden");
}

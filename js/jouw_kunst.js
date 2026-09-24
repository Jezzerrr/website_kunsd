const imageInput = document.getElementById("imageInput");

const preview = document.getElementById("preview");
const result = document.getElementById("result");

const blackWhiteButton = document.getElementById("blackWhiteButton");
const rotateButton = document.getElementById("rotateButton");
const inverseButton = document.getElementById("inverseButton");


// Hier bewaren we de gekozen afbeelding

let selectedImage = null;


// Wanneer de gebruiker een foto kiest

imageInput.addEventListener("change", function () {

    const file = imageInput.files[0];

    if (!file) {
        return;
    }


    // Maak een Image-object

    selectedImage = new Image();

    selectedImage.src = URL.createObjectURL(file);


    // Wacht totdat de afbeelding geladen is

    selectedImage.onload = function () {

        // Oude preview verwijderen

        preview.innerHTML = "";


        // Geef de afbeelding een CSS-class

        selectedImage.classList.add("uploaded-image");


        // Toon de afbeelding

        preview.appendChild(selectedImage);


        // Maak de drie knoppen actief

        blackWhiteButton.disabled = false;
        rotateButton.disabled = false;
        inverseButton.disabled = false;


        // Verwijder eventueel een oud resultaat

        result.innerHTML = "";
    };
});


// ----------------------------------------
// Zwart-wit
// ----------------------------------------

blackWhiteButton.addEventListener("click", function () {

    if (!selectedImage) {
        return;
    }


    const canvas = makeBlackAndWhite(selectedImage);


    showResult(
        canvas,
        "Zwart-wit",
        "jouw_kunsd_zwart_wit.jpg"
    );
});


// ----------------------------------------
// 180 graden roteren
// ----------------------------------------

rotateButton.addEventListener("click", function () {

    if (!selectedImage) {
        return;
    }


    const canvas = rotate180(selectedImage);


    showResult(
        canvas,
        "180 graden geroteerd",
        "jouw_kunsd_180_graden.jpg"
    );
});


// ----------------------------------------
// Inverse colors
// ----------------------------------------

inverseButton.addEventListener("click", function () {

    if (!selectedImage) {
        return;
    }


    const canvas = makeInverseColors(selectedImage);


    showResult(
        canvas,
        "Inverse color",
        "jouw_kunsd_inverse.jpg"
    );
});


// ----------------------------------------
// Resultaat tonen
// ----------------------------------------

function showResult(canvas, title, filename) {

    // Verwijder eventueel een vorig resultaat

    result.innerHTML = "";


    // Titel

    const heading = document.createElement("h2");

    heading.textContent = title;

    result.appendChild(heading);


    // Canvas een CSS-class geven

    canvas.classList.add("result-image");


    // Canvas tonen

    result.appendChild(canvas);


    // Downloadknop

    const downloadButton = document.createElement("a");

    downloadButton.textContent = "Download jouw kunsd";

    downloadButton.href = canvas.toDataURL("image/jpeg");

    downloadButton.download = filename;


    result.appendChild(
        document.createElement("br")
    );

    result.appendChild(downloadButton);
}

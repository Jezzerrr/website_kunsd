let selectedImage = null;


// HTML elements
const imageUpload = document.getElementById("image-upload");
const uploadedImage = document.getElementById("uploaded-image");

const buttonsHTML = document.getElementById("buttons-html");
const buttonsPython = document.getElementById("buttons-python");

const resultContainer = document.getElementById("result-container");
const resultImage = document.getElementById("result-image");
const downloadButton = document.getElementById("download-button");

const gridSizeSlider = document.getElementById("grid-size-slider");
const gridSizeValue = document.getElementById("grid-size-value");


// Upload
imageUpload.addEventListener("change", function () {

    const file = imageUpload.files[0];

    if (!file) {
        return;
    }

    const reader = new FileReader();

    reader.onload = function (event) {

        selectedImage = new Image();

        selectedImage.onload = function () {

            uploadedImage.src = event.target.result;

            buttonsHTML.style.display = "block";
            buttonsPython.style.display = "block";

            resultContainer.style.display = "none";
        };

        selectedImage.src = event.target.result;
    };

    reader.readAsDataURL(file);
});


// Resultaat tonen
function showResult(imageSource) {

    resultImage.src = imageSource;

    resultContainer.style.display = "block";

    downloadButton.href = imageSource;
}


// Zwart-wit
document
    .getElementById("black-white-button")
    .addEventListener("click", function () {

        if (!selectedImage) {
            return;
        }

        const result = makeBlackAndWhite(selectedImage);

        showResult(
            result.toDataURL("image/png")
        );
    });


// 180 graden draaien
document
    .getElementById("rotate-button")
    .addEventListener("click", function () {

        if (!selectedImage) {
            return;
        }

        const result = rotate180(selectedImage);

        showResult(
            result.toDataURL("image/png")
        );
    });


// Inverse colors
document
    .getElementById("inverse-button")
    .addEventListener("click", function () {

        if (!selectedImage) {
            return;
        }

        const result = makeInverseColors(selectedImage);

        showResult(
            result.toDataURL("image/png")
        );
    });


// Update displayed grid size
gridSizeSlider.addEventListener("input", function () {

    gridSizeValue.textContent = `${gridSizeSlider.value}%`;
});


// Ranked dots
document
    .getElementById("ranked-dots-button")
    .addEventListener("click", async function () {

        if (!imageUpload.files[0]) {
            return;
        }

        const file = imageUpload.files[0];

        const formData = new FormData();

        formData.append("image", file);
        formData.append(
            "grid_size_percent",
            gridSizeSlider.value
        );

        try {

            const response = await fetch(
                "/api/ranked-dots",
                {
                    method: "POST",
                    body: formData
                }
            );

            if (!response.ok) {

                console.error(
                    "Ranked dots gaf een fout:",
                    response.status
                );

                return;
            }

            const data = await response.json();

            showResult(data.image);

        } catch (error) {

            console.error(
                "Kon ranked dots niet uitvoeren:",
                error
            );
        }
    });

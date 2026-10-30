// Draaien en spiegelen: de knoppen "Draaien" (een kwartslag rechtsom) en "Spiegelen" (links-rechts).
//
// De server draait de foto (zie /api/orient in app.py) en stuurt hem terug; daarna is dat gewoon
// de foto waar alles mee werkt. Dat kan niet in de browser met een canvas, omdat sommige
// browsers een canvas bewust een beetje verstoren (tegen het volgen van bezoekers).
//
// We draaien altijd vanaf het bestand zoals het geüpload is (sourceFile), met de totale draaiing,
// zodat vaak draaien de foto niet steeds een beetje slechter maakt (JPEG).
// Een uitsnede of uitgeknipte vorm draait mee.
//
// Gebruikt uit js/jouw_kunst.js: sourceFile, orientation, originalFile, appliedCrop, appliedShape,
// showPhoto, restoreCrop, setCroppedState, renderCirclePreview, clearResult, saveProgress,
// readServerAnswer, friendlyError, track, en de elementen resultContainer en statusMessage.

const rotateButton = document.getElementById("rotate-button");
const flipButton = document.getElementById("flip-button");
const orientStatus = document.getElementById("orient-status");


rotateButton.addEventListener("click", function () {
    track("draaien");

    changeOrientation(
        { rotate: (orientation.rotate + 90) % 360, flip: orientation.flip },
        function (point) { return [1 - point[1], point[0]]; },
        function (rect) { return { x: 1 - rect.y - rect.h, y: rect.x, w: rect.h, h: rect.w }; }
    );
});


// Spiegelen na draaien is hetzelfde als eerst spiegelen en dan de andere kant op draaien.
flipButton.addEventListener("click", function () {
    track("spiegelen");

    changeOrientation(
        { rotate: (360 - orientation.rotate) % 360, flip: !orientation.flip },
        function (point) { return [1 - point[0], point[1]]; },
        function (rect) { return { x: 1 - rect.x - rect.w, y: rect.y, w: rect.w, h: rect.h }; }
    );
});


// Vraagt de server om de foto in de nieuwe stand, en draait de uitsnede en vorm mee
// (movePoint en moveRect rekenen in fracties van de foto, net als de uitsnede zelf).
async function changeOrientation(newOrientation, movePoint, moveRect) {
    if (!sourceFile) {
        return;
    }

    setOrientBusy(true);

    try {
        let file = sourceFile;

        // Terug in de beginstand: gewoon het geüploade bestand, dan hoeft de server niets te doen
        if (newOrientation.rotate !== 0 || newOrientation.flip) {
            const formData = new FormData();
            formData.append("image", sourceFile);
            formData.append("rotate", newOrientation.rotate);
            formData.append("flip", newOrientation.flip);

            const response = await fetch("/api/orient", { method: "POST", body: formData });
            const data = await readServerAnswer(response, "Draaien is mislukt.");
            const blob = await (await fetch(data.image)).blob();

            file = new File([blob], orientedFileName(sourceFile.name), { type: "image/jpeg" });
        }

        const crop = appliedCrop ? moveRect(appliedCrop) : null;
        const shape = appliedShape ? appliedShape.map(movePoint) : null;

        orientation = newOrientation;
        await showPhoto(file);      // zet de uitsnede en vorm op null

        if (crop) {
            appliedShape = shape;
            await restoreCrop(crop);
        } else {
            setCroppedState(false);
        }

        // Nieuwe invoer: het vorige resultaat hoort er niet meer bij.
        clearResult();
        resultContainer.classList.add("hidden");
        statusMessage.classList.add("hidden");
        saveProgress();

        orientStatus.classList.add("hidden");
    } catch (error) {
        orientStatus.textContent = friendlyError(error);
        orientStatus.classList.remove("hidden");
    } finally {
        setOrientBusy(false);
    }
}


function setOrientBusy(isBusy) {
    rotateButton.disabled = isBusy;
    flipButton.disabled = isBusy;

    if (isBusy) {
        orientStatus.textContent = "Even geduld, de foto wordt gedraaid...";
        orientStatus.classList.remove("hidden");
    }
}


// "vakantie.png" wordt "vakantie.jpg": de server stuurt altijd een JPEG terug.
function orientedFileName(name) {
    return (name || "foto").replace(/\.[^.]*$/, "") + ".jpg";
}

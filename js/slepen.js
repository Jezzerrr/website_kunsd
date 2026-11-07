/* ==========================================================================
   slepen.js (Jouw Kunsd)

   Op een pc staan foto's vaak in een map. Sleep je een foto ergens boven de pagina,
   dan verschijnt een melding; laat je los, dan werkt het precies alsof je hem met
   "Kies Een Foto" had gekozen. Op een telefoon gebeurt hier niets.

   Laden na jouw_kunst.js (die luistert naar het bestandsveld #image-upload).
   ========================================================================== */

(function () {
    const upload = document.getElementById("image-upload");

    if (!upload) {
        return;
    }

    // Teller, want dragenter/dragleave vuren ook bij elk element waar je overheen beweegt
    let depth = 0;

    function hasFiles(event) {
        return event.dataTransfer && Array.from(event.dataTransfer.types).includes("Files");
    }

    function stopDragging() {
        depth = 0;
        document.body.classList.remove("is-dragging");
    }

    document.addEventListener("dragenter", function (event) {
        if (!hasFiles(event)) {
            return;
        }

        depth += 1;
        document.body.classList.add("is-dragging");
    });

    document.addEventListener("dragleave", function (event) {
        if (!hasFiles(event)) {
            return;
        }

        depth -= 1;

        if (depth <= 0) {
            stopDragging();
        }
    });

    // Zonder dit opent de browser de foto zelf in plaats van hem aan de pagina te geven
    document.addEventListener("dragover", function (event) {
        if (hasFiles(event)) {
            event.preventDefault();
        }
    });

    document.addEventListener("drop", function (event) {
        if (!hasFiles(event)) {
            return;
        }

        event.preventDefault();
        stopDragging();

        const file = Array.from(event.dataTransfer.files).find(function (item) {
            return item.type.startsWith("image/");
        });

        if (!file) {
            return;
        }

        // Het bestand in het gewone bestandsveld zetten; jouw_kunst.js doet de rest
        const transfer = new DataTransfer();
        transfer.items.add(file);
        upload.files = transfer.files;
        upload.dispatchEvent(new Event("change"));

        if (typeof trackEvent === "function") {
            trackEvent("foto-gesleept");
        }
    });
})();

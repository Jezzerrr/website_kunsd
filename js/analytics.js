// Alles rond GoatCounter (bezoekersstatistieken) staat in dit bestand.
// Het moet op elke pagina geladen worden, VOOR het GoatCounter-script (count.js).
//
// Wat er geteld wordt:
//   - elk paginabezoek (doet count.js zelf, na de instelling hieronder);
//   - elke klik op een knop: met een eigen naam als een script trackEvent() aanroept,
//     anders automatisch met de id of tekst van de knop;
//   - elke klik op een link met een data-track="naam"-attribuut (bijv. de uitnodiging onderaan);
//   - elk verstuurd formulier (het contactformulier).


// ---------- Instelling voor count.js ----------

// "/" en "/index.html" zijn dezelfde pagina: tel ze onder één naam.
window.goatcounter = window.goatcounter || {};
window.goatcounter.path = function (path) {
    return path.replace(/\/index\.html$/, "/");
};


// ---------- Een gebeurtenis tellen ----------

const MAX_RETRIES = 10;
const RETRY_DELAY_MS = 500;

// Of er tijdens de huidige klik al een naam is geteld (zie het klik-luisteraartje hieronder).
let countedThisClick = false;

function trackEvent(name, retries = 0) {
    countedThisClick = true;

    if (window.goatcounter && typeof window.goatcounter.count === "function") {
        window.goatcounter.count({
            path: name,
            title: name,
            event: true
        });
        return;
    }

    // count.js wordt asynchroon geladen en is er misschien nog niet. Even later opnieuw proberen.
    // Geen fout als het nooit komt (bijv. door een adblocker of lokaal testen).
    if (retries < MAX_RETRIES) {
        setTimeout(function () {
            trackEvent(name, retries + 1);
        }, RETRY_DELAY_MS);
    }
}


// ---------- Automatisch alle knoppen tellen ----------

function slugify(text) {
    return text
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

// De naam van een knop: data-track, anders "knop-" + de id, anders zijn label of tekst.
function buttonName(button) {
    if (button.dataset.track) {
        return button.dataset.track;
    }

    const name = button.id
        || slugify(button.getAttribute("aria-label") || button.title || button.textContent);

    return "knop-" + (name || "onbekend");
}

// Eerst (in de capture-fase) vergeten we de vorige klik. Als de knop zelf trackEvent() aanroept,
// weten we daarna dat hij al geteld is en tellen we hem hieronder niet nog eens.
document.addEventListener("click", function (event) {
    if (event.target.closest("button, a[data-track]")) {
        countedThisClick = false;
    }
}, true);

document.addEventListener("click", function (event) {
    const button = event.target.closest("button, a[data-track]");

    // Verzendknoppen tellen we bij het versturen van het formulier (zie hieronder).
    if (!button || button.disabled || button.type === "submit") {
        return;
    }

    if (!countedThisClick) {
        trackEvent(buttonName(button));
    }
});


// ---------- Formulieren tellen ----------

document.addEventListener("submit", function (event) {
    trackEvent("verzonden-" + (event.target.id || "formulier"));
});

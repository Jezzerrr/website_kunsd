// Diavoorstelling op "Mijn Kunsd": twee willekeurige foto's uit mijn_kunsd/slide_show.
// De lijst met foto's komt van de server (/api/slide-show), dus een nieuwe foto in die map
// doet vanzelf mee. Elke foto komt één keer langs voordat de eerste opnieuw komt.

const slideShow = document.getElementById("slide-show");
const slideImages = [
    document.getElementById("slide-image-1"),
    document.getElementById("slide-image-2"),
];
const slideButton = document.getElementById("slide-button");

let deck = [];        // de foto's die nog aan de beurt komen, in willekeurige volgorde
let allPhotos = [];
let lastPhoto = null;


function shuffle(list) {
    const copy = list.slice();

    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }

    return copy;
}


function nextPhoto() {
    if (deck.length === 0) {
        deck = shuffle(allPhotos);

        // Niet twee keer achter elkaar dezelfde foto, ook niet bij het opnieuw schudden.
        if (deck.length > 1 && deck[deck.length - 1] === lastPhoto) {
            deck.unshift(deck.pop());
        }
    }

    lastPhoto = deck.pop();
    return lastPhoto;
}


// Zet nieuwe foto's in de vakjes en geeft een belofte terug die klaar is als ze geladen zijn.
function showNextPhotos() {
    // Met maar één foto in de map blijft het tweede vakje leeg en verborgen.
    const count = Math.min(slideImages.length, allPhotos.length);

    slideImages.forEach(function (image, index) {
        image.classList.toggle("hidden", index >= count);
    });

    return Promise.all(slideImages.slice(0, count).map(function (image) {
        return new Promise(function (resolve) {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });

            // encodeURI: bestandsnamen mogen spaties of bijzondere tekens bevatten.
            image.src = encodeURI(nextPhoto());
        });
    }));
}


async function startSlideShow() {
    try {
        const response = await fetch("/api/slide-show");
        allPhotos = await response.json();
    } catch (error) {
        // Geen server, of een server zonder deze route (oude versie, nog niet herstart):
        // de sectie blijft verborgen. In de console (F12) staat waarom.
        console.warn("Diavoorstelling: de lijst met foto's kon niet worden opgehaald.", error);
        return;
    }

    if (allPhotos.length === 0) {
        return;
    }

    // Pas laten zien als de foto's geladen zijn, anders staan er even lege kaders.
    await showNextPhotos();
    slideShow.classList.remove("hidden");

    // Bij één foto heeft de knop geen nut.
    if (allPhotos.length < 2) {
        slideButton.classList.add("hidden");
    }
}


slideButton.addEventListener("click", function () {
    if (typeof trackEvent === "function") {
        trackEvent("andere-foto");
    }

    showNextPhotos();
});


startSlideShow();

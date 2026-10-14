// ==========================================================================
// lightbox.js: klik op een kunstwerk en het opent schermvullend.
//
// Werkt voor elke afbeelding in .gallery en .featured-art op de pagina.
// - Sluiten: kruisje, Escape, of klikken naast de foto
// - Bladeren: pijltjes op het scherm, pijltjestoetsen, of vegen op een telefoon
// ==========================================================================

const zoomImages = Array.from(document.querySelectorAll(".gallery img, .featured-art img"));
let zoomIndex = 0;
let touchStartX = null;

// De vergroting zelf: één keer aanmaken, onderaan de pagina
const lightbox = document.createElement("div");
lightbox.className = "lightbox hidden";
lightbox.setAttribute("role", "dialog");
lightbox.setAttribute("aria-modal", "true");
lightbox.setAttribute("aria-label", "Vergroting");
lightbox.innerHTML = `
    <img id="lightbox-image" alt="">
    <button type="button" class="lightbox-button lightbox-close" data-track="vergroting-sluiten" aria-label="Sluiten">&times;</button>
    <button type="button" class="lightbox-button lightbox-prev" data-track="vergroting-vorige" aria-label="Vorige">&#8249;</button>
    <button type="button" class="lightbox-button lightbox-next" data-track="vergroting-volgende" aria-label="Volgende">&#8250;</button>
    <div class="lightbox-counter"></div>
`;
document.body.appendChild(lightbox);

const lightboxImage = lightbox.querySelector("#lightbox-image");
const lightboxCounter = lightbox.querySelector(".lightbox-counter");
const closeButton = lightbox.querySelector(".lightbox-close");

// Met maar één afbeelding op de pagina zijn bladerknoppen en teller zinloos
if (zoomImages.length < 2) {
    lightbox.querySelector(".lightbox-prev").hidden = true;
    lightbox.querySelector(".lightbox-next").hidden = true;
    lightboxCounter.hidden = true;
}


function showZoomImage(index) {
    // Rondgaan: na de laatste komt weer de eerste
    zoomIndex = (index + zoomImages.length) % zoomImages.length;
    const image = zoomImages[zoomIndex];

    lightboxImage.src = image.currentSrc || image.src;
    lightboxImage.alt = image.alt;
    lightboxCounter.textContent = `${zoomIndex + 1} / ${zoomImages.length}`;
}

function openLightbox(index) {
    showZoomImage(index);
    lightbox.classList.remove("hidden");
    document.body.classList.add("lightbox-open");
    closeButton.focus();
}

function closeLightbox() {
    lightbox.classList.add("hidden");
    document.body.classList.remove("lightbox-open");
    // Terug naar de afbeelding waar je was, handig voor toetsenbordgebruikers
    zoomImages[zoomIndex].focus();
}


// Elke afbeelding klikbaar (en met Enter te openen)
zoomImages.forEach(function (image, index) {
    image.classList.add("zoomable");
    image.tabIndex = 0;
    image.addEventListener("click", function () {
        openLightbox(index);
    });
    image.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            openLightbox(index);
        }
    });
});

closeButton.addEventListener("click", closeLightbox);
lightbox.querySelector(".lightbox-prev").addEventListener("click", function () {
    showZoomImage(zoomIndex - 1);
});
lightbox.querySelector(".lightbox-next").addEventListener("click", function () {
    showZoomImage(zoomIndex + 1);
});

// Klik op de donkere achtergrond (niet op de foto of een knop): sluiten
lightbox.addEventListener("click", function (event) {
    if (event.target === lightbox) {
        closeLightbox();
    }
});

document.addEventListener("keydown", function (event) {
    if (lightbox.classList.contains("hidden")) {
        return;
    }
    if (event.key === "Escape") {
        closeLightbox();
    } else if (event.key === "ArrowLeft" && zoomImages.length > 1) {
        showZoomImage(zoomIndex - 1);
    } else if (event.key === "ArrowRight" && zoomImages.length > 1) {
        showZoomImage(zoomIndex + 1);
    }
});

// Vegen op een telefoon: minstens 50 pixels opzij telt als vegen
lightbox.addEventListener("touchstart", function (event) {
    touchStartX = event.touches[0].clientX;
}, { passive: true });

lightbox.addEventListener("touchend", function (event) {
    if (touchStartX === null || zoomImages.length < 2) {
        return;
    }
    const distance = event.changedTouches[0].clientX - touchStartX;
    touchStartX = null;

    if (distance > 50) {
        showZoomImage(zoomIndex - 1);
    } else if (distance < -50) {
        showZoomImage(zoomIndex + 1);
    }
});

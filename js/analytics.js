// Hulpfunctie om klikken te tellen in GoatCounter.
// Dit bestand moet geladen worden VOOR de scripts die trackEvent() gebruiken.

function trackEvent(name) {
    // Geen fout als GoatCounter ontbreekt (bijv. door een adblocker of lokaal testen).
    if (window.goatcounter && typeof window.goatcounter.count === "function") {
        window.goatcounter.count({
            path: name,
            title: name,
            event: true
        });
    }
}

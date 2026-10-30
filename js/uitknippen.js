// Uitknippen: zelf een vorm om een stuk van de foto tekenen (bijvoorbeeld één gezicht).
// Alles buiten de vorm wordt wit, zodat een drukke of donkere achtergrond niet stoort.
//
// Zo werkt het:
// - Slepen tekent een lijn uit de vrije hand. Loslaten mag: tik of sleep daarna verder,
//   dan loopt de lijn recht door vanaf waar je was. Alleen tikken geeft dus een veelhoek.
// - Kom je terug bij het startpunt, dan gaat de vorm dicht. Of klik op OK.
// - Daarna kun je de puntjes verslepen, aan de lijn trekken voor een nieuw puntje, of
//   binnen de vorm slepen om hem te verplaatsen.
//
// De punten zijn fracties van de foto (0 t/m 1), net als de uitsnede. De server knipt
// (zie apply_cutout in app.py); hier wordt alleen getekend, zonder canvas.
//
// Gebruikt uit js/jouw_kunst.js: originalDataUrl, appliedShape, applyShape, track, clamp,
// en de elementen originalContainer en algorithmSection.

const cutoutContainer = document.getElementById("cutout-container");
const cutoutStage = document.getElementById("cutout-stage");
const cutoutImage = document.getElementById("cutout-image");
const cutoutShade = document.getElementById("cutout-shade");
const cutoutLine = document.getElementById("cutout-line");
const cutoutLineUnder = document.getElementById("cutout-line-under");
const cutoutDots = document.getElementById("cutout-dots");
const cutoutStart = document.getElementById("cutout-start");
const cutoutLoupe = document.getElementById("cutout-loupe");
const cutoutLoupePhoto = document.getElementById("cutout-loupe-photo");
const cutoutLoupeSvg = document.getElementById("cutout-loupe-svg");
const cutoutLoupeLine = document.getElementById("cutout-loupe-line");
const cutoutLoupeLineUnder = document.getElementById("cutout-loupe-line-under");
const cutoutHint = document.getElementById("cutout-hint");
const cutoutStartButton = document.getElementById("cutout-start-button");
const cutoutUndoButton = document.getElementById("cutout-undo-button");
const cutoutClearButton = document.getElementById("cutout-clear-button");
const cutoutCancelButton = document.getElementById("cutout-cancel-button");
const cutoutOkButton = document.getElementById("cutout-ok-button");

// Afstanden in schermpixels: binnen deze afstand "raak" je het startpunt, een puntje of de lijn.
// Met een vinger mag het wat ruimer.
const CUTOUT_GRAB_MOUSE = 16;
const CUTOUT_GRAB_TOUCH = 28;

// Bij uit de vrije hand tekenen: een nieuw punt na zoveel schermpixels beweging.
const CUTOUT_STEP = 3;

// Na het tekenen gaan overbodige punten eruit (Ramer-Douglas-Peucker), zolang de lijn
// minder dan zoveel verschuift: in pixels van de foto als die 1000 pixels breed (of hoog) was.
// Niet in schermpixels, anders wordt de rand op een telefoon hoekiger dan op een laptop.
const CUTOUT_SIMPLIFY = 0.8;

// Puntjes om te verslepen staan op het scherm minstens zoveel pixels uit elkaar (de rest
// is er wel, maar zonder bolletje), anders wordt de lijn één dikke kralenketting.
const CUTOUT_DOT_SPACING = 14;

// Nooit meer punten dan dit (de server accepteert er 2000).
const CUTOUT_MAX_POINTS = 1500;

// Het kleinste stuk dat je mag uitknippen, als fractie van de foto.
const CUTOUT_MIN_SIZE = 0.03;

// Het vergrootglas: grootte in schermpixels (hoogstens, en als deel van de kleinste kant
// van de foto, voor kleine schermen) en hoeveel keer vergroot.
const LOUPE_MAX_SIZE = 130;
const LOUPE_PART = 0.45;
const LOUPE_ZOOM = 2.5;

const CUTOUT_HINTS = {
    empty: "Zet je vinger of muis op de rand van wat je wilt houden en teken eromheen. " +
        "Loslaten mag: tik of teken daarna verder, dan gaat de lijn verder waar je was.",
    open: "Teken verder tot je weer bij het startpunt (het gele rondje) bent. " +
        "Of klik op OK: dan maken we de vorm vanzelf dicht.",
    closed: "Klaar! Niet helemaal goed? Versleep de puntjes, trek aan de lijn voor een extra " +
        "puntje, of sleep binnen de vorm om hem te verplaatsen. Klik daarna op OK.",
    tooFew: "Teken eerst een lijn om wat je wilt houden.",
    tooSmall: "Die vorm is wel heel klein. Teken een grotere vorm, of zoom eerst in met Bijsnijden."
};

let cutoutPoints = [];       // [[x, y], ...] als fracties van de foto
let cutoutClosed = false;
let cutoutHistory = [];      // eerdere toestanden, voor "Ongedaan Maken"
let cutoutDrag = null;


/* ---------- Openen en sluiten ---------- */

cutoutStartButton.addEventListener("click", function () {
    if (!originalDataUrl) {
        return;
    }

    track("uitknippen-start");

    cutoutImage.src = originalDataUrl;
    cutoutLoupePhoto.style.backgroundImage = `url("${originalDataUrl}")`;

    // Al eerder uitgeknipt: verder met die vorm
    cutoutPoints = appliedShape ? appliedShape.map(function (point) { return [...point]; }) : [];
    cutoutClosed = Boolean(appliedShape);
    cutoutHistory = [];
    renderCutout();

    originalContainer.classList.add("hidden");
    algorithmSection.classList.add("hidden");
    cutoutContainer.classList.remove("hidden");

    cutoutContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
});


function closeCutoutEditor() {
    cutoutDrag = null;
    cutoutLoupe.classList.add("hidden");

    cutoutContainer.classList.add("hidden");
    originalContainer.classList.remove("hidden");
    algorithmSection.classList.remove("hidden");

    originalContainer.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


cutoutCancelButton.addEventListener("click", function () {
    track("uitknippen-annuleren");
    closeCutoutEditor();
});


cutoutOkButton.addEventListener("click", function () {
    if (cutoutPoints.length < 3) {
        showCutoutHint("tooFew", true);
        return;
    }

    const xs = cutoutPoints.map(function (point) { return point[0]; });
    const ys = cutoutPoints.map(function (point) { return point[1]; });

    if (Math.max(...xs) - Math.min(...xs) < CUTOUT_MIN_SIZE ||
        Math.max(...ys) - Math.min(...ys) < CUTOUT_MIN_SIZE) {
        showCutoutHint("tooSmall", true);
        return;
    }

    track("uitknippen-ok");

    cutoutClosed = true;
    closeCutoutEditor();
    applyShape(cutoutPoints.map(function (point) { return [...point]; }));
});


cutoutClearButton.addEventListener("click", function () {
    if (!cutoutPoints.length) {
        return;
    }

    track("uitknippen-opnieuw");
    rememberCutout();
    cutoutPoints = [];
    cutoutClosed = false;
    renderCutout();
});


cutoutUndoButton.addEventListener("click", undoCutout);


// Ctrl+Z (of Cmd+Z) werkt ook, zolang het uitknippen open staat
document.addEventListener("keydown", function (event) {
    if (cutoutContainer.classList.contains("hidden")) {
        return;
    }

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undoCutout();
    }
});


function rememberCutout() {
    cutoutHistory.push({
        points: cutoutPoints.map(function (point) { return [...point]; }),
        closed: cutoutClosed
    });
}


function undoCutout() {
    const previous = cutoutHistory.pop();

    if (!previous) {
        return;
    }

    cutoutPoints = previous.points;
    cutoutClosed = previous.closed;
    renderCutout();
}


/* ---------- Tekenen en slepen ---------- */

cutoutStage.addEventListener("pointerdown", function (event) {
    // Alleen de linkermuisknop (of een aanraking).
    if (event.button !== undefined && event.button !== 0) {
        return;
    }

    const point = getCutoutPoint(event);
    const grab = event.pointerType === "touch" ? CUTOUT_GRAB_TOUCH : CUTOUT_GRAB_MOUSE;

    cutoutDrag = null;

    if (cutoutClosed) {
        const index = nearestPoint(point, grab);

        if (index >= 0) {
            rememberCutout();
            cutoutDrag = { mode: "point", index: index };
        } else {
            const segment = nearestSegment(point, grab);

            if (segment >= 0) {
                // Aan de lijn trekken: er komt een nieuw puntje bij
                rememberCutout();
                cutoutPoints.splice(segment + 1, 0, clampPoint(point));
                cutoutDrag = { mode: "point", index: segment + 1 };
            } else if (insideShape(point)) {
                rememberCutout();
                cutoutDrag = { mode: "move", last: point };
            } else {
                showCutoutHint("closed", true);
                return;
            }
        }
    } else {
        rememberCutout();

        // Terug bij het startpunt: de vorm gaat dicht
        if (cutoutPoints.length >= 3 && distanceInPixels(point, cutoutPoints[0]) <= grab) {
            cutoutClosed = true;
            renderCutout();
            return;
        }

        cutoutPoints.push(clampPoint(point));
        cutoutDrag = { mode: "draw", grab: grab, moved: false };
    }

    cutoutDrag.pointerId = event.pointerId;

    // Blijf de beweging volgen, ook als de muis of vinger buiten de foto komt.
    cutoutStage.setPointerCapture(event.pointerId);
    event.preventDefault();

    renderCutout();
    showLoupe(point);
});


cutoutStage.addEventListener("pointermove", function (event) {
    if (!cutoutDrag || event.pointerId !== cutoutDrag.pointerId) {
        return;
    }

    const point = getCutoutPoint(event);

    if (cutoutDrag.mode === "draw") {
        const last = cutoutPoints[cutoutPoints.length - 1];

        if (distanceInPixels(point, last) >= CUTOUT_STEP && cutoutPoints.length < CUTOUT_MAX_POINTS) {
            cutoutPoints.push(clampPoint(point));
            cutoutDrag.moved = true;
        }
    } else if (cutoutDrag.mode === "point") {
        cutoutPoints[cutoutDrag.index] = clampPoint(point);
    } else if (cutoutDrag.mode === "move") {
        moveShape(point[0] - cutoutDrag.last[0], point[1] - cutoutDrag.last[1]);
        cutoutDrag.last = point;
    }

    renderCutout();
    showLoupe(point);
});


function endCutoutDrag(event) {
    if (!cutoutDrag || event.pointerId !== cutoutDrag.pointerId) {
        return;
    }

    if (cutoutDrag.mode === "draw") {
        cutoutPoints = simplifyLine(cutoutPoints, CUTOUT_SIMPLIFY);

        // Geëindigd bij het startpunt: dicht. Het laatste stukje bij het startpunt hoeft niet.
        const first = cutoutPoints[0];
        const last = cutoutPoints[cutoutPoints.length - 1];

        if (cutoutDrag.moved && cutoutPoints.length >= 4 &&
            distanceInPixels(first, last) <= cutoutDrag.grab) {
            cutoutPoints.pop();
            cutoutClosed = true;
        }
    }

    cutoutDrag = null;
    cutoutLoupe.classList.add("hidden");
    renderCutout();
}


cutoutStage.addEventListener("pointerup", endCutoutDrag);
cutoutStage.addEventListener("pointercancel", endCutoutDrag);


// De hele vorm verschuiven, maar niet buiten de foto.
function moveShape(dx, dy) {
    const xs = cutoutPoints.map(function (point) { return point[0]; });
    const ys = cutoutPoints.map(function (point) { return point[1]; });

    dx = clamp(dx, -Math.min(...xs), 1 - Math.max(...xs));
    dy = clamp(dy, -Math.min(...ys), 1 - Math.max(...ys));

    cutoutPoints = cutoutPoints.map(function (point) {
        return [point[0] + dx, point[1] + dy];
    });
}


/* ---------- Rekenwerk ---------- */

// Muis- of vingerpositie als fractie van de foto (kan buiten 0-1 vallen).
function getCutoutPoint(event) {
    const bounds = cutoutStage.getBoundingClientRect();

    return [
        (event.clientX - bounds.left) / bounds.width,
        (event.clientY - bounds.top) / bounds.height
    ];
}


function clampPoint(point) {
    return [clamp(point[0], 0, 1), clamp(point[1], 0, 1)];
}


// Afstand tussen twee punten in schermpixels (de foto is meestal niet vierkant).
function distanceInPixels(a, b) {
    const bounds = cutoutStage.getBoundingClientRect();
    return Math.hypot((a[0] - b[0]) * bounds.width, (a[1] - b[1]) * bounds.height);
}


// Het dichtstbijzijnde puntje binnen maxDistance schermpixels, of -1.
function nearestPoint(point, maxDistance) {
    let best = -1;
    let bestDistance = maxDistance;

    cutoutPoints.forEach(function (other, index) {
        const distance = distanceInPixels(point, other);

        if (distance <= bestDistance) {
            best = index;
            bestDistance = distance;
        }
    });

    return best;
}


// Het dichtstbijzijnde stuk lijn (van punt i naar punt i + 1) binnen maxDistance, of -1.
function nearestSegment(point, maxDistance) {
    const bounds = cutoutStage.getBoundingClientRect();
    const px = point[0] * bounds.width;
    const py = point[1] * bounds.height;

    let best = -1;
    let bestDistance = maxDistance;

    cutoutPoints.forEach(function (a, index) {
        const b = cutoutPoints[(index + 1) % cutoutPoints.length];
        const distance = distanceToSegment(px, py,
            a[0] * bounds.width, a[1] * bounds.height, b[0] * bounds.width, b[1] * bounds.height);

        if (distance <= bestDistance) {
            best = index;
            bestDistance = distance;
        }
    });

    return best;
}


function distanceToSegment(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSquared = dx * dx + dy * dy;
    const t = lengthSquared ? clamp(((px - ax) * dx + (py - ay) * dy) / lengthSquared, 0, 1) : 0;

    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}


// Ligt het punt binnen de vorm? (even-odd, net als het knippen zelf)
function insideShape(point) {
    let inside = false;

    for (let i = 0, j = cutoutPoints.length - 1; i < cutoutPoints.length; j = i++) {
        const [xi, yi] = cutoutPoints[i];
        const [xj, yj] = cutoutPoints[j];

        if ((yi > point[1]) !== (yj > point[1]) &&
            point[0] < (xj - xi) * (point[1] - yi) / (yj - yi) + xi) {
            inside = !inside;
        }
    }

    return inside;
}


// Ramer-Douglas-Peucker: laat punten weg zolang de lijn minder dan tolerance pixels verschuift.
function simplifyLine(points, tolerance) {
    if (points.length < 3) {
        return points;
    }

    // De foto alsof hij 1000 pixels op de langste zijde is
    const naturalWidth = cutoutImage.naturalWidth || 1;
    const naturalHeight = cutoutImage.naturalHeight || 1;
    const scale = 1000 / Math.max(naturalWidth, naturalHeight);
    const bounds = { width: naturalWidth * scale, height: naturalHeight * scale };

    const keep = new Array(points.length).fill(false);
    const stack = [[0, points.length - 1]];

    keep[0] = true;
    keep[points.length - 1] = true;

    while (stack.length) {
        const [start, end] = stack.pop();
        const a = points[start];
        const b = points[end];

        let farthest = -1;
        let farthestDistance = tolerance;

        for (let i = start + 1; i < end; i++) {
            const distance = distanceToSegment(
                points[i][0] * bounds.width, points[i][1] * bounds.height,
                a[0] * bounds.width, a[1] * bounds.height, b[0] * bounds.width, b[1] * bounds.height);

            if (distance > farthestDistance) {
                farthest = i;
                farthestDistance = distance;
            }
        }

        if (farthest >= 0) {
            keep[farthest] = true;
            stack.push([start, farthest], [farthest, end]);
        }
    }

    return points.filter(function (point, index) {
        return keep[index];
    });
}


/* ---------- Tekenen op het scherm ---------- */

function renderCutout() {
    const line = linePath(cutoutPoints, cutoutClosed);

    cutoutLine.setAttribute("d", line);
    cutoutLineUnder.setAttribute("d", line);
    cutoutLoupeLine.setAttribute("d", line);
    cutoutLoupeLineUnder.setAttribute("d", line);

    // Dicht: alles buiten de vorm wordt bijna wit, zoals het straks wordt
    cutoutShade.setAttribute("d", cutoutClosed ? "M0 0H1V1H0Z " + line : "");

    // Puntjes om te verslepen (een heel kort lijntje met ronde uiteinden is een rondje)
    cutoutDots.setAttribute("d", cutoutClosed ? visibleDots().map(dotPath).join(" ") : "");
    cutoutStart.setAttribute("d", !cutoutClosed && cutoutPoints.length ? dotPath(cutoutPoints[0]) : "");

    cutoutUndoButton.disabled = cutoutHistory.length === 0;
    cutoutClearButton.disabled = cutoutPoints.length === 0;

    showCutoutHint(cutoutClosed ? "closed" : (cutoutPoints.length ? "open" : "empty"), false);
}


function linePath(points, closed) {
    if (!points.length) {
        return "";
    }

    const parts = points.map(function (point, index) {
        return `${index ? "L" : "M"}${point[0].toFixed(5)} ${point[1].toFixed(5)}`;
    });

    return parts.join("") + (closed ? "Z" : "");
}


// De puntjes die een bolletje krijgen: niet te dicht op elkaar op het scherm.
function visibleDots() {
    const dots = [];

    cutoutPoints.forEach(function (point) {
        const last = dots[dots.length - 1];

        if (!last || distanceInPixels(point, last) >= CUTOUT_DOT_SPACING) {
            dots.push(point);
        }
    });

    // Ook het laatste niet vlak naast het eerste
    if (dots.length > 2 && distanceInPixels(dots[0], dots[dots.length - 1]) < CUTOUT_DOT_SPACING) {
        dots.pop();
    }

    return dots;
}


function dotPath(point) {
    return `M${point[0].toFixed(5)} ${point[1].toFixed(5)}l0.00001 0`;
}


function showCutoutHint(name, isWarning) {
    cutoutHint.textContent = CUTOUT_HINTS[name];
    cutoutHint.classList.toggle("cutout-hint-warning", isWarning);
}


// Het vergrootglas laat zien wat er onder je vinger zit. Het staat bovenin, aan de andere
// kant van de foto dan je vinger.
function showLoupe(point) {
    const bounds = cutoutStage.getBoundingClientRect();
    const size = Math.round(Math.min(LOUPE_MAX_SIZE, LOUPE_PART * Math.min(bounds.width, bounds.height)));
    const zoomedWidth = bounds.width * LOUPE_ZOOM;
    const zoomedHeight = bounds.height * LOUPE_ZOOM;

    cutoutLoupe.style.width = `${size}px`;
    cutoutLoupe.style.height = `${size}px`;
    cutoutLoupe.classList.toggle("cutout-loupe-right", point[0] < 0.5);

    cutoutLoupePhoto.style.backgroundSize = `${zoomedWidth}px ${zoomedHeight}px`;
    cutoutLoupePhoto.style.backgroundPosition =
        `${size / 2 - point[0] * zoomedWidth}px ${size / 2 - point[1] * zoomedHeight}px`;

    // Dezelfde lijn, ingezoomd: een kleiner stukje van de foto (in fracties) op dezelfde plek
    const viewWidth = size / zoomedWidth;
    const viewHeight = size / zoomedHeight;
    cutoutLoupeSvg.setAttribute("viewBox",
        `${point[0] - viewWidth / 2} ${point[1] - viewHeight / 2} ${viewWidth} ${viewHeight}`);

    cutoutLoupe.classList.remove("hidden");
}

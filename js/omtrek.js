// Omtrek: van een masker (per pixel een getal van 0 t/m 1) naar een vorm voor Uitknippen.
//
// Gebruikt door js/achtergrond.js (het masker komt van het rekenmodel) en js/uitknippen.js
// (Stuk Wegknippen en Stuk Toevoegen: de vorm en het getekende stuk worden samen een masker).
//
// Zo werkt het:
// - Optioneel eerst het masker vervagen (smooth, in pixels). Na de drempel geeft dat een rustige
//   rand: dunne uitsteeksels en kleine inhammen verdwijnen.
// - Pixels boven de drempel horen erbij. Alleen het grootste aaneengesloten stuk telt.
// - Daar lopen we met de klok mee omheen (alleen de buitenrand: gaten blijven dicht, net als
//   bij Uitknippen), en daarna gaan overbodige punten eruit (Douglas-Peucker).
// - De punten zijn fracties (0 t/m 1) van het masker.


// Geeft [[x, y], ...] of null als er geen stuk is dat minstens minArea (fractie) groot is.
function outlineFromMask(values, width, height, options) {
    const threshold = options.threshold === undefined ? 0.5 : options.threshold;
    const minArea = options.minArea || 0;
    const tolerance = options.tolerance || 1;
    const maxPoints = options.maxPoints || 1000;

    const smooth = Math.round(options.smooth || 0);
    const source = smooth > 0 ? outlineBlur(values, width, height, smooth) : values;

    // Een rand van één lege pixel eromheen, dan hoeft het omtrekvolgen nooit op de rand te letten.
    const paddedWidth = width + 2;
    const paddedHeight = height + 2;
    const inside = new Uint8Array(paddedWidth * paddedHeight);

    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            if (source[y * width + x] >= threshold) {
                inside[(y + 1) * paddedWidth + x + 1] = 1;
            }
        }
    }

    const region = outlineLargestRegion(inside, paddedWidth, paddedHeight);

    if (!region || region.size < Math.max(4, minArea * width * height)) {
        return null;
    }

    const boundary = outlineTrace(region.mask, paddedWidth, region.start);

    if (boundary.length < 3) {
        return null;
    }

    const simple = outlineSimplifyClosed(boundary, tolerance, maxPoints);

    if (simple.length < 3) {
        return null;
    }

    // Middelpunt van de pixel, zonder de lege rand, als fractie
    return simple.map(function (point) {
        return [
            Math.min(Math.max((point[0] - 1 + 0.5) / width, 0), 1),
            Math.min(Math.max((point[1] - 1 + 0.5) / height, 0), 1)
        ];
    });
}


// Twee keer een snelle vervaging met een vierkantje (eerst horizontaal, dan verticaal):
// samen bijna een Gauss-vervaging.
function outlineBlur(values, width, height, radius) {
    let current = Float32Array.from(values);
    const scratch = new Float32Array(current.length);

    for (let pass = 0; pass < 2; pass++) {
        outlineBoxBlur(current, scratch, width, height, radius, 1, width);
        outlineBoxBlur(scratch, current, height, width, radius, width, 1);
    }

    return current;
}


// Vervaagt in één richting. count lijnen van length pixels; step is de afstand tussen buren
// in een lijn, lineStep die tussen het begin van twee lijnen. Buiten de rand telt als 0.
function outlineBoxBlur(source, target, length, count, radius, step, lineStep) {
    const size = 2 * radius + 1;

    for (let line = 0; line < count; line++) {
        const base = line * lineStep;
        let sum = 0;

        for (let i = 0; i <= radius && i < length; i++) {
            sum += source[base + i * step];
        }

        for (let i = 0; i < length; i++) {
            target[base + i * step] = sum / size;

            const enter = i + radius + 1;
            const leave = i - radius;

            if (enter < length) {
                sum += source[base + enter * step];
            }
            if (leave >= 0) {
                sum -= source[base + leave * step];
            }
        }
    }
}


// Het grootste aaneengesloten gebied (buren boven, onder, links, rechts), als eigen masker,
// en de eerste pixel ervan (bovenste rij, meest links): daar begint het omtrekvolgen.
function outlineLargestRegion(inside, width, height) {
    const labels = new Int32Array(inside.length);
    const stack = new Int32Array(inside.length);
    let best = null;
    let label = 0;

    for (let start = 0; start < inside.length; start++) {
        if (!inside[start] || labels[start]) {
            continue;
        }

        label += 1;
        labels[start] = label;
        let top = 0;
        let size = 0;
        stack[top++] = start;

        while (top > 0) {
            const index = stack[--top];
            size += 1;

            const neighbours = [index - 1, index + 1, index - width, index + width];

            for (const next of neighbours) {
                if (inside[next] && !labels[next]) {
                    labels[next] = label;
                    stack[top++] = next;
                }
            }
        }

        if (!best || size > best.size) {
            best = { label: label, size: size, start: start };
        }
    }

    if (!best) {
        return null;
    }

    const mask = new Uint8Array(inside.length);

    for (let index = 0; index < labels.length; index++) {
        if (labels[index] === best.label) {
            mask[index] = 1;
        }
    }

    return { mask: mask, size: best.size, start: best.start };
}


// Loopt met de klok mee langs de buitenrand van het gebied (Moore-buren, met de stopregel van
// Jacob: klaar als we het beginpunt weer op dezelfde manier binnenkomen).
// De acht richtingen, met de klok mee: oost, zuidoost, zuid, zuidwest, west, noordwest, noord, noordoost.
const OUTLINE_DX = [1, 1, 0, -1, -1, -1, 0, 1];
const OUTLINE_DY = [0, 1, 1, 1, 0, -1, -1, -1];

function outlineTrace(mask, width, start) {
    const points = [];
    const maxSteps = mask.length * 4;

    let current = start;
    // De beginpixel is de eerste in leesvolgorde, dus links ervan is leeg: daar komen we vandaan.
    let back = 4;
    const startBack = back;

    for (let step = 0; step < maxSteps; step++) {
        points.push([current % width, Math.floor(current / width)]);

        let found = -1;

        for (let turn = 1; turn <= 8; turn++) {
            const direction = (back + turn) % 8;
            const next = current + OUTLINE_DX[direction] + OUTLINE_DY[direction] * width;

            if (mask[next]) {
                found = direction;
                break;
            }
        }

        // Eén losse pixel: geen rand om te volgen
        if (found < 0) {
            break;
        }

        // De lege buur net vóór de gevonden pixel wordt het nieuwe "achter", gezien vanaf die pixel.
        const previous = (found + 7) % 8;
        const next = current + OUTLINE_DX[found] + OUTLINE_DY[found] * width;
        const emptyX = (current % width) + OUTLINE_DX[previous];
        const emptyY = Math.floor(current / width) + OUTLINE_DY[previous];

        back = outlineDirection(emptyX - next % width, emptyY - Math.floor(next / width));
        current = next;

        if (current === start && back === startBack) {
            break;
        }
    }

    return points;
}


function outlineDirection(dx, dy) {
    for (let direction = 0; direction < 8; direction++) {
        if (OUTLINE_DX[direction] === dx && OUTLINE_DY[direction] === dy) {
            return direction;
        }
    }

    return 4;
}


// Minder punten met (bijna) dezelfde vorm, voor een gesloten rand.
// Te veel punten over? Dan iets grover, tot het past.
function outlineSimplifyClosed(points, tolerance, maxPoints) {
    // Begin bij het eerste punt en het punt dat daar het verst vandaan ligt: twee open stukken.
    let far = 0;
    let farDistance = -1;

    for (let index = 1; index < points.length; index++) {
        const dx = points[index][0] - points[0][0];
        const dy = points[index][1] - points[0][1];
        const distance = dx * dx + dy * dy;

        if (distance > farDistance) {
            farDistance = distance;
            far = index;
        }
    }

    let result = points;

    for (let attempt = 0; attempt < 20; attempt++) {
        const first = outlineSimplifyOpen(points.slice(0, far + 1), tolerance);
        const second = outlineSimplifyOpen(points.slice(far).concat([points[0]]), tolerance);

        // Beide stukken delen hun eindpunten: die maar één keer houden
        result = first.slice(0, -1).concat(second.slice(0, -1));

        if (result.length <= maxPoints) {
            break;
        }

        tolerance *= 1.5;
    }

    return result;
}


function outlineSimplifyOpen(points, tolerance) {
    if (points.length <= 2) {
        return points.slice();
    }

    const keep = new Uint8Array(points.length);
    keep[0] = 1;
    keep[points.length - 1] = 1;

    const ranges = [[0, points.length - 1]];

    while (ranges.length > 0) {
        const [first, last] = ranges.pop();
        let worst = -1;
        let worstDistance = tolerance;

        for (let index = first + 1; index < last; index++) {
            const distance = outlineDistanceToLine(points[index], points[first], points[last]);

            if (distance > worstDistance) {
                worstDistance = distance;
                worst = index;
            }
        }

        if (worst >= 0) {
            keep[worst] = 1;
            ranges.push([first, worst], [worst, last]);
        }
    }

    return points.filter(function (point, index) {
        return keep[index];
    });
}


function outlineDistanceToLine(point, start, end) {
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const length = Math.hypot(dx, dy);

    if (length === 0) {
        return Math.hypot(point[0] - start[0], point[1] - start[1]);
    }

    return Math.abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / length;
}

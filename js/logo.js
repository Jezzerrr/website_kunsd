/* ---------- KUNSD: het wisselende logo ----------
   Bij elke paginaweergave wordt hier een nieuw logo opgebouwd (geen vaste lijst om uit te kiezen).
   De regels liggen vast, de uitkomst is elke keer anders:
   - de letters KUNSD (Syne, extra vet) zijn altijd hetzelfde;
   - een verschoven raster van driehoeken verdeelt het woord in vlakken (zoals Shape Division);
   - elk vlak krijgt een willekeurige kleur uit zwart, rood, geel en blauw (zwart iets vaker);
   - de naden tussen de vlakken zijn echte gaten (via een masker), dus het logo werkt op elke achtergrond.
   Kost minder dan een milliseconde. Zonder JavaScript zie je het vaste logo (versie 1956).

   Gebruik in de html: een element met data-kunsd-logo, met daarin het vaste logo als <img>:
     <a href="/" class="nav-logo" data-kunsd-logo aria-label="KUNSD, naar de homepagina">
         <img src="/mijn_kunsd/logo/kunsd-logo-kleur.svg" alt="" width="140" height="18">
     </a>
   Het script vervangt de <img> door een nieuw logo. Met de muis erover (of met Tab erop) veegt er
   een nieuwe versie overheen.
   Extra: KunsdLogo.make(versienummer) maakt altijd dezelfde versie; versie 1956 is het vaste logo. */

(function () {
    "use strict";

    // De vijf letters als SVG-paden (Syne 800), in een vlak van 600 x 200
    var LETTERS = ["M72.9 100.5V95.6L123.6 128.2H90.9L47.8 98.3L87.6 71.9H118.9ZM26 71.9H48V128.2H26Z","M216.3 96.1V71.9H238.3V100Q238.3 107.5 235.5 112.8Q232.7 118 227.8 121.4Q222.9 124.8 216.5 126.6Q210 128.4 202.7 129.2Q195.4 129.9 187.8 129.9Q179.8 129.9 172.3 129.2Q164.8 128.4 158.5 126.6Q152.1 124.8 147.3 121.4Q142.6 118 139.9 112.8Q137.2 107.5 137.2 100V71.9H159.2V96.1Q159.2 103.1 162.6 106.8Q166.1 110.5 172.5 111.9Q178.8 113.2 187.8 113.2Q196.5 113.2 202.9 111.9Q209.3 110.5 212.8 106.8Q216.3 103.1 216.3 96.1Z","M343.2 110.9 335 115.6V71.9H357V128.2H335L268.8 89.8L277 85.1V128.2H255V71.9H277Z","M370.6 107.5H394.6Q395.2 109.4 398.2 110.6Q401.2 111.9 406.3 112.6Q411.3 113.2 418 113.2Q424.6 113.2 428.4 112.8Q432.3 112.4 433.8 111.4Q435.4 110.4 435.4 108.7Q435.4 107 432.9 106.1Q430.3 105.1 423.8 104.8Q417.3 104.4 405.5 104.4Q396.7 104.4 390.4 103.6Q384 102.8 379.9 101Q375.8 99.2 373.9 96.4Q371.9 93.6 371.9 89.8Q371.9 83.1 376.5 78.7Q381 74.4 390.2 72.2Q399.4 70.1 413.2 70.1Q433.4 70.1 444.1 75.9Q454.8 81.8 454.8 92.7H432Q431.5 89.8 426.5 88.3Q421.5 86.8 412.3 86.8Q403.1 86.8 398.7 87.8Q394.3 88.9 394.3 91.4Q394.3 92.7 395.5 93.5Q396.7 94.3 399.8 94.8Q402.8 95.3 408.3 95.5Q413.9 95.6 422.4 95.6Q431.8 95.6 438.4 96.6Q445 97.5 449.1 99.3Q453.2 101.2 455 104Q456.9 106.9 456.9 110.8Q456.9 117.5 452.7 121.7Q448.4 125.9 439.3 127.9Q430.1 129.9 415.4 129.9Q407 129.9 400 129Q393 128 387.6 126.1Q382.1 124.2 378.3 121.5Q374.6 118.7 372.6 115.2Q370.6 111.7 370.6 107.5Z","M534.3 71.9Q546.1 71.9 553.9 74.2Q561.6 76.5 566 80.4Q570.4 84.4 572.2 89.4Q574 94.5 574 100Q574 105.6 572 110.6Q570 115.7 565.3 119.7Q560.7 123.6 553.1 125.9Q545.5 128.2 534.3 128.2H470.9V71.9ZM492.9 110.6H533.4Q538.3 110.6 541.7 109.9Q545.2 109.3 547.2 108Q549.3 106.6 550.2 104.7Q551.1 102.7 551.1 100Q551.1 97.4 550.2 95.4Q549.3 93.4 547.2 92.1Q545.2 90.8 541.7 90.2Q538.3 89.5 533.4 89.5H492.9Z"];
    var PALETTE = ["#171717", "#d7263d", "#e9a80c", "#2b59c3"];   // zwart, rood, geel, blauw
    var WEIGHTS = [2, 1, 1, 1];                                   // zwart komt twee keer zo vaak voor
    var BOX = {x0: 26, x1: 574, y0: 70, y1: 130};                 // waar het woord staat
    var VIEWBOX = "20 64 560 72";
    var GAP = 1.4;                                                // breedte van de naden
    var LETTER_D = LETTERS.join("");
    var counter = 0;                                              // voor unieke id's van maskers

    // Toevalsgenerator met een startgetal, zodat een versienummer altijd hetzelfde logo geeft
    function rng(seed) {
        var a = seed >>> 0;
        return function () {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }

    function pickColor(r) {
        var x = r() * 5;                                          // 5 = som van WEIGHTS
        for (var i = 0; i < PALETTE.length; i++) {
            x -= WEIGHTS[i];
            if (x <= 0) return i;
        }
        return 0;
    }

    /* Eén versie maken. Normaal: maaswijdte 66 tot 84 (een paar naden per letter).
       special: true geeft een uitschieter, net zo druk als ontwerp 4 (maaswijdte 40 tot 46). */
    function make(seed, opts) {
        opts = opts || {};
        var r = rng(seed), sp = !!opts.special;
        var st = sp ? 40 + r() * 6 : 66 + r() * 18, jit = st * 0.33;
        var ox = BOX.x0 - st * (0.3 + r() * 0.7), oy = BOX.y0 - st * (0.2 + r() * 0.8);
        var nx = Math.ceil((BOX.x1 + 20 - ox) / st) + 1, ny = Math.ceil((BOX.y1 + 20 - oy) / st) + 1;
        var P = [], i, j;
        for (j = 0; j <= ny; j++) {
            var row = [];
            for (i = 0; i <= nx; i++) {
                row.push([ox + i * st + (r() - 0.5) * 2 * jit, oy + j * st + (r() - 0.5) * 2 * jit]);
            }
            P.push(row);
        }
        // Elk vak in twee driehoeken, om en om in de andere richting: zo komen naden in punten samen
        var flip = r() < 0.5 ? 0 : 1, faces = [];
        for (j = 0; j < ny; j++) {
            for (i = 0; i < nx; i++) {
                var a = P[j][i], b = P[j][i + 1], c = P[j + 1][i + 1], d = P[j + 1][i];
                var tris = (i + j + flip) % 2 ? [[a, b, c], [a, c, d]] : [[a, b, d], [b, c, d]];
                for (var k = 0; k < 2; k++) faces.push({pts: tris[k], col: pickColor(r)});
            }
        }
        return {faces: faces, seed: seed, special: sp};
    }

    function f1(v) { return Math.round(v * 10) / 10; }
    function poly(pts) {
        return "M" + pts.map(function (p) { return f1(p[0]) + " " + f1(p[1]); }).join("L") + "Z";
    }

    // Eén laag: gekleurde vlakken, zichtbaar door een masker (letters min de naden)
    function layer(state, mono, extraLine) {
        var id = "kunsd-logo-" + (++counter);
        var seams = state.faces.map(function (f) { return poly(f.pts); }).join("");
        var s = '<mask id="' + id + '" maskUnits="userSpaceOnUse" x="0" y="0" width="600" height="200">' +
            '<path d="' + LETTER_D + '" fill="#fff"/>' +
            '<path d="' + seams + '" fill="none" stroke="#000" stroke-width="' + GAP + '" stroke-linejoin="round"/>' +
            (extraLine ? '<path d="' + extraLine + '" fill="none" stroke="#000" stroke-width="' + (GAP + 0.6) + '"/>' : "") +
            '</mask><g mask="url(#' + id + ')">';
        state.faces.forEach(function (f) {
            s += '<path d="' + poly(f.pts) + '" fill="' + (mono || PALETTE[f.col]) + '"/>';
        });
        return s + "</g>";
    }

    function wrap(inner) {
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + VIEWBOX +
            '" role="img" aria-label="KUNSD" focusable="false">' + inner + "</svg>";
    }

    // Het hele logo als SVG-tekst. mono: een kleur (bijv. "#000") voor de zwart-witversie
    function svg(state, mono) { return wrap(layer(state, mono)); }

    // Tussenstand van de veeg-animatie: links (of rechts) van de witte naad al de nieuwe versie
    function wipe(A, B, t, dir) {
        var slant = 18, W = BOX.x1 - BOX.x0 + 2 * slant + 40;
        var x = dir > 0 ? BOX.x0 - slant - 20 + W * t : BOX.x1 + slant + 20 - W * t;
        var top = [x + slant, 40], bot = [x - slant, 160];
        var newSide = dir > 0 ? [[-100, 40], top, bot, [-100, 160]] : [[700, 40], top, bot, [700, 160]];
        var oldSide = dir > 0 ? [top, [700, 40], [700, 160], bot] : [top, [-100, 40], [-100, 160], bot];
        var line = "M" + f1(top[0]) + " 40L" + f1(bot[0]) + " 160";
        var id = "kunsd-wipe-" + (++counter);
        return wrap('<clipPath id="' + id + 'n"><path d="' + poly(newSide) + '"/></clipPath>' +
            '<clipPath id="' + id + 'o"><path d="' + poly(oldSide) + '"/></clipPath>' +
            '<g clip-path="url(#' + id + 'o)">' + layer(A, null, line) + "</g>" +
            '<g clip-path="url(#' + id + 'n)">' + layer(B, null, line) + "</g>");
    }

    function randomSeed() { return 1 + Math.floor(Math.random() * 99999); }

    // Af en toe (ongeveer 1 op de 20 keer) een uitschieter: net zo druk als ontwerp 4
    var UITSCHIETER_KANS = 1 / 20;
    function randomLogo() { return make(randomSeed(), {special: Math.random() < UITSCHIETER_KANS}); }

    // Laat in element el een nieuwe versie overheen vegen (ongeveer een seconde)
    function animateTo(el, from, to, dir, done) {
        var t0 = null, MOVE = 900;
        function ease(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
        function step(now) {
            if (t0 === null) t0 = now;
            var p = Math.min(1, (now - t0) / MOVE);
            el.innerHTML = p < 1 ? wipe(from, to, ease(p), dir) : svg(to);
            if (p < 1) requestAnimationFrame(step); else if (done) done();
        }
        requestAnimationFrame(step);
    }

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function setup(el) {
        var state = randomLogo();
        el.innerHTML = svg(state);
        el.setAttribute("data-logo-versie", state.seed + (state.special ? " uitschieter" : ""));
        if (reduceMotion) return;
        var busy = false, dir = 1;
        function renew() {
            if (busy) return;
            busy = true;
            var next = randomLogo();
            animateTo(el, state, next, dir, function () {
                state = next; busy = false;
                el.setAttribute("data-logo-versie", state.seed + (state.special ? " uitschieter" : ""));
            });
            dir = -dir;
        }
        el.addEventListener("mouseenter", renew);
        el.addEventListener("focus", renew);
    }

    // Beschikbaar voor andere scripts (bijvoorbeeld later een wachtscherm)
    window.KunsdLogo = {make: make, svg: svg, wipe: wipe, animateTo: animateTo, randomSeed: randomSeed, randomLogo: randomLogo, PALETTE: PALETTE};

    var els = document.querySelectorAll("[data-kunsd-logo]");
    for (var n = 0; n < els.length; n++) setup(els[n]);
})();

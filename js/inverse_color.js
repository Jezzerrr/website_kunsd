function makeInverseColors(image) {

    const canvas = document.createElement("canvas");

    const context = canvas.getContext("2d");


    // Gebruik de oorspronkelijke afmetingen

    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;


    // Teken de originele afbeelding

    context.drawImage(
        image,
        0,
        0
    );


    // Haal alle pixels op

    const imageData = context.getImageData(
        0,
        0,
        canvas.width,
        canvas.height
    );

    const pixels = imageData.data;


    // Loop door alle pixels

    for (let i = 0; i < pixels.length; i += 4) {

        // Inverseer R, G en B

        pixels[i] = 255 - pixels[i];

        pixels[i + 1] = 255 - pixels[i + 1];

        pixels[i + 2] = 255 - pixels[i + 2];

        // Alpha blijft hetzelfde
    }


    // Zet de aangepaste pixels terug

    context.putImageData(
        imageData,
        0,
        0
    );


    // Geef het resultaat terug

    return canvas;
}

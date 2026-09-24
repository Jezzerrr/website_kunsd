function makeBlackAndWhite(image) {

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

        const red = pixels[i];
        const green = pixels[i + 1];
        const blue = pixels[i + 2];


        // Bereken de grijswaarde

        const gray =
            0.299 * red +
            0.587 * green +
            0.114 * blue;


        // Maak R, G en B gelijk

        pixels[i] = gray;
        pixels[i + 1] = gray;
        pixels[i + 2] = gray;

        // pixels[i + 3] is alpha
        // Die laten we ongemoeid.
    }


    // Zet de pixels terug

    context.putImageData(
        imageData,
        0,
        0
    );


    // Geef het resultaat terug

    return canvas;
}

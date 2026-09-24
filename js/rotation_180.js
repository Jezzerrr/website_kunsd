function rotate180(image) {

    const canvas = document.createElement("canvas");

    const context = canvas.getContext("2d");


    // Zelfde afmetingen als de originele foto

    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;


    // Verplaats het nulpunt naar het midden

    context.translate(
        canvas.width / 2,
        canvas.height / 2
    );


    // Draai 180 graden

    context.rotate(Math.PI);


    // Teken de afbeelding vanuit het midden

    context.drawImage(
        image,
        -image.naturalWidth / 2,
        -image.naturalHeight / 2
    );


    // Geef het resultaat terug

    return canvas;
}

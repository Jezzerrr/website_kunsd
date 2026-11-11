import numpy as np
from PIL import Image, ImageDraw


SHAPES = {
    "squares",
    "brick",
    "triangles",
    "hexagons",
    "rhombi",
    "cubes",
    "octagons_squares",
    "crosses",
    "arrows",
    "truchet",
    "fish_scales",
}


def image_to_shapes(
    img,
    grid_size=20,
    max_colors=16,
    shape="squares",
    fill=True,
    outline=None,
    outline_width=1,
    seed=None,
):
    """
    Convert an image into a coloured or empty tessellation.

    Available shapes:
        squares
        brick
        triangles
        hexagons
        rhombi
        cubes
        octagons_squares
        crosses
        arrows
        truchet
        fish_scales

    Parameters
    ----------
    img : PIL.Image.Image
        Input image.

    grid_size : int or float
        Approximate tile size.

    max_colors : int
        Maximum number of colours when fill=True.

    shape : str
        Tessellation pattern.

    fill : bool
        Fill the shapes using colours derived from the input image.
        If False, the shapes remain white.

    outline : colour or None
        Optional outline colour.
        If fill=False and outline=None, black is used.

    outline_width : int
        Width of outlines.

    seed : int or None
        Random seed used by the Truchet pattern.
    """

    if grid_size <= 0:
        raise ValueError("grid_size must be greater than 0")

    if not 1 <= max_colors <= 256:
        raise ValueError("max_colors must be between 1 and 256")

    if outline_width < 1:
        raise ValueError("outline_width must be at least 1")

    if shape not in SHAPES:
        raise ValueError(
            f"shape must be one of: {', '.join(sorted(SHAPES))}"
        )

    img = img.convert("RGB")
    img_array = np.array(img)
    width, height = img.size

    if shape == "truchet":
        return render_truchet(
            img_array=img_array,
            width=width,
            height=height,
            grid_size=grid_size,
            max_colors=max_colors,
            fill=fill,
            outline=outline,
            outline_width=outline_width,
            seed=seed,
        )

    polygons = create_polygons(
        width=width,
        height=height,
        grid_size=grid_size,
        shape=shape,
    )

    polygons = [
        polygon
        for polygon in polygons
        if polygon_intersects_image(
            polygon,
            width,
            height,
        )
    ]

    output = Image.new(
        "RGB",
        (width, height),
        "white",
    )

    draw = ImageDraw.Draw(output)

    if not fill:
        outline_color = (
            outline
            if outline is not None
            else "black"
        )

        for polygon in polygons:
            draw.polygon(
                polygon,
                fill="white",
                outline=outline_color,
                width=outline_width,
            )

        return output

    average_colors = [
        get_polygon_average(
            img_array,
            polygon,
        )
        for polygon in polygons
    ]

    quantized_colors = quantize_colors(
        average_colors,
        max_colors,
    )

    for polygon, color in zip(
        polygons,
        quantized_colors,
    ):
        draw.polygon(
            polygon,
            fill=color,
            outline=outline,
            width=outline_width,
        )

    return output


def create_polygons(
    width,
    height,
    grid_size,
    shape,
):
    """Create polygons for the selected tessellation."""

    if shape == "squares":
        return create_square_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "brick":
        return create_brick_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "triangles":
        return create_triangle_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "hexagons":
        return create_hexagon_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "rhombi":
        return create_rhombus_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "cubes":
        return create_cube_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "octagons_squares":
        return create_octagon_square_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "crosses":
        return create_cross_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "arrows":
        return create_arrow_polygons(
            width,
            height,
            grid_size,
        )

    if shape == "fish_scales":
        return create_fish_scale_polygons(
            width,
            height,
            grid_size,
        )

    return []


def create_square_polygons(
    width,
    height,
    size,
):
    """Create a square tessellation."""

    polygons = []
    size = max(1, int(round(size)))

    for y0 in range(0, height, size):
        for x0 in range(0, width, size):
            x1 = min(x0 + size, width)
            y1 = min(y0 + size, height)

            polygons.append([
                (x0, y0),
                (x1, y0),
                (x1, y1),
                (x0, y1),
            ])

    return polygons


def create_brick_polygons(
    width,
    height,
    size,
):
    """Create a staggered brick tessellation."""

    polygons = []

    brick_width = 2 * size
    brick_height = size

    first_row = -2
    last_row = (
        int(np.ceil(height / brick_height))
        + 2
    )

    for row in range(
        first_row,
        last_row,
    ):
        y0 = row * brick_height
        y1 = y0 + brick_height

        offset = (
            -brick_width / 2
            if row % 2
            else 0
        )

        x = offset - brick_width

        while x < width + brick_width:
            polygons.append([
                (x, y0),
                (x + brick_width, y0),
                (x + brick_width, y1),
                (x, y1),
            ])

            x += brick_width

    return polygons


def create_triangle_polygons(width, height, side):
    """Create an edge-to-edge tessellation of equilateral triangles."""

    polygons = []

    triangle_height = np.sqrt(3) * side / 2

    first_row = -2
    last_row = int(np.ceil(height / triangle_height)) + 2

    first_column = -3
    last_column = int(np.ceil(width / side)) + 3

    for row in range(first_row, last_row):
        y0 = row * triangle_height
        y1 = y0 + triangle_height

        offset = side / 2 if row % 2 else 0

        for column in range(first_column, last_column):
            x0 = column * side + offset

            polygons.extend([
                [
                    (x0, y0),
                    (x0 + side, y0),
                    (x0 + side / 2, y1),
                ],
                [
                    (x0 + side / 2, y1),
                    (x0 + 1.5 * side, y1),
                    (x0 + side, y0),
                ],
            ])

    return polygons


def create_hexagon_polygons(
    width,
    height,
    side,
):
    """Create a regular hexagonal tessellation."""

    polygons = []

    hex_width = np.sqrt(3) * side
    horizontal_spacing = hex_width
    vertical_spacing = 1.5 * side

    first_row = -2
    last_row = (
        int(np.ceil(height / vertical_spacing))
        + 2
    )

    first_column = -2
    last_column = (
        int(np.ceil(width / horizontal_spacing))
        + 2
    )

    for row in range(
        first_row,
        last_row,
    ):
        cy = row * vertical_spacing

        offset = (
            hex_width / 2
            if row % 2
            else 0
        )

        for column in range(
            first_column,
            last_column,
        ):
            cx = (
                column * horizontal_spacing
                + offset
            )

            polygons.append(
                regular_polygon(
                    cx=cx,
                    cy=cy,
                    radius=side,
                    sides=6,
                    rotation=-30,
                )
            )

    return polygons


def create_rhombus_polygons(
    width,
    height,
    side,
):
    """Create a tessellation of 60-degree rhombi."""

    polygons = []

    rhombus_height = (
        np.sqrt(3) * side / 2
    )

    first_row = -2
    last_row = (
        int(np.ceil(height / rhombus_height))
        + 2
    )

    first_column = -3
    last_column = (
        int(np.ceil(width / side))
        + 3
    )

    for row in range(
        first_row,
        last_row,
    ):
        y0 = row * rhombus_height
        y1 = y0 + rhombus_height

        offset = (
            side / 2
            if row % 2
            else 0
        )

        for column in range(
            first_column,
            last_column,
        ):
            x0 = column * side + offset

            polygons.append([
                (x0, y0),
                (x0 + side, y0),
                (x0 + 1.5 * side, y1),
                (x0 + 0.5 * side, y1),
            ])

    return polygons


def create_cube_polygons(
    width,
    height,
    side,
):
    """Create a tumbling-block tessellation."""

    polygons = []

    half_width = (
        np.sqrt(3) * side / 2
    )

    horizontal_spacing = (
        2 * half_width
    )

    vertical_spacing = (
        1.5 * side
    )

    first_row = -3
    last_row = (
        int(np.ceil(height / vertical_spacing))
        + 3
    )

    first_column = -3
    last_column = (
        int(np.ceil(width / horizontal_spacing))
        + 3
    )

    for row in range(
        first_row,
        last_row,
    ):
        cy = row * vertical_spacing

        offset = (
            half_width
            if row % 2
            else 0
        )

        for column in range(
            first_column,
            last_column,
        ):
            cx = (
                column * horizontal_spacing
                + offset
            )

            top = (
                cx,
                cy - side,
            )

            upper_left = (
                cx - half_width,
                cy - side / 2,
            )

            centre = (
                cx,
                cy,
            )

            upper_right = (
                cx + half_width,
                cy - side / 2,
            )

            lower_right = (
                cx + half_width,
                cy + side / 2,
            )

            bottom = (
                cx,
                cy + side,
            )

            lower_left = (
                cx - half_width,
                cy + side / 2,
            )

            polygons.extend([
                [
                    top,
                    upper_right,
                    centre,
                    upper_left,
                ],
                [
                    upper_left,
                    centre,
                    bottom,
                    lower_left,
                ],
                [
                    centre,
                    upper_right,
                    lower_right,
                    bottom,
                ],
            ])

    return polygons


def create_octagon_square_polygons(
    width,
    height,
    side,
):
    """Create regular octagons and rotated squares."""

    polygons = []

    cut = side / np.sqrt(2)
    spacing = side + 2 * cut

    first_row = -2
    last_row = (
        int(np.ceil(height / spacing))
        + 2
    )

    first_column = -2
    last_column = (
        int(np.ceil(width / spacing))
        + 2
    )

    for row in range(
        first_row,
        last_row,
    ):
        cy = row * spacing

        for column in range(
            first_column,
            last_column,
        ):
            cx = column * spacing

            polygons.append([
                (
                    cx - side / 2,
                    cy - spacing / 2,
                ),
                (
                    cx + side / 2,
                    cy - spacing / 2,
                ),
                (
                    cx + spacing / 2,
                    cy - side / 2,
                ),
                (
                    cx + spacing / 2,
                    cy + side / 2,
                ),
                (
                    cx + side / 2,
                    cy + spacing / 2,
                ),
                (
                    cx - side / 2,
                    cy + spacing / 2,
                ),
                (
                    cx - spacing / 2,
                    cy + side / 2,
                ),
                (
                    cx - spacing / 2,
                    cy - side / 2,
                ),
            ])

            square_cx = cx + spacing / 2
            square_cy = cy + spacing / 2

            polygons.append([
                (
                    square_cx,
                    square_cy - cut,
                ),
                (
                    square_cx + cut,
                    square_cy,
                ),
                (
                    square_cx,
                    square_cy + cut,
                ),
                (
                    square_cx - cut,
                    square_cy,
                ),
            ])

    return polygons


def create_cross_polygons(
    width,
    height,
    size,
):
    """
    Create a gapless tessellation of plus pentominoes.

    Every plus sign consists of five equal square units.
    """

    polygons = []

    unit = size

    horizontal_range = (
        int(np.ceil(width / unit))
        + 8
    )

    vertical_range = (
        int(np.ceil(height / unit))
        + 8
    )

    lattice_range = (
        horizontal_range
        + vertical_range
    )

    seen_centres = set()

    for i in range(
        -lattice_range,
        lattice_range + 1,
    ):
        for j in range(
            -lattice_range,
            lattice_range + 1,
        ):
            centre_column = 2 * i - j
            centre_row = i + 2 * j

            key = (
                centre_column,
                centre_row,
            )

            if key in seen_centres:
                continue

            seen_centres.add(key)

            cx = (
                centre_column * unit
                + unit / 2
            )

            cy = (
                centre_row * unit
                + unit / 2
            )

            polygon = create_plus_polygon(
                cx,
                cy,
                unit,
            )

            if polygon_intersects_image(
                polygon,
                width,
                height,
            ):
                polygons.append(polygon)

    return polygons


def create_plus_polygon(
    cx,
    cy,
    unit,
):
    """Create one plus-sign pentomino."""

    half = unit / 2
    one_and_half = 1.5 * unit

    return [
        (
            cx - half,
            cy - one_and_half,
        ),
        (
            cx + half,
            cy - one_and_half,
        ),
        (
            cx + half,
            cy - half,
        ),
        (
            cx + one_and_half,
            cy - half,
        ),
        (
            cx + one_and_half,
            cy + half,
        ),
        (
            cx + half,
            cy + half,
        ),
        (
            cx + half,
            cy + one_and_half,
        ),
        (
            cx - half,
            cy + one_and_half,
        ),
        (
            cx - half,
            cy + half,
        ),
        (
            cx - one_and_half,
            cy + half,
        ),
        (
            cx - one_and_half,
            cy - half,
        ),
        (
            cx - half,
            cy - half,
        ),
    ]


def create_arrow_polygons(
    width,
    height,
    size,
):
    """Create repeating three-armed concave shapes."""

    polygons = []

    horizontal_spacing = 1.5 * size
    vertical_spacing = np.sqrt(3) * size

    first_column = -3
    last_column = (
        int(np.ceil(width / horizontal_spacing))
        + 3
    )

    first_row = -3
    last_row = (
        int(np.ceil(height / vertical_spacing))
        + 3
    )

    for column in range(
        first_column,
        last_column,
    ):
        cx = column * horizontal_spacing

        offset = (
            vertical_spacing / 2
            if column % 2
            else 0
        )

        for row in range(
            first_row,
            last_row,
        ):
            cy = (
                row * vertical_spacing
                + offset
            )

            rotation = (
                0
                if (row + column) % 2 == 0
                else 180
            )

            polygons.append(
                create_three_arm_polygon(
                    cx=cx,
                    cy=cy,
                    outer_radius=size,
                    inner_radius=size / 2,
                    rotation=rotation,
                )
            )

    return polygons


def create_three_arm_polygon(
    cx,
    cy,
    outer_radius,
    inner_radius,
    rotation=0,
):
    """Create one concave three-armed polygon."""

    points = []

    for index in range(12):
        angle = (
            rotation
            - 90
            + index * 30
        )

        if index % 4 == 0:
            radius = outer_radius
        elif index % 4 == 2:
            radius = outer_radius * 0.75
        else:
            radius = inner_radius

        points.append((
            cx
            + radius
            * np.cos(np.deg2rad(angle)),
            cy
            + radius
            * np.sin(np.deg2rad(angle)),
        ))

    return points


def create_fish_scale_polygons(width, height, size):
    """
    Create a gapless curved fish-scale pattern.

    Every rectangular cell is divided by a curved scale boundary.
    Both sides of every curve are independent regions and therefore
    receive separate colours.
    """

    polygons = []

    cell_width = max(2, int(round(size)))
    cell_height = max(2, int(round(size * 0.8)))
    curve_steps = max(16, int(round(size / 2)))

    first_row = -1
    last_row = int(np.ceil(height / cell_height)) + 1
    first_column = -2
    last_column = int(np.ceil(width / cell_width)) + 2

    for row in range(first_row, last_row):
        y0 = row * cell_height
        y1 = y0 + cell_height

        offset = cell_width / 2 if row % 2 else 0

        for column in range(first_column, last_column):
            x0 = column * cell_width + offset
            x1 = x0 + cell_width

            curve = []

            for index in range(curve_steps + 1):
                t = index / curve_steps
                y = y0 + t * cell_height

                bulge = np.sin(np.pi * t)
                direction = 1 if (row + column) % 2 == 0 else -1

                x = (
                    x0
                    + cell_width / 2
                    + direction * cell_width * 0.48 * bulge
                )

                curve.append((x, y))

            left_region = [
                (x0, y0),
                curve[0],
                *curve[1:],
                (x0, y1),
            ]

            right_region = [
                curve[0],
                (x1, y0),
                (x1, y1),
                curve[-1],
                *reversed(curve[:-1]),
            ]

            polygons.extend([
                left_region,
                right_region,
            ])

    return polygons


def render_truchet(
    img_array,
    width,
    height,
    grid_size,
    max_colors,
    fill,
    outline,
    outline_width,
    seed,
):
    """
    Render Truchet cells as two separately coloured regions.

    Every curved boundary separates two independent colour regions.
    No black border is drawn unless outline is explicitly supplied.
    """

    size = max(
        1,
        int(round(grid_size)),
    )

    rng = np.random.default_rng(seed)

    regions = []

    for y0 in range(
        0,
        height,
        size,
    ):
        for x0 in range(
            0,
            width,
            size,
        ):
            x1 = min(
                x0 + size,
                width,
            )

            y1 = min(
                y0 + size,
                height,
            )

            orientation = int(
                rng.integers(4)
            )

            masks = create_truchet_region_masks(
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                orientation=orientation,
            )

            for mask in masks:
                regions.append({
                    "bbox": (
                        x0,
                        y0,
                        x1,
                        y1,
                    ),
                    "mask": mask,
                })

    output = Image.new(
        "RGB",
        (width, height),
        "white",
    )

    if fill:
        average_colors = [
            get_mask_average(
                img_array=img_array,
                bbox=region["bbox"],
                mask=region["mask"],
            )
            for region in regions
        ]

        region_colors = quantize_colors(
            average_colors,
            max_colors,
        )

    else:
        region_colors = [
            "white"
        ] * len(regions)

    for region, color in zip(
        regions,
        region_colors,
    ):
        x0, y0, x1, y1 = region["bbox"]

        colour_layer = Image.new(
            "RGB",
            (
                x1 - x0,
                y1 - y0,
            ),
            color,
        )

        output.paste(
            colour_layer,
            (
                x0,
                y0,
            ),
            region["mask"],
        )

    if outline is not None or not fill:
        draw = ImageDraw.Draw(output)

        line_color = (
            outline
            if outline is not None
            else "black"
        )

        rng = np.random.default_rng(seed)

        for y0 in range(
            0,
            height,
            size,
        ):
            for x0 in range(
                0,
                width,
                size,
            ):
                x1 = min(
                    x0 + size,
                    width,
                )

                y1 = min(
                    y0 + size,
                    height,
                )

                orientation = int(
                    rng.integers(4)
                )

                draw_truchet_boundary(
                    draw=draw,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    orientation=orientation,
                    color=line_color,
                    width=outline_width,
                )

    return output


def create_truchet_region_masks(
    x0,
    y0,
    x1,
    y1,
    orientation,
):
    """Create two complementary masks separated by a curved arc."""

    tile_width = x1 - x0
    tile_height = y1 - y0

    mask_a = Image.new(
        "L",
        (
            tile_width,
            tile_height,
        ),
        0,
    )

    draw = ImageDraw.Draw(mask_a)

    if orientation == 0:
        draw.pieslice(
            (
                -tile_width,
                -tile_height,
                tile_width,
                tile_height,
            ),
            start=0,
            end=90,
            fill=255,
        )

    elif orientation == 1:
        draw.pieslice(
            (
                0,
                -tile_height,
                2 * tile_width,
                tile_height,
            ),
            start=90,
            end=180,
            fill=255,
        )

    elif orientation == 2:
        draw.pieslice(
            (
                0,
                0,
                2 * tile_width,
                2 * tile_height,
            ),
            start=180,
            end=270,
            fill=255,
        )

    else:
        draw.pieslice(
            (
                -tile_width,
                0,
                tile_width,
                2 * tile_height,
            ),
            start=270,
            end=360,
            fill=255,
        )

    mask_b = Image.eval(
        mask_a,
        lambda value: 255 - value,
    )

    return [
        mask_a,
        mask_b,
    ]


def draw_truchet_boundary(
    draw,
    x0,
    y0,
    x1,
    y1,
    orientation,
    color,
    width,
):
    """Draw the optional boundary between two Truchet regions."""

    tile_width = x1 - x0
    tile_height = y1 - y0

    if orientation == 0:
        draw.arc(
            (
                x0 - tile_width,
                y0 - tile_height,
                x0 + tile_width,
                y0 + tile_height,
            ),
            start=0,
            end=90,
            fill=color,
            width=width,
        )

    elif orientation == 1:
        draw.arc(
            (
                x1 - tile_width,
                y0 - tile_height,
                x1 + tile_width,
                y0 + tile_height,
            ),
            start=90,
            end=180,
            fill=color,
            width=width,
        )

    elif orientation == 2:
        draw.arc(
            (
                x1 - tile_width,
                y1 - tile_height,
                x1 + tile_width,
                y1 + tile_height,
            ),
            start=180,
            end=270,
            fill=color,
            width=width,
        )

    else:
        draw.arc(
            (
                x0 - tile_width,
                y1 - tile_height,
                x0 + tile_width,
                y1 + tile_height,
            ),
            start=270,
            end=360,
            fill=color,
            width=width,
        )


def regular_polygon(
    cx,
    cy,
    radius,
    sides,
    rotation=0,
):
    """Create the vertices of a regular polygon."""

    return [
        (
            cx
            + radius
            * np.cos(
                np.deg2rad(
                    rotation
                    + index
                    * 360
                    / sides
                )
            ),
            cy
            + radius
            * np.sin(
                np.deg2rad(
                    rotation
                    + index
                    * 360
                    / sides
                )
            ),
        )
        for index in range(sides)
    ]


def polygon_intersects_image(
    polygon,
    width,
    height,
):
    """Check whether a polygon intersects the image."""

    min_x = min(
        x
        for x, y in polygon
    )

    max_x = max(
        x
        for x, y in polygon
    )

    min_y = min(
        y
        for x, y in polygon
    )

    max_y = max(
        y
        for x, y in polygon
    )

    return (
        max_x >= 0
        and max_y >= 0
        and min_x < width
        and min_y < height
    )


def get_mask_average(
    img_array,
    bbox,
    mask,
):
    """Calculate the average colour inside a local mask."""

    x0, y0, x1, y1 = bbox

    region = img_array[
        y0:y1,
        x0:x1,
    ]

    mask_array = np.array(
        mask,
        dtype=bool,
    )

    pixels = region[mask_array]

    if len(pixels) == 0:
        return 255, 255, 255

    return tuple(
        np.round(
            pixels.mean(axis=0)
        ).astype(np.uint8)
    )


def get_polygon_average(
    img_array,
    polygon,
):
    """Calculate the average RGB colour inside a polygon."""

    height, width = img_array.shape[:2]

    x0 = max(
        0,
        int(
            np.floor(
                min(
                    x
                    for x, y in polygon
                )
            )
        ),
    )

    y0 = max(
        0,
        int(
            np.floor(
                min(
                    y
                    for x, y in polygon
                )
            )
        ),
    )

    x1 = min(
        width,
        int(
            np.ceil(
                max(
                    x
                    for x, y in polygon
                )
            )
        ) + 1,
    )

    y1 = min(
        height,
        int(
            np.ceil(
                max(
                    y
                    for x, y in polygon
                )
            )
        ) + 1,
    )

    if x1 <= x0 or y1 <= y0:
        return 255, 255, 255

    local_polygon = [
        (
            x - x0,
            y - y0,
        )
        for x, y in polygon
    ]

    mask = Image.new(
        "L",
        (
            x1 - x0,
            y1 - y0,
        ),
        0,
    )

    ImageDraw.Draw(mask).polygon(
        local_polygon,
        fill=255,
    )

    region = img_array[
        y0:y1,
        x0:x1,
    ]

    mask_array = np.array(
        mask,
        dtype=bool,
    )

    pixels = region[mask_array]

    if len(pixels) == 0:
        return 255, 255, 255

    return tuple(
        np.round(
            pixels.mean(axis=0)
        ).astype(np.uint8)
    )


def quantize_colors(
    colors,
    max_colors,
):
    """Reduce RGB colours to at most max_colors colours."""

    if not colors:
        return []

    palette_img = Image.new(
        "RGB",
        (
            len(colors),
            1,
        ),
    )

    palette_img.putdata(colors)

    quantized = palette_img.quantize(
        colors=min(
            max_colors,
            len(colors),
        ),
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")

    return list(
        quantized.getdata()
    )

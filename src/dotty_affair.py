from matplotlib import colormaps
import numpy as np
from PIL import Image, ImageDraw


def image_to_dots(img, grid_size=10, min_radius=0, max_radius=None, jitter=None, color=True, fill=True, outline_width=1):
    """Convert an image into a field of black dots (halftone style)."""
    # Define max_radius
    if not max_radius:
        max_radius = grid_size / 2

    # Convert to grayscale
    img_gray = img.convert("L")

    width, height = img_gray.size
    n_cols = round(width / grid_size)
    n_rows = round(height / grid_size)

    x_edges = np.linspace(0, width, n_cols + 1, dtype=int)
    y_edges = np.linspace(0, height, n_rows + 1, dtype=int)

    # Create white canvas
    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)

    # Convert to numpy for easy brightness access
    img_array = np.array(img_gray)

    for i in range(n_rows):
        for j in range(n_cols):
            # Extract grid cell
            x0, x1 = x_edges[j], x_edges[j+1]
            y0, y1 = y_edges[i], y_edges[i+1]

            if x1 <= x0 or y1 <= y0: continue

            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2

            cell_size = min(x1 - x0, y1 - y0)
            cx, cy = apply_circular_jitter(cx, cy, cell_size, jitter)

            # Clamp ONLY for sampling, NOT for drawing
            sx = max(0, min(width - 1, cx))
            sy = max(0, min(height - 1, cy))

            # Get dot size
            radius = get_radius(img_array, sx, sy, max_radius, min_radius)
            if radius is None: continue

            # Draw dot
            if fill:
                fill_color = img.getpixel((sx, sy)) if color else "black"
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill_color)
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline="grey", width=outline_width)
            else:
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline="grey", width=outline_width)
                # draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(120, 120, 120), width=outline_width)

    return output


def image_to_density_dots(img, grid_size=10, dot_radius=None, jitter=None, fill=False, seed=None):
    """Convert image to constant-size dots, with density based on brightness."""
    if seed is not None:
        np.random.seed(seed)

    if dot_radius is None:
        dot_radius = grid_size / 2

    img_gray = img.convert("L")
    width, height = img_gray.size

    n_cols = round(width / grid_size)
    n_rows = round(height / grid_size)

    x_edges = np.linspace(0, width, n_cols + 1, dtype=int)
    y_edges = np.linspace(0, height, n_rows + 1, dtype=int)

    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)

    img_array = np.array(img_gray)

    for i in range(n_rows):
        for j in range(n_cols):
            x0, x1 = x_edges[j], x_edges[j + 1]
            y0, y1 = y_edges[i], y_edges[i + 1]

            if x1 <= x0 or y1 <= y0:
                continue

            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2

            cell_size = min(x1 - x0, y1 - y0)
            cx, cy = apply_circular_jitter(cx, cy, cell_size, jitter)

            sx = max(0, min(width - 1, cx))
            sy = max(0, min(height - 1, cy))

            brightness = img_array[sy, sx]

            # 0 = white area -> low chance
            # 1 = dark area  -> high chance
            dot_probability = 1 - brightness / 255

            if np.random.random() > dot_probability:
                continue

            bbox = (
                cx - dot_radius,
                cy - dot_radius,
                cx + dot_radius,
                cy + dot_radius,
            )

            palette = [
                (231, 76, 60),  # red
                (241, 196, 15),  # yellow
                # (46, 204, 113),  # green
                # (52, 152, 219),  # blue
                (155, 89, 182),  # purple
            ]
            random_color = palette[np.random.randint(len(palette))]

            # random_color = tuple(np.random.randint(50, 206, 3))

            # cmap = colormaps["viridis"]
            # rgba = cmap(np.random.random())
            # random_color = tuple(int(255 * c) for c in rgba[:3])

            if fill:
                draw.ellipse(bbox, fill=random_color)
            else:
                draw.ellipse(bbox, outline=random_color, width=1)

    return output


def image_to_color_dots(img, colors, grid_size=10, radius=None, min_fraction=0.02):
    """Convert an image into same-sized dots using a balanced color palette."""
    if radius is None:
        radius = grid_size * 0.4

    img = img.convert("RGB")
    width, height = img.size
    n_cols, n_rows = round(width / grid_size), round(height / grid_size)
    x_edges = np.linspace(0, width, n_cols + 1, dtype=int)
    y_edges = np.linspace(0, height, n_rows + 1, dtype=int)
    img_array = np.array(img).astype(float)
    color_array = np.array(colors).astype(float)

    # Get sampling positions
    positions = []
    for i in range(n_rows):
        for j in range(n_cols):
            x0, x1 = x_edges[j], x_edges[j + 1]
            y0, y1 = y_edges[i], y_edges[i + 1]
            if x1 <= x0 or y1 <= y0:
                continue
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            sx, sy = max(0, min(width - 1, cx)), max(0, min(height - 1, cy))
            positions.append((cx, cy, sx, sy))

    samples = np.array([img_array[sy, sx] for _, _, sx, sy in positions])
    distances = np.sum((samples[:, None, :] - color_array[None, :, :]) ** 2, axis=2)

    # Initially, every dot gets its closest color
    assignments = np.argmin(distances, axis=1)

    # Force every palette color to appear
    min_count = max(1, int(len(positions) * min_fraction))
    used = np.zeros(len(positions), dtype=bool)

    for color_idx in range(len(colors)):
        for _ in range(min_count):
            regret = distances[:, color_idx] - distances.min(axis=1)
            regret[used] = np.inf
            idx = np.argmin(regret)
            assignments[idx] = color_idx
            used[idx] = True

    # Draw
    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)

    for (cx, cy, _, _), color_idx in zip(positions, assignments):
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        draw.ellipse(bbox, fill=colors[color_idx])

    return output


def image_to_ranked_dots(img, colors, grid_size=10, radius=None, balance=0.5):
    """
    balance=0.0 -> pure brightness mapping
    balance=1.0 -> equal colour usage
    """

    if radius is None:
        radius = grid_size * 0.4

    img = img.convert("RGB")
    width, height = img.size

    n_cols = round(width / grid_size)
    n_rows = round(height / grid_size)

    x_edges = np.linspace(0, width, n_cols + 1, dtype=int)
    y_edges = np.linspace(0, height, n_rows + 1, dtype=int)

    img_array = np.array(img)

    positions = []
    brightnesses = []

    for i in range(n_rows):
        for j in range(n_cols):

            x0, x1 = x_edges[j], x_edges[j + 1]
            y0, y1 = y_edges[i], y_edges[i + 1]

            if x1 <= x0 or y1 <= y0:
                continue

            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2

            sx = max(0, min(width - 1, cx))
            sy = max(0, min(height - 1, cy))

            r, g, b = img_array[sy, sx]

            brightness = 0.299 * r + 0.587 * g + 0.114 * b

            positions.append((cx, cy))
            brightnesses.append(brightness)

    brightnesses = np.array(brightnesses)

    # rank of every dot within the image
    order = np.argsort(brightnesses)
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))

    rank_fraction = rank / max(1, len(rank) - 1)

    # actual brightness fraction
    brightness_fraction = brightnesses / 255.0

    # blend the two approaches
    blended = (
        balance * rank_fraction
        + (1 - balance) * brightness_fraction
    )

    n_colors = len(colors)

    color_idx = np.floor(blended * n_colors).astype(int)
    color_idx = np.clip(color_idx, 0, n_colors - 1)

    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)

    for (cx, cy), idx in zip(positions, color_idx):
        draw.ellipse(
            (
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
            ),
            fill=colors[idx],
        )

    return output


def apply_circular_jitter(cx, cy, cell_size, jitter):
    """Apply circular jitter to a point."""
    if not jitter:
        return cx, cy

    max_r = cell_size * jitter

    angle = np.random.uniform(0, 2 * np.pi)
    r = max_r * np.sqrt(np.random.uniform(0, 1))

    cx += int(r * np.cos(angle))
    cy += int(r * np.sin(angle))

    return cx, cy


def get_radius(img_array, sx, sy, max_radius, min_radius):
    brightness = img_array[sy, sx]
    radius = max_radius * (1 - brightness / 255)

    if radius < min_radius:
        return None

    return radius

"""Adapt Create's window sprites to Horizon's existing CTM format."""

from pathlib import Path
import struct
import zlib


VERTICAL_WINDOWS = (
    "oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove",
    "crimson", "warped", "cherry", "bamboo", "ornate_iron",
)
PNG = b"\x89PNG\r\n\x1a\n"

# Java numbers these tiles by (up ? 1 : 0) + (down ? 2 : 0).
# OptiFine vertical order is bottom, middle, top, isolated.
JAVA_TILE_ORDER = (1, 3, 2, 0)
WINDOW_TILE_DIRECTORY = "block/window_ctm"


def png_chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))


def paeth(left, above, diagonal):
    prediction = left + above - diagonal
    return min((left, above, diagonal), key=lambda sample: abs(prediction - sample))


def read_sheet(path, columns):
    """Unfilter the pinned assets' RGBA8 or indexed PNG rows without changing palette/alpha."""
    raw = path.read_bytes()
    if not raw.startswith(PNG):
        raise ValueError(f"Expected a PNG sheet: {path}")
    offset = len(PNG)
    metadata = []
    compressed = []
    header = None
    while offset + 12 <= len(raw):
        length, name = struct.unpack_from(">I4s", raw, offset)
        data = raw[offset + 8:offset + 8 + length]
        offset += 12 + length
        if name == b"IHDR":
            header = struct.unpack(">IIBBBBB", data)
        elif name == b"IDAT":
            compressed.append(data)
        elif name in (b"PLTE", b"tRNS", b"sRGB", b"gAMA", b"cHRM", b"sBIT"):
            metadata.append(png_chunk(name, data))
        elif name == b"IEND":
            break
    if header is None:
        raise ValueError(f"Window sheet is missing its PNG header: {path}")
    width, height, depth, color, compression, filtering, interlace = header
    if (width, height, compression, filtering, interlace) != (16 * columns, 16 * columns, 0, 0, 0) or (color, depth) not in (
        (6, 8), (3, 4), (3, 8),
    ):
        raise ValueError(f"Unexpected window sheet format: {path}: {header}")
    bytes_per_pixel = 4 if color == 6 else 1
    stride = width * depth * (4 if color == 6 else 1) // 8
    scanlines = zlib.decompress(b"".join(compressed))
    if len(scanlines) != height * (stride + 1):
        raise ValueError(f"Unexpected row sizes in {path}")
    rows = [bytes(stride)]
    for start in range(0, len(scanlines), stride + 1):
        kind = scanlines[start]
        if kind > 4:
            raise ValueError(f"Unknown PNG filter {kind} in {path}")
        above = rows[-1]
        row = bytearray(scanlines[start + 1:start + 1 + stride])
        for col, sample in enumerate(row):
            left = row[col - bytes_per_pixel] if col >= bytes_per_pixel else 0
            diagonal = above[col - bytes_per_pixel] if col >= bytes_per_pixel else 0
            predictor = (0, left, above[col], (left + above[col]) // 2)[kind] if kind < 4 else paeth(
                left, above[col], diagonal,
            )
            row[col] = (sample + predictor) & 255
        rows.append(bytes(row))
    tile_header = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, depth, color, 0, 0, 0))
    return tile_header + b"".join(metadata), rows[1:], stride // columns, depth


def mirrored_palette_row(row):
    return bytes(((sample << 4) | (sample >> 4)) & 255 for sample in reversed(row))


def write_tiles(sheet, target, columns, order, *, mirrored=False, keep_index=False):
    target.mkdir(parents=True, exist_ok=True)
    header, rows, width, depth = read_sheet(sheet, columns)
    if mirrored and depth != 4:
        raise ValueError(f"Unexpected bit depth for a mirrored framed-glass sheet: {sheet}")
    for tile, java in enumerate(order):
        x, y = java % columns * width, java // columns * 16
        lines = (line[x:x + width] for line in rows[y:y + 16])
        if mirrored:
            lines = (mirrored_palette_row(line) for line in lines)
        pixels = b"".join(b"\0" + line for line in lines)
        (target / f"{java if keep_index else tile}.png").write_bytes(
            PNG + header + png_chunk(b"IDAT", zlib.compress(pixels)) + png_chunk(b"IEND", b""),
        )


def write_rules(target, name, method, tiles, *, pane_orientation=None):
    for suffix in ("", "_pane"):
        config = (
            f"matchBlocks=create:{name}{suffix}\n"
            f"matchTiles=create:block/palettes/{name}\n"
            f"method={method}\n"
            "faces=sides\n"
            "connect=block\n"
            f"tiles={tiles}\n"
        )
        if not suffix:
            config += "innerSeams=true\n"
        elif pane_orientation:
            config += f"orient={pane_orientation}\n"
        (target / f"{name}{suffix}.properties").write_text(config, encoding="utf-8")


def prepare_vertical_windows(resources: Path, content: Path):
    textures = resources / "assets/create/textures/block/palettes"
    for prefix in VERTICAL_WINDOWS:
        name = f"{prefix}_window"
        rules = content / f"assets/create/optifine/ctm/{name}"
        rules.mkdir(parents=True, exist_ok=True)
        tile_path = f"{WINDOW_TILE_DIRECTORY}/{name}"
        target = content / f"assets/create/textures/{tile_path}"
        write_tiles(textures / f"{name}_connected.png", target, 2, JAVA_TILE_ORDER)
        tiles = " ".join(f"create:{tile_path}/{tile}" for tile in range(len(JAVA_TILE_ORDER)))
        write_rules(rules, name, "vertical", tiles)


# In OptiFine's 47-tile order, repeat Java's 16 RECTANGLE tiles for
# every context with the same four cardinal connections.
RECTANGLE_TILES = (
    12, 13, 14, 15, 1, 3, 5, 2, 6, 6, 6, 6,
    0, 1, 2, 3, 9, 11, 10, 7, 6, 6, 6, 6,
    4, 5, 6, 7, 5, 2, 5, 2, 6, 6, 6, 6,
    8, 9, 10, 11, 10, 7, 10, 7, 6, 6, 6,
)


def prepare_industrial_window(resources: Path, content: Path):
    name = "industrial_iron_window"
    sheet = resources / f"assets/create/textures/block/palettes/{name}_connected.png"
    rules = content / f"assets/create/optifine/ctm/{name}"
    rules.mkdir(parents=True, exist_ok=True)
    tile_path = f"{WINDOW_TILE_DIRECTORY}/{name}"
    write_tiles(sheet, content / f"assets/create/textures/{tile_path}", 4, range(16))
    tiles = " ".join(f"create:{tile_path}/{tile}" for tile in RECTANGLE_TILES)
    write_rules(rules, name, "ctm", tiles, pane_orientation="texture")

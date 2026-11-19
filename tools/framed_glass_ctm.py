"""Port Java framed-glass CT indices through Horizon's existing pack rules."""

from window_ctm import JAVA_TILE_ORDER, WINDOW_TILE_DIRECTORY, write_tiles

# Java OMNIDIRECTIONAL tiles in the Horizon 47-tile order.
OMNI = (
    0, 16, 24, 8, 18, 10, 19, 26, 28, 43, 37, 30,
    2, 21, 58, 13, 17, 9, 25, 11, 29, 35, 51, 44,
    3, 42, 54, 34, 40, 56, 41, 57, 38, 46, 36, 45,
    1, 20, 50, 12, 49, 33, 48, 32, 53, 52, 27,
)

OMNI_REFLECTED = (
    0, 8, 24, 16, 10, 18, 11, 26, 29, 35, 44, 30,
    2, 13, 58, 21, 9, 17, 25, 19, 28, 43, 51, 37,
    3, 34, 54, 42, 32, 57, 33, 56, 46, 38, 45, 36,
    1, 12, 50, 20, 48, 41, 49, 40, 52, 53, 27,
)

SIDES = {
    "framed_glass": ("ctm", OMNI, OMNI_REFLECTED),
    "horizontal_framed_glass": ("horizontal", (2, 1, 3, 0), (3, 1, 2, 0)),
    "vertical_framed_glass": ("vertical", JAVA_TILE_ORDER, JAVA_TILE_ORDER),
}
CTM = "assets/create/optifine/ctm"


def write_rule(target, file, name, texture, method, indices, faces, *, mirrored=False):
    tile_folder = f"create:{WINDOW_TILE_DIRECTORY}/{texture}" + ("/mirrored" if mirrored else "")
    tiles = " ".join(f"{tile_folder}/{index}" for index in indices)
    config = (
        f"matchBlocks=create:{name}\n"
        "matchTiles=create:block/palettes/framed_glass\n"
        f"method={method}\n"
        f"faces={faces}\n"
        "connect=block\n"
        f"tiles={tiles}\n"
    )
    if not name.endswith("_pane"):
        config += "innerSeams=true\n"
    (target / f"{file}.properties").write_text(config, encoding="utf-8")


def prepare_framed_glass(resources, content):
    sheets = resources / "assets/create/textures/block/palettes"
    for name, (method, ordered, reflected) in SIDES.items():
        target = content / CTM / name
        target.mkdir(parents=True, exist_ok=True)
        tiles = content / f"assets/create/textures/{WINDOW_TILE_DIRECTORY}/{name}"
        source = sheets / f"{name}_connected.png"
        grid = 8 if method == "ctm" else 2
        indices = sorted(set(ordered))
        write_tiles(source, tiles, grid, indices, keep_index=True)
        write_tiles(source, tiles / "mirrored", grid, indices, mirrored=True, keep_index=True)
        write_rule(target, name, name, name, method, ordered, "all" if name == "framed_glass" else "sides")
        pane = f"{name}_pane"
        write_rule(target, pane, pane, name, method, ordered, "south east")
        write_rule(target, f"{pane}_mirrored", pane, name, method, reflected, "north west", mirrored=True)
        if name == "horizontal_framed_glass":
            write_rule(target, f"{name}_caps", name, "framed_glass", "ctm", OMNI, "top bottom")

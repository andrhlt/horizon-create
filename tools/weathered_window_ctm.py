"""Pack the four Java Weathered Iron atlases for the model-random CTM rule."""

from window_ctm import RECTANGLE_TILES, WINDOW_TILE_DIRECTORY, write_tiles


def prepare_weathered_window(resources, content):
    name = "weathered_iron_window"
    texture = f"create:block/palettes/{name}"
    source = resources / "assets/create/textures/block/palettes"
    target = content / f"assets/create/optifine/ctm/{name}"
    target.mkdir(parents=True, exist_ok=True)
    tile_path = f"{WINDOW_TILE_DIRECTORY}/{name}"
    content_path = content / f"assets/create/textures/{tile_path}"
    for variant in range(4):
        write_tiles(source / f"{name}_{variant+1}_connected.png", content_path / str(variant), 4, range(16))
    tiles = " ".join(f"create:{tile_path}/{variant}/{index}"
                     for variant in range(4) for index in RECTANGLE_TILES)
    for suffix, option in (("", "innerSeams=true"), ("_pane", "orient=texture")):
        (target / f"{name}{suffix}.properties").write_text(
            f"matchBlocks=create:{name}{suffix}\n"
            f"matchTiles={texture}\n"
            "method=ctm\nfaces=sides\nconnect=block\njavaModelRandom=true\n"
            f"{option}\n"
            f"tiles={tiles}\n",
            encoding="utf-8",
        )

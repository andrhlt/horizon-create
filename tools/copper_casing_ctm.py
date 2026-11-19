"""Pack Java Copper Casing tiles for casing and closed Encased Fluid Pipe faces."""

import json
from shutil import copy2

from framed_glass_ctm import OMNI
from window_ctm import write_tiles

TILES = "block/copper_casing_ctm"
BASE = f"create:{TILES}/base"


def prepare_copper_casing(resources, content):
    assets = content / "assets/create"
    artwork = resources / "assets/create/textures/block"
    tiles = assets / "textures" / TILES
    write_tiles(artwork / "copper_casing_connected.png", tiles, 8, sorted(set(OMNI)), keep_index=True)
    copy2(artwork / "copper_casing.png", tiles / "base.png")

    # Other Create models use the same artwork without belonging to the casing
    # family. An alias limits adjacency to these two models and leaves open
    # pipe faces on their own sprite.
    for model, key in (("copper_casing", "all"), ("encased_fluid_pipe/block_flat", "0")):
        path = assets / "models/block" / f"{model}.json"
        data = json.loads(path.read_bytes())
        if data["textures"][key] != "create:block/copper_casing":
            raise ValueError(f"Unexpected Copper Casing sprite in {model}")
        data["textures"][key] = BASE
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    folder = assets / "optifine/ctm/copper_casing"
    folder.mkdir(parents=True, exist_ok=True)
    indices = " ".join(f"create:{TILES}/{java}" for java in OMNI)
    (folder / "copper_casing.properties").write_text(
        "matchBlocks=create:copper_casing create:encased_fluid_pipe\n"
        f"matchTiles={BASE}\n"
        "method=ctm\nfaces=all\nconnect=tile\ninnerSeams=true\n"
        f"tiles={indices}\n",
        encoding="utf-8",
    )

"""Prepare the 16 Toolbox blocks and translate their Java crafting recipes."""

import json
from pathlib import Path
from shutil import copy2


DYE_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)
TOOLBOX_COLORS = dict(zip(DYE_COLORS, (8, *range(15, 30)), strict=True))
TOOLBOXES = tuple(f"{color}_toolbox" for color in TOOLBOX_COLORS)
FACINGS = {"north": 0, "east": 90, "south": 180, "west": 270}


def _copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, target)


def _assets(resources, generated, content, write_json):
    assets = content / "assets/create"
    originals = resources / "assets/create"
    generated_assets = generated / "assets/create"
    for path in ("block", "item", "drawer", *(f"lid/{color}" for color in TOOLBOX_COLORS)):
        relative = Path(f"models/block/toolbox/{path}.json")
        _copy(originals / relative, assets / relative)
    relative = Path("textures/gui/toolbox.png")
    _copy(originals / relative, assets / relative)

    for color in TOOLBOX_COLORS:
        name = f"{color}_toolbox"
        for root in ("models/item", "models/block"):
            relative = Path(root) / f"{name}.json"
            _copy(generated_assets / relative, assets / relative)
        relative = Path(f"textures/block/toolbox/{color}.png")
        _copy(originals / relative, assets / relative)
        relative = Path(f"blockstates/{name}.json")
        _copy(generated_assets / relative, assets / relative)


def _labels(resources, generated, content, write_json):
    root = Path("assets/create/lang")
    english = generated / root / "en_us.json"
    source_languages = [english, *(path for path in (resources / root).glob("*.json") if path.name != english.name)]
    for source in source_languages:
        translations = json.loads(source.read_bytes())
        toolbox = {
            key: value for key, value in translations.items()
            if key.startswith("create.toolbox.") or key == "create.keyinfo.toolbelt"
        }
        if not toolbox:
            continue
        target = content / root / source.name
        labels = json.loads(target.read_bytes()) if target.exists() else {}
        labels.update(toolbox)
        write_json(target, labels)


def prepare_toolboxes(resources, generated, content, write_json, crafting_ingredient, upgrade_block_loot):
    """Call after generic asset/loot preparation, before archiving the pack."""
    definitions = content / "data/create/horizon/block"
    north_south = [[1 / 16, 0, 4 / 16, 15 / 16, 9 / 16, 12 / 16]]
    east_west = [[4 / 16, 0, 1 / 16, 12 / 16, 9 / 16, 15 / 16]]
    shapes = {"property": "facing", "values": {
        "north": north_south, "south": north_south, "east": east_west, "west": east_west,
    }}
    recipes = Path("data/create/recipe/crafting/curiosities")
    dyeing = recipes / "toolbox_dyeing.json"
    _copy(generated / dyeing, content / dyeing)
    for color, map_color in TOOLBOX_COLORS.items():
        name = f"{color}_toolbox"
        write_json(definitions / f"{name}.json", {
            "template": "minecraft:oak_planks",
            "item": True,
            "properties": {
                "occludes": False, "map_color": map_color,
                "hardness": 2.0, "explosion_resistance": 2.0,
                "sounds": "minecraft:stripped_spruce_wood",
            },
            "state_properties": {
                "facing": {"type": "enum", "values": list(FACINGS)},
                "waterlogged": {"type": "boolean"},
            },
            "default_state": {"facing": "north", "waterlogged": "false"},
            "shapes": shapes,
            "collision_shapes": shapes,
        })
        loot = Path(f"data/create/loot_table/blocks/{name}.json")
        table = json.loads((generated / loot).read_bytes())
        upgrade_block_loot(table)
        write_json(content / loot, table)

    direct = recipes / "brown_toolbox.json"
    recipe = json.loads((generated / direct).read_bytes())
    recipe["key"] = {key: crafting_ingredient(value) for key, value in recipe["key"].items()}
    write_json(content / direct, recipe)
    for kind in ("item", "block"):
        relative = Path(f"data/create/tags/{kind}/toolboxes.json")
        _copy(generated / relative, content / relative)

    for tag, values in (
        ("leathers", ["minecraft:leather"]),
        ("chests/wooden", ["minecraft:chest", "minecraft:trapped_chest"]),
    ):
        path = content / f"data/c/tags/item/{tag}.json"
        if not path.exists():
            write_json(path, {"values": values})
    dyes = content / "data/c/tags/item/dyes.json"
    existing = json.loads(dyes.read_bytes()) if dyes.exists() else {"values": []}
    for color in TOOLBOX_COLORS:
        reference = f"#c:dyes/{color}"
        if reference not in existing["values"]:
            existing["values"].append(reference)
    write_json(dyes, existing)
    cannot_nest = content / "data/c/tags/item/cannot_fit_inside_container_items.json"
    tag = json.loads(cannot_nest.read_bytes()) if cannot_nest.exists() else {"values": []}
    if "#create:toolboxes" not in tag["values"]:
        tag["values"].append("#create:toolboxes")
    write_json(cannot_nest, tag)
    _assets(resources, generated, content, write_json)
    _labels(resources, generated, content, write_json)

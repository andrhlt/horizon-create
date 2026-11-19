"""Prepare the pinned Create window and glass palettes."""

import json
from pathlib import Path

from stone_palettes import normalize_recipe, palette_recipes, palette_tags

# Map colors from the Java palette GameTest. Pane blocks inherit the color.
WINDOW_COLORS = {
    "tiled_glass": 0,
    "framed_glass": 0,
    "horizontal_framed_glass": 0,
    "vertical_framed_glass": 0,
    "oak_window": 13,
    "spruce_window": 34,
    "birch_window": 2,
    "jungle_window": 10,
    "acacia_window": 15,
    "dark_oak_window": 26,
    "mangrove_window": 28,
    "crimson_window": 53,
    "warped_window": 56,
    "cherry_window": 36,
    "bamboo_window": 18,
    "ornate_iron_window": 44,
    "industrial_iron_window": 21,
    "weathered_iron_window": 44,
}
WINDOW_BLOCKS = tuple(family + suffix for family in WINDOW_COLORS for suffix in ("", "_pane"))
WINDOW_IDS = {f"create:{name}" for name in WINDOW_BLOCKS}


def window_face_culling(name):
    family = name.removesuffix("_pane")
    if family == "tiled_glass":
        return None
    if name.endswith("_pane"):
        return "connected_pane"
    if family.endswith("framed_glass"):
        return "connected_glass"
    if family in ("birch_window", "weathered_iron_window"):
        return "translucent_window"
    return "cutout_window"


def prepare_windows(generated, content, write_json, ingredient):
    declarations = content / "data/create/horizon"
    for name in WINDOW_BLOCKS:
        pane = name.endswith("_pane")
        family = name.removesuffix("_pane")
        properties = {
            "map_color": WINDOW_COLORS[family],
            "hardness": 0.3,
            "explosion_resistance": 0.3,
            "occludes": False,
        }
        if mode := window_face_culling(name):
            properties["face_culling"] = mode
        write_json(declarations / f"block/{name}.json", {
            "template": "minecraft:glass_pane" if pane else "minecraft:glass",
            "item": True,
            "properties": properties,
        })
        relative = Path(f"data/create/loot_table/blocks/{name}.json")
        table = json.loads((generated / relative).read_bytes())
        pool, = table["pools"]
        silk_touch, = pool.pop("conditions")
        silk_touch["type"] = silk_touch.pop("condition")
        pool["condition"] = silk_touch
        write_json(content / relative, table)

    for relative, recipe in palette_recipes(generated, WINDOW_IDS):
        write_json(content / relative, normalize_recipe(recipe, ingredient))

    for family, color in WINDOW_COLORS.items():
        if color:
            continue
        for suffix in ("", "_pane"):
            glass = f"glass{suffix}"
            relative = Path(f"data/create/recipe/smelting/{glass}_from_{family}{suffix}.json")
            recipe = json.loads((generated / relative).read_bytes())
            recipe["ingredient"] = ingredient(recipe["ingredient"])
            write_json(content / relative, recipe)

    for relative, values in palette_tags(generated, WINDOW_IDS):
        target = content / relative
        tag = json.loads(target.read_bytes()) if target.is_file() else {"values": []}
        tag["values"].extend(value for value in values if value not in tag["values"])
        write_json(target, tag)

    # NeoForge supplies the vanilla entries in the source recipes' convention tags.
    for kind, vanilla in (("blocks", "glass"), ("panes", "glass_pane")):
        target = content / f"data/c/tags/item/glass_{kind}/colorless.json"
        tag = json.loads(target.read_bytes())
        tag["values"].append(f"minecraft:{vanilla}")
        write_json(target, tag)

    tab = declarations / "creative_tab/palettes.json"
    creative = json.loads(tab.read_bytes())
    creative["items"][:0] = [f"create:{name}" for name in WINDOW_BLOCKS]
    write_json(tab, creative)

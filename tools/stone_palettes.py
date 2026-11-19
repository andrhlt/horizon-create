"""Generate Create's native decorative stone families."""

import json
from shutil import copy2

# Values captured from the pinned Create registries. Shape templates supply
# their vanilla placement, waterlogging and collision behavior.
MATERIALS = {
    "asurine": ("deepslate", 1.25, 6.0, 25),
    "crimsite": ("deepslate", 1.25, 6.0, 28),
    "limestone": ("sandstone", 1.25, 0.8, 2),
    "ochrum": ("calcite", 1.25, 0.75, 40),
    "scoria": ("blackstone", 1.5, 6.0, 26),
    "scorchia": ("blackstone", 1.5, 6.0, 43),
    "veridium": ("tuff", 1.25, 6.0, 55),
}
VANILLA_MATERIALS = {
    "andesite": ("stone", 1.5, 6.0, 11),
    "calcite": ("calcite", 0.75, 0.75, 36),
    "deepslate": ("deepslate", 3.0, 6.0, 59),
    "diorite": ("stone", 1.5, 6.0, 14),
    "dripstone": ("dripstone_block", 1.5, 1.0, 48),
    "granite": ("stone", 1.5, 6.0, 10),
    "tuff": ("tuff", 1.5, 6.0, 43),
}
PARTIAL_TEMPLATES = {
    "slab": "stone_brick_slab",
    "stairs": "stone_brick_stairs",
    "wall": "stone_brick_wall",
}


def palette_blocks(materials, include_base):
    for family, (base, hardness, resistance, color) in materials.items():
        props = {
            "hardness": hardness,
            "explosion_resistance": resistance,
            "map_color": color,
            "requires_tool": True,
            "sounds": f"minecraft:{base}",
        }
        for name, partial_prefix in (
            (f"cut_{family}", f"cut_{family}"),
            (f"polished_cut_{family}", f"polished_cut_{family}"),
            (f"cut_{family}_bricks", f"cut_{family}_brick"),
            (f"small_{family}_bricks", f"small_{family}_brick"),
            (family, None),
            (f"layered_{family}", None),
        ):
            if name == family and not include_base:
                continue
            yield name, {"template": "minecraft:stone", "item": True, "properties": props}
            if partial_prefix:
                for part, template in PARTIAL_TEMPLATES.items():
                    yield f"{partial_prefix}_{part}", {
                        "template": f"minecraft:{template}", "item": True, "properties": props,
                    }
        directions = ("north", "south", "west", "east")
        yield f"{family}_pillar", {
            "template": "minecraft:purpur_pillar",
            "item": True,
            "properties": props,
            "state_properties": {side: {"type": "boolean"} for side in directions},
            "default_state": {side: "false" for side in directions},
        }


PALETTE_BLOCKS = dict(palette_blocks(MATERIALS, include_base=True))
VANILLA_PALETTE_BLOCKS = dict(palette_blocks(VANILLA_MATERIALS, include_base=False))
ALL_PALETTE_BLOCKS = PALETTE_BLOCKS | VANILLA_PALETTE_BLOCKS
PALETTE_IDS = {f"create:{name}" for name in PALETTE_BLOCKS}


def palette_recipes(generated, ids=PALETTE_IDS):
    kinds = ("minecraft:stonecutting", "minecraft:crafting_shaped", "minecraft:crafting_shapeless")
    for path in sorted((generated / "data/create/recipe").glob("*.json")):
        recipe = json.loads(path.read_text(encoding="utf-8"))
        if recipe["type"] in kinds and recipe["result"]["id"] in ids:
            yield path.relative_to(generated), recipe


def palette_tags(generated, ids=PALETTE_IDS):
    for path in sorted((generated / "data").glob("*/tags/**/*.json")):
        tag = json.loads(path.read_text(encoding="utf-8"))
        values = [value for value in tag["values"]
                  if (value if isinstance(value, str) else value["id"]) in ids]
        if values:
            yield path.relative_to(generated), values


def normalize_recipe(recipe, ingredient):
    match recipe["type"]:
        case "minecraft:stonecutting":
            recipe["ingredient"] = ingredient(recipe["ingredient"])
        case "minecraft:crafting_shaped":
            recipe["key"] = {key: ingredient(value) for key, value in recipe["key"].items()}
        case "minecraft:crafting_shapeless":
            recipe["ingredients"] = [ingredient(value) for value in recipe["ingredients"]]
    return recipe


def prepare_palettes(generated, content, write_json, ingredient, *, extra_tag_ids=()):
    declarations = content / "data/create/horizon"
    ids = {f"create:{name}" for name in ALL_PALETTE_BLOCKS}
    for name, options in ALL_PALETTE_BLOCKS.items():
        write_json(declarations / f"block/{name}.json", options)

    for relative, recipe in palette_recipes(generated, ids):
        write_json(content / relative, normalize_recipe(recipe, ingredient))
    for family in VANILLA_MATERIALS:
        output = "dripstone_block" if family == "dripstone" else family
        relative = f"data/create/recipe/{output}_from_stone_types_{family}_stonecutting.json"
        original = json.loads((generated / relative).read_text(encoding="utf-8"))
        write_json(content / relative, normalize_recipe(original, ingredient))

    for relative, values in palette_tags(generated, ids.union(extra_tag_ids)):
        dest = content / relative
        if relative.parent.name == "stone_types":
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy2(generated / relative, dest)
            continue
        tag = json.loads(dest.read_text(encoding="utf-8")) if dest.is_file() else {"values": []}
        tag["values"].extend(value for value in values if value not in tag["values"])
        write_json(dest, tag)

    language = json.loads((generated / "assets/create/lang/en_us.json").read_text(encoding="utf-8"))
    write_json(declarations / "creative_tab/palettes.json", {
        "title": language["itemGroup.create.palettes"],
        "icon": "create:ornate_iron_window",
        "items": [f"create:{name}" for name in ALL_PALETTE_BLOCKS],
    })

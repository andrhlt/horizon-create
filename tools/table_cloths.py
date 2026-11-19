"""Import the non-shop Table Cloth blocks and their ordinary recipes."""

import json
from pathlib import Path
from shutil import copy2

COLORS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
          "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")
TABLE_CLOTHS = tuple(f"{name}_table_cloth" for name in (*COLORS, "andesite", "brass", "copper"))


def prepare_table_cloths(generated, content, write_json, crafting_ingredient, upgrade_block_loot):
    for name in TABLE_CLOTHS:
        material = name.removesuffix("_table_cloth")
        template = f"minecraft:{material}_carpet" if material in COLORS else {
            "andesite": "minecraft:andesite", "brass": "minecraft:iron_block",
            "copper": "minecraft:copper_block",
        }[material]
        write_json(content / f"data/create/horizon/block/{name}.json", {
            "template": template, "item": True,
            "properties": {"occludes": False},
            "state_properties": {"entity": {"type": "boolean"}},
            "default_state": {"entity": "false"},
            "shapes": {"default": [[-1/16, -9/16, -1/16, 17/16, 1/16, 17/16]]},
            "collision_shapes": {"default": [[0, 0, 0, 1, 1/16, 1]]},
        })
        loot = Path(f"data/create/loot_table/blocks/{name}.json")
        table = json.loads((generated / loot).read_bytes())
        upgrade_block_loot(table)
        write_json(content / loot, table)
        crafting_suffixes = ("", "_from_other_table_cloth", "_clear") if material in COLORS else ("_clear",)
        for suffix in crafting_suffixes:
            path = Path(f"data/create/recipe/crafting/logistics/{name}{suffix}.json")
            recipe = json.loads((generated / path).read_bytes())
            recipe["ingredients"] = [crafting_ingredient(i) for i in recipe["ingredients"]]
            write_json(content / path, recipe)
        if material not in COLORS:
            ingredient = {"andesite": "andesite_alloy", "brass": "ingots_brass", "copper": "ingots_copper"}[material]
            path = Path(f"data/create/recipe/{name}_from_{ingredient}_stonecutting.json")
            recipe = json.loads((generated / path).read_bytes())
            recipe["ingredient"] = crafting_ingredient(recipe["ingredient"])
            write_json(content / path, recipe)
    for kind, tags in (("block", ("table_cloths",)), ("item", ("table_cloths", "dyed_table_cloths"))):
        for tag in tags:
            path = Path(f"data/create/tags/{kind}/{tag}.json")
            (content / path).parent.mkdir(parents=True, exist_ok=True)
            copy2(generated / path, content / path)
    for tag, names in (
        ("combination_step_sound_blocks", TABLE_CLOTHS[:16]),
        ("inside_step_sound_blocks", TABLE_CLOTHS[16:]),
        ("mineable/pickaxe", TABLE_CLOTHS[16:]),
    ):
        path = content / f"data/minecraft/tags/block/{tag}.json"
        data = json.loads(path.read_bytes()) if path.exists() else {"values": []}
        for name in names:
            value = f"create:{name}"
            if value not in data["values"]:
                data["values"].append(value)
        write_json(path, data)
    tab = content / "data/create/horizon/creative_tab/palettes.json"
    data = json.loads(tab.read_bytes())
    data["items"].extend(f"create:{name}" for name in TABLE_CLOTHS)
    write_json(tab, data)

"""Import the original Create copper shingle and tile families."""
import json

from stone_palettes import normalize_recipe, palette_tags

AGES = ("", "exposed_", "weathered_", "oxidized_")
COPPER_ROOFS = {
    f"{wax}{age}copper_{family}{shape}": f"minecraft:{wax}{age}{template}"
    for wax in ("", "waxed_")
    for age in AGES
    for family in ("shingle", "tile")
    for shape, template in (
        ("s", "copper_block" if not age else "copper"),
        ("_slab", "cut_copper_slab"),
        ("_stairs", "cut_copper_stairs"),
    )
}


def prepare_copper_roofs(generated, content, write_json, ingredient):
    ids = {f"create:{name}" for name in COPPER_ROOFS}
    for name, template in COPPER_ROOFS.items():
        write_json(content / f"data/create/horizon/block/{name}.json", {
            "template": template,
            "item": True,
            "properties": {
                "hardness": 3.0,
                "explosion_resistance": 6.0,
                "requires_tool": True,
                "sounds": "minecraft:copper_block",
            },
        })

    for path in sorted((generated / "data/create/recipe").rglob("*.json")):
        recipe = json.loads(path.read_bytes())
        result = recipe.get("result")
        if isinstance(result, dict) and result.get("id") in ids:
            write_json(content / path.relative_to(generated), normalize_recipe(recipe, ingredient))

    for relative, values in palette_tags(generated, ids):
        path = content / relative
        tag = json.loads(path.read_bytes()) if path.is_file() else {"values": []}
        tag["values"].extend(value for value in values if value not in tag["values"])
        write_json(path, tag)

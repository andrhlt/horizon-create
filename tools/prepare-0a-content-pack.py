#!/usr/bin/env python3
"""Normalize a Create .hmod content pack for the pinned Horizon 0a schema.

The 0a block definition schema and registry paths differ from the upstream
Create pack. This converter makes the narrow schema/path translations needed
for 0a and evaluates optional NeoForge recipe conditions against the content
actually present in this pack. Every omission or translation is reported.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

UNSUPPORTED_0A_PROPERTIES = {
    "face_culling", "fall_distance_reduction", "legacy_bounce_facing",
    "legacy_bounce_restitution", "piston_push_only", "skylight_down",
    "straight_rail", "trapdoor_sound_source", "waterloggable",
}

def normalize(source: Path, output: Path, report: Path) -> None:
    removed: dict[str, list[str]] = {}
    translated: dict[str, dict[str, str]] = {}
    added: list[str] = []
    loot_condition_arrays: list[str] = []
    removed_duplicate_fluid_blocks: list[str] = []
    removed_duplicate_fluid_items: list[str] = []
    skipped_optional_recipes: list[dict[str, str]] = []
    translated_worldgen_paths: list[dict[str, str]] = []
    with ZipFile(source) as original, ZipFile(output, "w", ZIP_DEFLATED) as normalized:
        nonempty_tags: set[str] = set()
        for name in original.namelist():
            parts = Path(name).parts
            if (len(parts) < 6 or parts[0] != "data" or parts[2] != "tags"
                    or not name.endswith(".json")):
                continue
            namespace, registry = parts[1], parts[3]
            tag_path = "/".join(parts[4:])[:-5]
            definition = json.loads(original.read(name))
            if definition.get("values"):
                nonempty_tags.add(f"{namespace}:{tag_path}")
        fluid_names = {
            Path(name).stem for name in original.namelist()
            if name.startswith("data/create/horizon/fluid/") and name.endswith(".json")
        }
        fluid_block_names = {f"data/create/horizon/block/{name}.json" for name in fluid_names}
        fluid_item_names = {f"data/create/horizon/item/{name}_bucket.json" for name in fluid_names}
        for entry in original.infolist():
            if entry.filename in fluid_block_names:
                removed_duplicate_fluid_blocks.append(entry.filename)
                continue
            if entry.filename in fluid_item_names:
                removed_duplicate_fluid_items.append(entry.filename)
                continue
            payload = original.read(entry.filename)
            if entry.filename.startswith("data/create/recipe/") and entry.filename.endswith(".json"):
                definition = json.loads(payload)
                conditions = definition.get("neoforge:conditions")
                if conditions is not None:
                    if not isinstance(conditions, list):
                        raise ValueError(f"invalid neoforge:conditions in {entry.filename}")
                    keep = True
                    for condition in conditions:
                        if (not isinstance(condition, dict)
                                or condition.get("type") != "neoforge:not"
                                or not isinstance(condition.get("value"), dict)):
                            raise ValueError(f"unsupported optional recipe condition in {entry.filename}: {condition!r}")
                        nested = condition["value"]
                        kind = nested.get("type")
                        if kind == "neoforge:tag_empty":
                            tag = nested.get("tag")
                            if not isinstance(tag, str):
                                raise ValueError(f"invalid tag_empty condition in {entry.filename}")
                            keep &= tag in nonempty_tags
                            if tag not in nonempty_tags:
                                skipped_optional_recipes.append({"file": entry.filename, "reason": f"optional tag is empty or absent: {tag}"})
                        elif kind == "neoforge:mod_loaded":
                            mod = nested.get("modid")
                            if not isinstance(mod, str):
                                raise ValueError(f"invalid mod_loaded condition in {entry.filename}")
                            keep = False
                            skipped_optional_recipes.append({"file": entry.filename, "reason": f"optional integration is not installed: {mod}"})
                        else:
                            raise ValueError(f"unsupported optional recipe condition in {entry.filename}: {kind!r}")
                    if not keep:
                        continue
                    definition.pop("neoforge:conditions")
                    payload = (json.dumps(definition, indent=2, ensure_ascii=False) + "\n").encode()
            if (entry.filename.startswith("data/create/horizon/") or entry.filename.startswith("data/create/loot_table/")) and entry.filename.endswith(".json"):
                definition = json.loads(payload)
                changed = False
                properties = definition.get("properties")
                if entry.filename.startswith("data/create/horizon/block/") and isinstance(properties, dict):
                    unsupported = sorted(UNSUPPORTED_0A_PROPERTIES & properties.keys())
                    if unsupported:
                        for key in unsupported:
                            del properties[key]
                        removed[entry.filename] = unsupported
                        changed = True
                if entry.filename.startswith("data/create/horizon/item/") and "place_block" in definition:
                    definition["block"] = definition.pop("place_block")
                    translated[entry.filename] = {"place_block": "block"}
                    changed = True
                if entry.filename.startswith("data/create/horizon/creative_tab/") and "search_items" in definition:
                    items = definition.setdefault("items", [])
                    items.extend(item for item in definition.pop("search_items") if item not in items)
                    translated[entry.filename] = {"search_items": "items (merged, de-duplicated)"}
                    changed = True
                if entry.filename.startswith("data/create/horizon/fluid/") and "template" in definition:
                    definition = {
                        "sprite": definition.get("still"),
                        "tint": definition.get("tint"),
                        "world": {
                            "tick_delay": definition.get("tick_rate", 5),
                            "drop_off": definition.get("level_decrease_per_block", 1),
                            "slope_find_distance": definition.get("slope_find_distance", 4),
                            "source_conversion": definition.get("can_convert_to_source", False),
                            "bucket": bool(definition.get("bucket")),
                        },
                    }
                    translated[entry.filename] = {
                        "template": "sprite=still",
                        "tick_rate": "world.tick_delay",
                        "level_decrease_per_block": "world.drop_off",
                        "can_convert_to_source": "world.source_conversion",
                        "bucket": "world.bucket",
                        "viscosity": "omitted (not represented by Horizon 0a)",
                        "density": "omitted (not represented by Horizon 0a)",
                        "explosion_resistance": "omitted (not represented by Horizon 0a)",
                        "flowing": "omitted (uses the still sprite for this fluid look)",
                    }
                    changed = True
                if entry.filename.startswith("data/create/loot_table/"):
                    def normalize_conditions(value, location=""):
                        nonlocal changed
                        if isinstance(value, dict):
                            for key, child in list(value.items()):
                                if key == "condition" and isinstance(child, list):
                                    value[key] = {"type": "minecraft:all_of", "terms": child}
                                    loot_condition_arrays.append(entry.filename + location + "/condition")
                                    changed = True
                                else:
                                    normalize_conditions(child, location + "/" + key)
                        elif isinstance(value, list):
                            for index, child in enumerate(value):
                                normalize_conditions(child, location + f"/{index}")
                    normalize_conditions(definition)
                if changed:
                    payload = (json.dumps(definition, indent=2, ensure_ascii=False) + "\n").encode()
            target_name = entry.filename
            if "/worldgen/configured_feature/" in target_name:
                target_name = target_name.replace("/worldgen/configured_feature/", "/worldgen/feature/")
                translated_worldgen_paths.append({"source": entry.filename, "target": target_name})
            normalized.writestr(target_name, payload)
        for menu in ("sequenced_gearshift", "rotation_speed_controller"):
            name = f"data/create/horizon/menu/{menu}.json"
            if name not in original.namelist():
                normalized.writestr(name, '{"slots": 1, "data_slots": 0}\n')
                added.append(name)
    report.write_text(json.dumps({
        "source": str(source), "output": str(output),
        "target_horizon": "0a875da91dbb0fdcb7ba8c42c11341aa229af51a",
        "removed_property_count": sum(map(len, removed.values())),
        "removed_properties_by_file": removed,
        "translated_fields_by_file": translated,
        "added_menu_files": added,
        "removed_duplicate_fluid_blocks": removed_duplicate_fluid_blocks,
        "removed_duplicate_fluid_items": removed_duplicate_fluid_items,
        "loot_condition_arrays_normalized": loot_condition_arrays,
        "optional_recipes_skipped": skipped_optional_recipes,
        "worldgen_configured_feature_path_translations": translated_worldgen_paths,
    }, indent=2) + "\n")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="source Create .hmod")
    parser.add_argument("output", type=Path, help="normalized output .hmod")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("source and output must be different files")
    normalize(args.source, args.output, args.report)
    print(args.output)

if __name__ == "__main__":
    main()

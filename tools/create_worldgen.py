"""Prepare the pinned Create ore features for Horizon's worldgen data format."""

import json
from pathlib import Path
from shutil import copy2

FEATURES = ("striated_ores_overworld", "striated_ores_nether", "zinc_ore")
DEEPSLATE = {"predicate_type": "minecraft:tag_match", "tag": "minecraft:deepslate_ore_replaceables"}


def configured_feature(original):
    feature = {"type": original["type"], **original["config"]}
    groups = [feature["targets"]] if "targets" in feature else [
        group for pattern in feature["layer_patterns"] for layer in pattern for group in layer["targets"]
    ]
    for group in groups:
        for entry in group:
            state = entry["state"]
            entry["state"] = ({"id": state["Name"], "properties": state["Properties"]}
                              if "Properties" in state else state["Name"])
            if entry["target"] == DEEPSLATE:
                # In 1.21.1 this tag includes Tuff. Horizon's vanilla tag is from 26.3.
                entry["target"] = {"predicate_type": "minecraft:any_of", "rules": [
                    DEEPSLATE, {"predicate_type": "minecraft:block_match", "block": "minecraft:tuff"},
                ]}
    return feature


def prepare_worldgen(generated, content, write_json):
    for feature in FEATURES:
        for folder in ("worldgen/configured_feature", "worldgen/placed_feature", "neoforge/biome_modifier"):
            path = Path(f"data/create/{folder}/{feature}.json")
            source, target = generated / path, content / path
            if folder.endswith("biome_modifier"):
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(source, target)
                continue
            data = json.loads(source.read_text())
            if folder.endswith("configured_feature"):
                data = configured_feature(data)
            else:
                # The original option defaults to enabling the feature.
                config_filter = data["placement"].pop()
                if config_filter != {"type": "create:config_filter"}:
                    raise ValueError(f"Unexpected Java placement filter in {path}: {config_filter}")
            write_json(target, data)

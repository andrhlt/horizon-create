#!/usr/bin/env python3
"""Check APP-2177 content against the pinned 0a block and item schema."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/data/create/horizon"
WATERLOGGABLE_BLOCKS = {
    "andesite_belt_funnel", "andesite_funnel", "belt", "brass_belt_funnel",
    "brass_funnel", "cart_assembler", "chute", "clipboard", "contraption_controls",
    "controls", "controller_rail", "copycat_panel", "copycat_step", "cogwheel",
    "copper_backtank", "copper_valve_handle", "depot", "desk_bell", "display_board",
    "factory_gauge", "fake_track", "fluid_pipe", "fluid_valve", "framed_glass_trapdoor",
    "glass_fluid_pipe", "hand_crank", "item_hatch", "large_bogey", "large_cogwheel",
    "mechanical_drill", "mechanical_harvester", "mechanical_piston_head",
    "mechanical_plough", "mechanical_pump", "mechanical_roller", "netherite_backtank",
    "nixie_tube", "placard", "powered_shaft", "piston_extension_pole", "pulley_magnet",
    "rope", "shaft", "small_bogey", "smart_fluid_pipe", "steam_engine", "stock_link",
    "track", "track_station", "train_trapdoor", "weighted_ejector", "white_seat",
}
PLACEABLE_ITEMS = {
    "copper_backtank", "copper_backtank_placeable", "netherite_backtank",
    "netherite_backtank_placeable", "vertical_gearbox",
}


def read(path):
    return json.loads(path.read_text())


def main():
    blocks = {path.stem: read(path) for path in (CONTENT / "block").glob("*.json")}
    items = {path.stem: read(path) for path in (CONTENT / "item").glob("*.json")}
    assert WATERLOGGABLE_BLOCKS <= blocks.keys()
    for name in WATERLOGGABLE_BLOCKS:
        block = blocks[name]
        assert "waterloggable" not in block.get("properties", {}), name
        inherited = block["template"] == "minecraft:oak_trapdoor"
        state_property = block.get("state_properties", {}).get("waterlogged", {}).get("type") == "boolean"
        assert inherited or state_property, f"{name} lost its waterlogged state"
        if state_property:
            assert block.get("default_state", {}).get("waterlogged") == "false", name
    for name in PLACEABLE_ITEMS:
        item = items[name]
        assert "place_block" not in item, name
        target = item.get("block")
        assert target and target.removeprefix("create:") in blocks, (name, target)

    assert '"waterloggable"' not in (ROOT / "tools/prepare.py").read_text()
    assert '"waterloggable"' not in (ROOT / "tools/toolboxes.py").read_text()
    print(f"Pinned content schema: {len(WATERLOGGABLE_BLOCKS)} waterlogged blocks and {len(PLACEABLE_ITEMS)} block items pass")


if __name__ == "__main__":
    main()

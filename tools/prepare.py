#!/usr/bin/env python3
"""Prepare the supported assets and GameTest fixtures from Create’s source checkout."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from shutil import copy2, copytree
from tempfile import TemporaryDirectory
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from copper_roofs import COPPER_ROOFS, prepare_copper_roofs
from create_worldgen import prepare_worldgen
from copper_casing_ctm import prepare_copper_casing
from framed_glass_ctm import prepare_framed_glass
from stone_palettes import ALL_PALETTE_BLOCKS, prepare_palettes
from toolboxes import TOOLBOXES, prepare_toolboxes
from table_cloths import TABLE_CLOTHS, prepare_table_cloths
from weathered_window_ctm import prepare_weathered_window
from window_ctm import prepare_industrial_window, prepare_vertical_windows
from window_palettes import WINDOW_BLOCKS, prepare_windows

ROOT = Path(__file__).resolve().parents[1]
MOTOR_MENU = Path("data/create/horizon/menu/creative_motor.json")
CREATE_REVISION = "ac0c444d9828da3453ae8cc65338e8de063286fb"
FIXTURES = ("processing/wheat_milling", "processing/track_crafting", "processing/crushing_wheel_crafting", "processing/precision_mechanism_crafting", "processing/water_filling_bottle", "processing/sand_washing", "processing/stone_cobble_sand_crushing", "processing/brass_mixing", "processing/potion_brewing", "processing/brass_mixing_2", "processing/spout_crafting", "fluids/small_waterwheel", "fluids/large_waterwheel", "fluids/waterwheel_materials", "fluids/in_world_pumping_in", "fluids/in_world_pumping_out", "fluids/3_pipe_split", "fluids/3_pipe_combine", "fluids/steam_engine", "fluids/hose_pulley_transfer", "fluids/spouting", "fluids/threshold_switch", "fluids/smart_observer_pipes", "items/depot_comparator_output", "items/threshold_switch",
    *(f"items/brass_tunnel_{mode}" for mode in ("filtering", "prefer_nearest", "round_robin", "split", "sync_input")),
    "contraptions/vaults_protect_fuel", "contraptions/crop_farming", "contraptions/controls", "contraptions/elevator",
    "contraptions/roller_filling", "contraptions/roller_paving_and_clearing",
    "contraptions/ploughing", "contraptions/arrow_dispenser",
    "contraptions/dispensers_dont_fight", "contraptions/dispensers_refill",
    "contraptions/mounted_item_extract", "contraptions/mounted_fluid_drain",
    "contraptions/redstone_contacts", "misc/shearing", "misc/netherite_backtank", "misc/schematicannon",
    "items/storages", "items/belt_coaster", "items/attribute_filters",
    "fluids/open_pipes",
    "regressions/issue9615_efficient_deployers",
    "items/smart_observer_belt_and_funnel", "items/smart_observer_counting", "items/depot_display",
    "items/smart_observer_storage", "items/smart_observer_filtered_storage",
    "misc/smart_observer_blocks", "misc/threshold_switch_pulley", "items/smart_observer_chutes", "items/andesite_tunnel_split", "items/fan_processing", "items/vault_comparator_output", "items/arm_multi_output", "items/arm_purgatory",
)
# Map colors captured from the pinned sail GameTest.
DYED_SAILS = {
    "orange_sail": 15, "magenta_sail": 16, "light_blue_sail": 17, "yellow_sail": 18,
    "lime_sail": 19, "pink_sail": 20, "gray_sail": 21, "light_gray_sail": 22,
    "cyan_sail": 23, "purple_sail": 24, "blue_sail": 25, "brown_sail": 26,
    "green_sail": 27, "red_sail": 28, "black_sail": 29,
}
VALVE_DYES = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)
DYED_VALVE_HANDLES = tuple(f"{color}_valve_handle" for color in VALVE_DYES)
DYED_NIXIES = tuple(f"{color}_nixie_tube" for color in VALVE_DYES if color != "orange")
SEAT_COLORS = dict(zip(VALVE_DYES, (8, *range(15, 30)), strict=True))
SEATS = tuple(f"{color}_seat" for color in SEAT_COLORS)
POSTBOXES = tuple(f"{color}_postbox" for color in SEAT_COLORS)

SLIDING_DOORS = ("andesite_door", "brass_door", "copper_door", "train_door", "framed_glass_door")
ADVANCEMENTS = (
    "root", "andesite_alloy", "andesite_casing", "water_wheel", "lava_wheel_00000",
    "mechanical_press", "windmill", "shifting_gears", "millstone", "super_glue",
    "contraption_actors", "portable_storage_interface", "belt_funnel_kiss",
)

ENCASED_COGWHEELS = (
    "brass_encased_cogwheel", "andesite_encased_cogwheel",
    "andesite_encased_large_cogwheel", "brass_encased_large_cogwheel",
)

ZINC_BLOCKS = ("zinc_ore", "deepslate_zinc_ore", "raw_zinc_block", "zinc_block")
ORE_COOKING = (
    "zinc_ingot_from_ore", "zinc_ingot_from_raw_ore",
    *(f"{metal}_ingot_from_crushed" for metal in ("zinc", "iron", "gold", "copper")),
)

METAL_SCAFFOLDING = ("andesite_scaffolding", "brass_scaffolding", "copper_scaffolding")
METAL_DECORATIONS = (*METAL_SCAFFOLDING, *(
    f"{metal}_{part}" for metal in ("andesite", "brass", "copper") for part in ("bars", "ladder")
))
METAL_INGREDIENTS = {"andesite": "andesite_alloy", "brass": "ingots_brass", "copper": "ingots_copper"}
IRON_DECORATIONS = ("industrial_iron_block", "weathered_iron_block")
METAL_BLOCKS = ("andesite_alloy_block", *IRON_DECORATIONS)
ROSE_QUARTZ_PALETTE = {
    "rose_quartz_block": "rose_quartz",
    "rose_quartz_tiles": "polished_rose_quartz",
    "small_rose_quartz_tiles": "polished_rose_quartz",
}

BRASS_DIODES = ("pulse_extender", "pulse_repeater", "pulse_timer")

BLOCKS = (
    "honey", "chocolate",
    *BRASS_DIODES, *ZINC_BLOCKS, *METAL_DECORATIONS, *METAL_BLOCKS, *COPPER_ROOFS,
    *SLIDING_DOORS, *DYED_VALVE_HANDLES, *DYED_NIXIES, *SEATS, *TABLE_CLOTHS,
    "wooden_bracket", "metal_bracket", "experience_block", "item_hatch", "copper_backtank", "netherite_backtank",
    *ALL_PALETTE_BLOCKS, *ROSE_QUARTZ_PALETTE,
    *WINDOW_BLOCKS, "cardboard_block", "bound_cardboard_block", "packager", "repackager", "factory_gauge", "stock_link", "redstone_requester", "stock_ticker", "rose_quartz_lamp", "powered_latch", "powered_toggle_latch", "desk_bell", "peculiar_bell", "haunted_bell",
    "windmill_bearing", "clockwork_bearing", "cuckoo_clock", "mysterious_cuckoo_clock", "sail_frame", "white_sail", *DYED_SAILS,
    "sticker", "mechanical_roller", "cart_assembler", "minecart_anchor", "controller_rail", "mechanical_harvester", "contraption_controls", "elevator_pulley", "elevator_contact",
    "mechanical_piston", "sticky_mechanical_piston", "piston_extension_pole", "mechanical_piston_head", "mechanical_plough",
    "portable_storage_interface", "portable_fluid_interface",
    "cogwheel", "large_cogwheel", "shaft", "flywheel", "hand_crank", "creative_motor", "millstone", "smart_chute", "shadow_steel_casing", "refined_radiance_casing", "schematicannon", "schematic_table", "brass_block", "brass_casing", "andesite_casing", "mechanical_press", "mechanical_saw", "mechanical_drill", "mechanical_crafter", "belt", "andesite_tunnel", "brass_tunnel", "encased_fan",
    "clutch", "gearbox", "gearshift", "deployer", "chute", "depot", "nixie_tube", "redstone_contact", "redstone_link", "analog_lever", "display_link", "display_board", "metal_girder", "metal_girder_encased_shaft", "stockpile_switch", "content_observer",
    "water_wheel", "large_water_wheel", "speedometer", "stressometer", "item_drain", "water_wheel_structure", "copycat_panel", "copycat_step", "copycat_base", "copycat_bars", "andesite_belt_funnel", "brass_belt_funnel", "creative_crate", "andesite_funnel", "brass_funnel", "item_vault", "crushing_wheel", "crushing_wheel_controller", "andesite_encased_shaft", "brass_encased_shaft",
    "chain_conveyor", "package_frogport", "lectern_controller", "clipboard", "placard", "turntable", "nozzle", "train_trapdoor", "framed_glass_trapdoor", *POSTBOXES, *TOOLBOXES,
    "rope", "pulley_magnet", "fake_track", "track_station", "track_signal", "track_observer", "controls", "gantry_shaft", "gantry_carriage", "railway_casing", "small_bogey", "large_bogey",
    "basin", "copper_casing", "mechanical_pump", "fluid_pipe", "glass_fluid_pipe", "encased_fluid_pipe", "smart_fluid_pipe", "fluid_tank", "steam_whistle", "steam_whistle_extension", "mechanical_mixer", "blaze_burner", "lit_blaze_burner", "steam_engine", "powered_shaft", "creative_fluid_tank", "mechanical_arm", "mechanical_bearing", "linear_chassis", "secondary_linear_chassis", "radial_chassis", "encased_chain_drive", "adjustable_chain_gearshift", "rotation_speed_controller", "spout", "weighted_ejector", "track", *ENCASED_COGWHEELS, "fluid_valve", "copper_valve_handle", "hose_pulley", "rope_pulley", "sequenced_gearshift",
)
CARDBOARD_PACKAGES = (
    "cardboard_package_12x12", "cardboard_package_10x12",
    "cardboard_package_10x8", "cardboard_package_12x10",
)
RARE_PACKAGES = tuple(f"rare_{name}_package" for name in (
    "creeper", "darcy", "evan", "jinx", "kryppers", "simi", "starlotte", "thunder", "up", "vector",
))
PACKAGES = (*CARDBOARD_PACKAGES, *RARE_PACKAGES)

CARDBOARD_ARMOR = tuple(f"cardboard_{piece}" for piece in ("helmet", "chestplate", "leggings", "boots"))
CART_CONTRAPTION_ITEMS = ("minecart_contraption", "furnace_minecart_contraption", "chest_minecart_contraption")
ITEMS = ("tree_fertilizer", *CART_CONTRAPTION_ITEMS, *PACKAGES, *CARDBOARD_ARMOR, "cardboard_sword", "extendo_grip", "potato_cannon", "linked_controller", "crafting_blueprint", "wand_of_symmetry", "minecart_coupling", "handheld_worldshaper", "honey_bucket", "chocolate_bucket", *(name for name in BLOCKS if name not in ("lectern_controller", "fake_track", "honey", "chocolate", "lit_blaze_burner", "steam_whistle_extension", "mechanical_piston_head", "water_wheel_structure", "minecart_anchor", "belt", "andesite_belt_funnel", "brass_belt_funnel", "crushing_wheel_controller", "glass_fluid_pipe", "encased_fluid_pipe", "powered_shaft", "rope", "pulley_magnet", "small_bogey", "large_bogey", "metal_girder_encased_shaft", "copycat_base", "copycat_bars", *DYED_SAILS, *DYED_NIXIES)), "chromatic_compound", "refined_radiance", "shadow_steel", "pulp", "cardboard", "wheat_flour", "andesite_alloy", "iron_sheet", "copper_sheet", "golden_sheet", "belt_connector", "brass_ingot", "brass_sheet", "brass_hand", "propeller", "dough", "shopping_list", "experience_nugget", "crafter_slot_cover", "filter", "attribute_filter", "package_filter", "brass_nugget", "zinc_ingot", "raw_zinc", "crushed_raw_zinc", "empty_blaze_burner", "blaze_cake", "creative_blaze_cake", "whisk", "cinder_flour", "incomplete_track", "zinc_nugget", "incomplete_precision_mechanism", "precision_mechanism", "crushed_raw_gold", "crushed_raw_iron", "crushed_raw_copper", "crushed_raw_aluminum", "crushed_raw_lead", "crushed_raw_nickel", "crushed_raw_osmium", "crushed_raw_platinum", "crushed_raw_quicksilver", "crushed_raw_silver", "crushed_raw_tin", "crushed_raw_uranium", "copper_nugget", "sturdy_sheet", "unprocessed_obsidian_sheet", "powdered_obsidian", "super_glue", "transmitter", "sand_paper", "red_sand_paper", "rose_quartz", "polished_rose_quartz", "electron_tube", "schedule", "netherite_backtank", "netherite_diving_helmet", "netherite_diving_boots", "copper_diving_helmet", "copper_diving_boots", "copper_backtank_placeable", "netherite_backtank_placeable", "schematic", "empty_schematic", "schematic_and_quill", "goggles", "wrench", "blaze_cake_base", "bar_of_chocolate", "sweet_roll", "chocolate_glazed_berries", "honeyed_apple", "builders_tea", "vertical_gearbox")


def model_references(value):
    if isinstance(value, dict):
        for key, entry in value.items():
            if key in ("model", "parent") and isinstance(entry, str) and entry.startswith("create:"):
                name = entry.removeprefix("create:")
                yield name if name.endswith(".obj") else f"models/{name}.json"
            elif key == "textures" and isinstance(entry, dict):
                for texture in entry.values():
                    if isinstance(texture, str) and texture.startswith("create:"):
                        yield f"textures/{texture.removeprefix('create:')}.png"
            else:
                yield from model_references(entry)
    elif isinstance(value, list):
        for entry in value:
            yield from model_references(entry)


def bogey_display_blocks(content):
    names = ("bogey_frame", "bogey_wheel", "bogey_drive_wheel_pin",
             "bogey_drive_piston", "bogey_drive", "bogey_drive_wheel", "bogey_drive_belt")
    for part in names:
        name = f"carriage_{part}"
        write_json(content / f"data/create/horizon/block/{name}.json", {
            "template": "minecraft:iron_block", "properties": {"occludes": False},
        })
        write_json(content / f"assets/create/blockstates/{name}.json", {
            "variants": {"": {"model": f"create:block/track/bogey/{part}"}},
        })


def carriage_port_display_blocks(content):
    for port in ("portable_storage_interface", "portable_fluid_interface"):
        for part in ("block_middle", "block_middle_powered", "block_top"):
            name = f"carriage_{port}_{part}"
            write_json(content / f"data/create/horizon/block/{name}.json", {
                "template": "minecraft:iron_block", "item": False,
                "properties": {"occludes": False},
            })
            write_json(content / f"assets/create/blockstates/{name}.json", {
                "variants": {"": {"model": f"create:block/{port}/{part}"}},
            })


def copy_assets(resources, generated, content):
    for state, model in (("on", "redstone_torch"), ("off", "redstone_torch_off")):
        write_json(content / f"assets/create/items/stockpile_{state}.json", {
            "model": {"type": "minecraft:model", "model": f"minecraft:block/{model}"},
        })
    pending = [f"blockstates/{name}.json" for name in BLOCKS]
    pending.extend(("textures/gui/icons.png", "textures/gui/curiosities.png", "textures/gui/clipboard.png", "textures/gui/value_settings.png", "textures/gui/display_link.png", "textures/gui/factory_gauge.png", "textures/gui/sequencer.png", "textures/gui/threshold_switch.png"))
    pending.extend(f"models/item/{name}.json" for name in ITEMS)
    pending.extend(f"models/item/handheld_worldshaper/{part}.json" for part in ("core", "core_glow", "accelerator"))
    pending.extend(("models/item/wrench/gear.json", "models/item/cardboard_sword/item_in_hand.json",
                    "models/item/linked_controller/button.json", "models/item/linked_controller/powered.json"))
    pending.extend(f"models/item/clipboard_{mode}.json" for mode in range(3))
    pending.extend(f"models/item/package/rigging_{size}.json" for size in ("12x12", "10x12", "10x8", "12x10"))
    pending.extend(
        f"models/block/{name}/fold_{side}.json"
        for name in ("andesite_door", "copper_door") for side in ("left", "right")
    )
    pending.extend(f"models/block/{name}.json" for name in (
        *(f"chain_conveyor/{part}" for part in ("wheel", "shaft", "guard")),
        *(f"package_frogport/{part}" for part in ("body", "head", "head_goggles", "tongue")),
        "water_wheel/wheel", "gauge/dial", "gauge/speedometer/head", "gauge/stressometer/head", "fluid_valve/pointer",
        "large_cogwheel_shaftless", "cogwheel_shaft", "mechanical_press/head", "belt_pulley", "encased_fan/propeller", "mechanical_pump/cog", "cogwheel_shaftless", "mechanical_mixer/pole", "mechanical_mixer/head",
        "mechanical_drill/head", "shaft_half", "bearing/top_wooden", "bearing/top", "track_signal/indicator_on", "track_signal/indicator_off", *(f"mechanical_saw/blade_{orientation}_{motion}"
            for orientation in ("vertical", "horizontal") for motion in ("inactive", "active", "reversed")),
        *(f"mechanical_arm/{part}" for part in ("cog", "base", "lower_body", "upper_body", "claw_base", "upper_claw_grip", "lower_claw_grip")),
        *(f"hose_pulley/{part}" for part in ("hose_coil", "rope", "rope_half", "pulley_magnet", "rope_half_magnet")),
        *(f"rope_pulley/{part}" for part in ("rope_coil", "rope", "rope_half", "pulley_magnet", "rope_half_magnet")),
        *(f"elevator_pulley/{part}" for part in ("rope_coil", "rope", "rope_half", "pulley_magnet")),
        "goggles", "contraption_controls/button", "analog_lever/handle", "analog_lever/indicator", "desk_bell/plunger", "desk_bell/bell", "peculiar_bell", "haunted_bell",
        "packager/hatch_open", "packager/hatch_closed", "packager/tray", "factory_gauge/panel", "hand_crank/handle", "rotation_speed_controller/bracket",
        *(f"contraption_controls/indicator_{index}" for index in range(8)),
        *(f"track/bogey/{part}" for part in ("bogey_frame", "bogey_wheel", "bogey_drive_wheel_pin",
                                               "bogey_drive_piston", "bogey_drive", "bogey_drive_wheel",
                                               "bogey_drive_belt")),
        "track/tie", "track/segment_left", "track/segment_right",
        *(f"{port}/{part}" for port in ("portable_storage_interface", "portable_fluid_interface")
          for part in ("block_middle", "block_middle_powered", "block_top")),
        "schematicannon/pipe", "schematicannon/connector",
        "copper_backtank/block_cogs", "copper_backtank/block_shaft_input",
        *(f"fluid_pipe/{part}/{face}" for part in ("rim_connector", "drain")
          for face in ("down", "up", "north", "south", "west", "east")),
        "weighted_ejector/top", "spout/top", "spout/middle", "spout/bottom",
        "belt_funnel/flap", "funnel/flap",
        "steam_engine/piston", "steam_engine/linkage", "steam_engine/shaft_connector",
        "blaze_burner/block_with_blaze", "blaze_burner/block_with_fire", "blaze_burner/block_with_soul_fire",
        *(f"belt/{part}{suffix}" for part in ("start", "middle", "end") for suffix in ("", "_bottom")),
        *(f"belt/diagonal_{part}" for part in ("start", "middle", "end")),
    ))
    copied = set()
    while pending:
        name = pending.pop()
        if name in copied:
            continue
        relative = Path("assets/create") / name
        original = resources / relative
        if not original.is_file():
            original = generated / relative
        target = content / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(original, target)
        copied.add(name)
        if original.suffix == ".json":
            model = json.loads(original.read_text(encoding="utf-8"))
            if name in {f"models/item/{item}.json" for item in CARDBOARD_ARMOR}:
                # The 1.21.1 trim overrides refer to palette-generated sprites.
                model.pop("overrides", None)
            pending.extend(model_references(model))
        elif original.suffix == ".obj":
            for line in original.read_text(encoding="utf-8").splitlines():
                if line.startswith("mtllib "):
                    pending.append(str(Path(name).with_name(line.removeprefix("mtllib ").strip())))

    # Create renders the bell body separately from its attachment frame. Until
    # animated block entities are ported, include the original body at rest.
    for bell in ("peculiar_bell", "haunted_bell"):
        path = content / f"assets/create/blockstates/{bell}.json"
        variants = json.loads(path.read_text(encoding="utf-8"))["variants"]
        parts = []
        for key, frame in variants.items():
            properties = dict(pair.split("=") for pair in key.split(","))
            body = {"model": f"create:block/{bell}"}
            rotation = (frame.get("y", 0) + (90 if properties["attachment"] in ("single_wall", "double_wall") else 0)) % 360
            if rotation:
                body["y"] = rotation
            parts.extend(({"when": properties, "apply": frame}, {"when": properties, "apply": body}))
        write_json(path, {"multipart": parts})


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sliding_doors(content):
    closed = (
        (0, 0, 13, 16, 16, 16), (0, 0, 0, 3, 16, 16),
        (0, 0, 0, 16, 16, 3), (13, 0, 0, 16, 16, 16),
    )
    sliding = (
        (0, 0, -13, 3, 16, 3), (-13, 0, 0, 3, 16, 3),
        (13, 0, 13, 16, 16, 29), (13, 0, 13, 29, 16, 16),
        (13, 0, -13, 16, 16, 3), (13, 0, 0, 29, 16, 3),
        (0, 0, 13, 3, 16, 29), (-13, 0, 13, 3, 16, 16),
    )
    folded = (
        (0, 0, -3, 9, 16, 3), (-3, 0, 0, 3, 16, 9),
        (7, 0, 13, 16, 16, 19), (13, 0, 7, 19, 16, 16),
        (7, 0, -3, 16, 16, 3), (13, 0, 0, 19, 16, 9),
        (0, 0, 13, 9, 16, 19), (-3, 0, 7, 3, 16, 16),
    )
    assets = content / "assets/create"
    write_json(assets / "models/block/empty_sliding_door.json", {"elements": []})
    for name in SLIDING_DOORS:
        variant_path = assets / f"blockstates/{name}.json"
        states = json.loads(variant_path.read_text(encoding="utf-8"))
        for key in states["variants"]:
            if key.endswith("visible=false"):
                states["variants"][key] = {"model": "create:block/empty_sliding_door"}
        folds = name in ("andesite_door", "copper_door")
        opened = folded if folds else sliding
        shapes = {}
        for facing, shut, open_indices in zip(
            ("north", "east", "south", "west"), closed,
            ((7, 3), (0, 6), (5, 1), (2, 4)), strict=True,
        ):
            for hinge, index in zip(("left", "right"), open_indices, strict=True):
                for opening in ("false", "true"):
                    for visible in ("false", "true"):
                        box = shut if opening == "false" and visible == "true" else opened[index]
                        shapes[f"{facing},{hinge},{opening},{visible}"] = [[n / 16 for n in box]]
        write_json(content / f"data/create/horizon/block/{name}.json", {
            "template": "minecraft:oak_door",
            "state_properties": {"visible": {"type": "boolean"}},
            "default_state": {"visible": "true"},
            "properties": {"occludes": False},
            "shapes": {"properties": ["facing", "hinge", "open", "visible"], "values": shapes},
            "collision_shapes": {"properties": ["facing", "hinge", "open", "visible"], "values": shapes},
        })
        if folds:
            geometry = f"{name}_fold"
            write_json(content / f"data/create/horizon/block/{geometry}.json", {
                "template": "minecraft:stone", "item": False,
                "state_properties": {"pane": {"type": "enum", "values": ["left", "right"]}},
                "default_state": {"pane": "left"},
                "properties": {"occludes": False},
            })
            write_json(assets / f"blockstates/{geometry}.json", {
                "variants": {f"pane={side}": {"model": f"create:block/{name}/fold_{side}"}
                             for side in ("left", "right")},
            })
            write_json(variant_path, states)
            continue
        for half in ("lower", "upper"):
            segment = "block_bottom" if half == "lower" else "block_top"
            base = assets / f"models/block/{name}/{segment}.json"
            for hinge, shift in (("left", -13), ("right", 13)):
                model = json.loads(base.read_text(encoding="utf-8"))
                for element in model["elements"]:
                    for edge in ("from", "to"):
                        element[edge][0] += 0.5
                        element[edge][2] += shift
                write_json(base.with_stem(f"{segment}_open_{hinge}"), model)
                for facing in ("north", "east", "south", "west"):
                    key = f"facing={facing},half={half},hinge={hinge},open="
                    closed_state = states["variants"][f"{key}false,visible=true"]
                    states["variants"][f"{key}true,visible=true"] = {
                        **closed_state, "model": f"{closed_state['model']}_open_{hinge}",
                    }
        write_json(variant_path, states)


def complete_creative_tab(content):
    declarations = content / "data/create/horizon"
    registered = {f"create:{path.stem}" for path in (declarations / "item").glob("*.json")}
    registered.update(
        f"create:{path.stem}" for path in (declarations / "block").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8")).get("item", True)
    )
    with (ROOT / "fixtures/creative-tabs-java.csv").open(encoding="utf-8") as trace:
        rows = [row for row in csv.DictReader(trace) if row["item"] in registered]

    for name in ("base", "palettes"):
        path = declarations / f"creative_tab/{name}.json"
        tab = json.loads(path.read_text(encoding="utf-8"))
        visible = [row["item"] for row in rows if row["tab"] == name and row["visibility"] == "display"]
        tab["search_items"] = [row["item"] for row in rows if row["tab"] == name and row["visibility"] == "search"]
        if name == "base":
            # Java assigns 3D items first using its client item renderer.
            # Keep the port's existing order within the measured membership.
            allowed = set(visible)
            existing = [item for item in tab["items"] if item in allowed]
            visible = list(dict.fromkeys(existing + visible))
        tab["items"] = visible
        write_json(path, tab)


CRAFTING = (
    *(f"appliances/{gear}{suffix}" for gear in ("netherite_backtank", "netherite_diving_helmet", "netherite_diving_boots")
      for suffix in ("", "_from_netherite")),
    "appliances/book", "appliances/clipboard_clear", "appliances/crafting_blueprint", "appliances/item_frame", "appliances/linked_controller",
    "appliances/name_tag", "appliances/slime_ball", "curiosities/cake",
    "kinetics/fluid_tank", "kinetics/steam_whistle", "kinetics/item_vault", "kinetics/steam_engine",
    "materials/brass_ingot_from_decompacting", "materials/cardboard_from_bound_block", "palettes/scorchia",
    "kinetics/placard", "kinetics/chain_conveyor", "kinetics/turntable", "kinetics/nozzle", "kinetics/train_trapdoor", "kinetics/framed_glass_trapdoor", "logistics/package_frogport",
    *(f"logistics/{box}{suffix}" for box in POSTBOXES for suffix in ("", "_from_other_postbox")),
    "materials/experience_block", "materials/experience_nugget_from_block",
    "materials/copper_ingot", "materials/copper_nugget", "logistics/item_hatch",
    "appliances/copper_backtank", "appliances/copper_diving_helmet", "appliances/copper_diving_boots",
    "appliances/dough", "appliances/filter_clear", "appliances/attribute_filter_clear",
    "appliances/package_filter_clear", "appliances/schedule_clear",
    "kinetics/chute", "kinetics/encased_chain_drive_from_zinc", "kinetics/filter",
    "kinetics/attribute_filter", "kinetics/package_filter",
    "kinetics/fluid_pipe", "kinetics/fluid_pipe_vertical", "kinetics/large_cogwheel_from_little",
    "kinetics/mechanical_arm", "kinetics/mechanical_bearing", "kinetics/mechanical_crafter",
    "kinetics/mechanical_pump", "kinetics/smart_chute", "kinetics/smart_fluid_pipe",
    "kinetics/speedometer_from_conversion", "kinetics/spout",
    *(f"kinetics/{seat}{suffix}" for seat in SEATS for suffix in ("", "_from_other_seat")),
    "logistics/andesite_tunnel", "logistics/brass_funnel", "logistics/content_observer",
    "logistics/stockpile_switch",
    "materials/andesite_alloy_block", "materials/andesite_alloy_from_block",
    "materials/andesite_alloy_from_zinc", "materials/brass_block_from_compacting", "materials/zinc_ingot_from_compacting",
    "materials/brass_nugget_from_decompacting", "materials/brass_ingot_from_compacting",
    "materials/zinc_nugget_from_decompacting",
    "materials/zinc_block_from_compacting", "materials/zinc_ingot_from_decompacting",
    "materials/raw_zinc", "materials/raw_zinc_block", "appliances/chain_from_zinc", "appliances/clipboard", "appliances/tree_fertilizer",
    "schematics/schematicannon", "schematics/schematic_table", "schematics/empty_schematic", "schematics/schematic_and_quill",
    "materials/andesite_alloy", "materials/transmitter", "materials/sand_paper", "materials/red_sand_paper",
    "materials/rose_quartz_tiles_from_conversion", "materials/small_rose_quartz_tiles_from_conversion",
    "materials/rose_quartz", "materials/electron_tube", "logistics/brass_tunnel", "logistics/redstone_contact", "logistics/redstone_link", "logistics/display_link", "logistics/andesite_funnel",
    "materials/cardboard_block", "materials/cardboard_from_block", "materials/bound_cardboard_block",
    *(f"appliances/{name}" for name in CARDBOARD_ARMOR), "appliances/cardboard_sword",
    *(f"logistics/{name}" for name in BRASS_DIODES),
    "logistics/packager", "logistics/packager_from_conversion", "logistics/repackager_from_conversion", "logistics/stock_link", "logistics/stock_link_clear", "logistics/factory_gauge", "logistics/factory_gauge_clear", "logistics/redstone_requester", "logistics/redstone_requester_clear", "logistics/stock_ticker", "logistics/stock_ticker_clear", "logistics/powered_latch", "logistics/powered_toggle_latch", "logistics/desk_bell", "curiosities/peculiar_bell", "curiosities/minecart_coupling", "kinetics/sticker", "kinetics/crafter_slot_cover", "kinetics/rose_quartz_lamp", "kinetics/analog_lever", "kinetics/mechanical_saw", "kinetics/mechanical_drill", "kinetics/goggles", "kinetics/wrench", "kinetics/linear_chassis",
    "kinetics/linear_chassis_from_conversion", "kinetics/secondary_linear_chassis_from_conversion", "kinetics/radial_chassis",
    *(f"kinetics/{name}" for name in SLIDING_DOORS),
    *(f"kinetics/{name}_from_other_valve_handle" for name in DYED_VALVE_HANDLES),
    "kinetics/copper_valve_handle_from_others",
    *(f"kinetics/{name}" for name in (
        "shaft", "cogwheel", "large_cogwheel", "wooden_bracket", "metal_bracket", "gearbox", "vertical_gearbox",
        "gearbox_from_conversion", "vertical_gearbox_from_conversion", "minecart_from_contraption_cart", "furnace_minecart_from_contraption_cart", "clutch", "millstone",
        "windmill_bearing", "clockwork_bearing", "cuckoo_clock", "mysterious_cuckoo_clock", "white_sail", "white_sail_from_conversion", "sail_frame_from_conversion",
        "mechanical_roller", "mechanical_piston", "sticky_mechanical_piston", "piston_extension_pole", "mechanical_plough",
        "portable_storage_interface", "portable_fluid_interface",
        "depot", "water_wheel", "large_water_wheel", "speedometer", "stressometer_from_conversion",
        "mechanical_press", "belt_connector", "encased_fan", "propeller", "brass_hand", "deployer", "flywheel", "item_drain",
        "basin", "mechanical_mixer", "cart_assembler", "controller_rail", "mechanical_harvester", "contraption_controls", "elevator_pulley", "whisk", "empty_blaze_burner", "weighted_ejector", "gearshift", "encased_chain_drive", "adjustable_chain_gearshift", "rotation_speed_controller", "hand_crank", "fluid_valve", "copper_valve_handle", "hose_pulley", "rope_pulley", "sequenced_gearshift", "track_station", "track_signal", "track_observer", "track_observer_from_other_plates", "schedule", "controls", "super_glue", "gantry_shaft", "gantry_carriage", "metal_girder", "display_board", "nixie_tube",
    )),
)


def crafting_ingredient(ingredient):
    if isinstance(ingredient, list):
        return [crafting_ingredient(option) for option in ingredient]
    if "item" in ingredient:
        return ingredient["item"]
    if "tag" in ingredient:
        return "#" + ingredient["tag"]
    return ingredient


def copy_crafting(generated, content):
    for name in CRAFTING:
        path = Path(f"data/create/recipe/crafting/{name}.json")
        if not (generated / path).is_file():
            path = Path(f"data/create/recipe/{name}.json")
        recipe = json.loads((generated / path).read_text(encoding="utf-8"))
        if recipe["type"] == "minecraft:smithing_transform":
            for slot in ("template", "base", "addition"):
                recipe[slot] = crafting_ingredient(recipe[slot])
        elif "key" in recipe:
            recipe["key"] = {key: crafting_ingredient(value) for key, value in recipe["key"].items()}
        else:
            recipe["ingredients"] = [crafting_ingredient(value) for value in recipe["ingredients"]]
        write_json(content / path, recipe)


def copy_zinc_data(generated, content):
    for kind in ("smelting", "blasting"):
        for name in ORE_COOKING:
            path = Path(f"data/create/recipe/{kind}/{name}.json")
            recipe = json.loads((generated / path).read_bytes())
            recipe["ingredient"] = crafting_ingredient(recipe["ingredient"])
            if kind == "blasting":
                # Horizon applies the blast furnace's 2x speed to declared cook times.
                recipe["cookingtime"] *= 2
            write_json(content / path, recipe)
    for kind, names in (
        ("block", ("ores/zinc", "storage_blocks/raw_zinc", "storage_blocks/zinc")),
        ("item", ("ores/zinc", "storage_blocks/raw_zinc", "storage_blocks/zinc", "raw_materials/zinc")),
    ):
        for name in names:
            path = Path(f"data/c/tags/{kind}/{name}.json")
            write_json(content / path, json.loads((generated / path).read_bytes()))


def upgrade_loot_condition(condition):
    condition["type"] = condition.pop("condition")
    if "term" in condition:
        upgrade_loot_condition(condition["term"])
    for child in condition.get("terms", ()):
        upgrade_loot_condition(child)
    return condition


def upgrade_block_loot(entry):
    if "conditions" in entry:
        conditions = [upgrade_loot_condition(condition) for condition in entry.pop("conditions")]
        if len(conditions) == 1:
            entry["condition"] = conditions[0]
        elif conditions:
            entry["condition"] = conditions
    if "functions" in entry:
        modifiers = entry.pop("functions")
        for modifier in modifiers:
            modifier["type"] = modifier.pop("function")
        entry["modifier"] = modifiers
    for key in ("pools", "entries", "children", "modifier"):
        for child in entry.get(key, ()):
            upgrade_block_loot(child)


def build_pack(source, content, archive, *, worldgen=True):
    resources = source / "src/main/resources"
    generated = source / "src/generated/resources"
    copytree(ROOT / "content", content)
    menu = content / MOTOR_MENU
    if not menu.is_file():
        raise RuntimeError(f"required Creative Motor menu is missing: {menu}")
    menu_hash = hashlib.sha256(menu.read_bytes()).hexdigest()
    print(f"Creative Motor menu staged: {MOTOR_MENU} sha256={menu_hash}")
    copy_zinc_data(generated, content)
    packages_tag = Path("data/create/tags/item/packages.json")
    (content / packages_tag).parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / packages_tag, content / packages_tag)
    for name in PACKAGES:
        write_json(content / f"data/create/horizon/item/{name}.json", {
            "template": "minecraft:flint", "max_stack_size": 1,
        })
    if worldgen:
        prepare_worldgen(generated, content, write_json)
    blocks = content / "data/create/horizon/block"
    seat = json.loads((blocks / "white_seat.json").read_bytes())
    seat["properties"].update({
        "hardness": 2.0, "explosion_resistance": 2.0, "sounds": "minecraft:stripped_spruce_wood",
        "fall_distance_reduction": 0.5, "legacy_bounce_restitution": 0.66,
    })
    for color, map_color in SEAT_COLORS.items():
        write_json(blocks / f"{color}_seat.json", {
            **seat, "properties": {**seat["properties"], "map_color": map_color},
        })
    encased_cog = json.loads((blocks / "brass_encased_cogwheel.json").read_bytes())
    for name in ENCASED_COGWHEELS[1:]:
        write_json(blocks / f"{name}.json", encased_cog)
    sail = json.loads((blocks / "white_sail.json").read_bytes())
    for name, color in DYED_SAILS.items():
        write_json(blocks / f"{name}.json", {
            **sail, "item": False, "properties": {**sail["properties"], "map_color": color},
        })
    copper = json.loads((blocks / "copper_valve_handle.json").read_bytes())
    for name, color in zip(DYED_VALVE_HANDLES, (8, *range(15, 30)), strict=True):
        write_json(blocks / f"{name}.json", {
            **copper, "properties": {**copper["properties"], "map_color": color},
        })
    tube = json.loads((blocks / "nixie_tube.json").read_bytes())
    for name in DYED_NIXIES:
        color = SEAT_COLORS[name.removesuffix("_nixie_tube")]
        write_json(blocks / f"{name}.json", {
            **tube, "item": False, "properties": {**tube["properties"], "map_color": color},
        })
    north_south = [[.125, 0, 0, .875, .875, 1]]
    east_west = [[0, 0, .125, 1, .875, .875]]
    postbox_shapes = {"property": "facing", "values": {
        "north": north_south, "south": north_south, "east": east_west, "west": east_west,
    }}
    for color, map_color in SEAT_COLORS.items():
        write_json(blocks / f"{color}_postbox.json", {
            "template": "minecraft:oak_planks", "item": True,
            "properties": {
                "occludes": False, "map_color": map_color, "waterloggable": True,
                "hardness": 2.0, "explosion_resistance": 2.0,
                "sounds": "minecraft:stripped_spruce_wood",
            },
            "state_properties": {
                "facing": {"type": "enum", "values": ["north", "south", "east", "west"]},
                "open": {"type": "boolean"}, "waterlogged": {"type": "boolean"},
            },
            "default_state": {"facing": "north", "open": "false", "waterlogged": "false"},
            "shapes": postbox_shapes, "collision_shapes": postbox_shapes,
        })
    postboxes = content / "data/create/tags/item/postboxes.json"
    postboxes.parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / "data/create/tags/item/postboxes.json", postboxes)
    postbox_blocks = content / "data/create/tags/block/postboxes.json"
    postbox_blocks.parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / "data/create/tags/block/postboxes.json", postbox_blocks)
    copy_assets(resources, generated, content)
    copytree(resources / "assets/create/ponder", content / "assets/create/ponder", dirs_exist_ok=True)
    texture_path = Path("assets/create/textures")
    for source in (generated, resources):
        if (source / texture_path).is_dir():
            copytree(source / texture_path, content / texture_path, dirs_exist_ok=True)
    for layer, index in (("humanoid", 1), ("humanoid_leggings", 2)):
        source_texture = resources / f"assets/create/textures/models/armor/cardboard_layer_{index}.png"
        texture = content / f"assets/create/textures/entity/equipment/{layer}/cardboard.png"
        texture.parent.mkdir(parents=True, exist_ok=True)
        copy2(source_texture, texture)
    checker = resources / "assets/create/textures/special/highlighted_checkerboard.png"
    copy2(checker, content / "assets/create/textures/gui/chassis_preview.png")
    diving_texture = content / "assets/create/textures/entity/equipment/humanoid/copper_diving.png"
    diving_texture.parent.mkdir(parents=True, exist_ok=True)
    copy2(resources / "assets/create/textures/models/armor/copper_diving_layer_1.png", diving_texture)
    saw_recipes = Path("data/create/recipe/cutting")
    (content / saw_recipes).mkdir(parents=True, exist_ok=True)
    for recipe in (generated / saw_recipes).glob("*.json"):
        copy2(recipe, content / saw_recipes / recipe.name)
    runtime_processing = json.loads((ROOT / "fixtures/runtime-processing-java.json").read_bytes())
    for name, recipe in runtime_processing.items():
        write_json(content / f"data/create/recipe/{name}.json", recipe)
    for texture in ("saw_reversed", "experience_block"):
        animation = Path(f"assets/create/textures/block/{texture}.png.mcmeta")
        copy2(resources / animation, content / animation)
    sliding_doors(content)

    for part, sprite in (("rope", "belt"), ("rope_half", "belt"), ("rope_coil", "coil")):
        model = content / f"assets/create/models/block/elevator_pulley/{part}.json"
        data = json.loads(model.read_text(encoding="utf-8"))
        data["textures"]["1"] += "_scroll"
        write_json(model.with_stem(f"{part}_scroll"), data)
        texture = Path(f"assets/create/textures/block/elevator_pulley_{sprite}_scroll.png")
        copy2(resources / texture, content / texture)
    for sprite in ("schedule_2", "assemble", "schedule", "widgets", "player_inventory", "advancements", "filters", "filters_2", "frogport_and_mailbox", "requester", "stock_keeper"):
        relative = Path(f"assets/create/textures/gui/{sprite}.png")
        (content / relative).parent.mkdir(parents=True, exist_ok=True)
        copy2(resources / relative, content / relative)
    for sprite in (f"{fluid}_{variant}" for fluid in ("potion", "honey", "chocolate", "milk", "tea")
                   for variant in ("still", "flow")):
        for extension in (".png", ".png.mcmeta"):
            relative = Path(f"assets/create/textures/fluid/{sprite}{extension}")
            original = resources / relative
            if original.is_file():
                target = content / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(original, target)

    assets = content / "assets/create"
    model_dir = assets / "models/block"
    for fluid, texture in (("water", "minecraft:block/water"),
                           ("lava", "minecraft:block/lava"),
                           *((fluid, f"create:fluid/{fluid}")
                             for fluid in ("potion", "honey", "chocolate", "milk", "tea"))):
        for variant in ("still", "flow"):
            write_json(model_dir / f"spout/{fluid}_{variant}.json", {
                "textures": {"liquid": f"{texture}_{variant}"},
                "elements": [{
                    "from": [0, 0, 0], "to": [16, 16, 16],
                    "faces": {
                        face: {"texture": "#liquid", "tintindex": 0}
                        for face in ("up", "down", "north", "south", "west", "east")
                    },
                }],
            })
    woods = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak",
             "crimson", "warped", "mangrove", "bamboo", "cherry", "pale_oak")
    for path in ("water_wheel/wheel", "large_water_wheel/block",
                 "large_water_wheel/block_extension"):
        model = json.loads((model_dir / (path + ".json")).read_text(encoding="utf-8"))
        for wood in woods:
            material = ("stem" if wood in ("crimson", "warped") else
                        "block" if wood == "bamboo" else "log")
            log = f"{wood}_{material}"
            model["textures"] = {
                "planks": f"minecraft:block/{wood}_planks",
                "log": f"minecraft:block/{log}",
                "log_top": f"minecraft:block/{log}_top",
            }
            write_json(model_dir / f"{path}_{wood}.json", model)
    # The item mesh contains the original drum, frame, and housing.
    roller = "mechanical_roller"
    model = json.loads((model_dir / f"{roller}/item.json").read_text(encoding="utf-8"))
    model.pop("display", None)
    write_json(model_dir / f"{roller}/world.json", model)
    path = assets / f"blockstates/{roller}.json"
    blockstate = json.loads(path.read_text(encoding="utf-8"))
    for variant in blockstate["variants"].values():
        variant["model"] = f"create:block/{roller}/world"
        variant["y"] = (variant.get("y", 0) + 180) % 360
    write_json(path, blockstate)

    # The inventory models include Create's original retracted render parts.
    for block in ("portable_storage_interface", "portable_fluid_interface"):
        path = assets / f"blockstates/{block}.json"
        blockstate = json.loads(path.read_text(encoding="utf-8"))
        blockstate["variants"] = {
            f"{facing},extended={str(extended).lower()}":
                (variant if extended else {**variant, "model": f"create:block/{block}/item"})
            for facing, variant in blockstate["variants"].items()
            for extended in (False, True)
        }
        write_json(path, blockstate)

    # The original world model is drawn by the block entity renderer.
    for block in ("large_water_wheel", "shaft", "cogwheel", "large_cogwheel", "crushing_wheel", "copper_valve_handle", "hand_crank", *DYED_VALVE_HANDLES):
        write_json(assets / f"blockstates/{block}.json", {
            "variants": {"": {"model": "minecraft:block/air"}},
        })

    write_json(assets / "blockstates/blaze_burner.json", {
        "variants": {
            f"blaze={heat}": {"model": f"create:block/blaze_burner/{model}"}
            for heat, model in (
                ("none", "block"), ("smouldering", "block_with_blaze"),
                ("fading", "block_with_fire"), ("kindled", "block_with_fire"),
                ("seething", "block_with_soul_fire"),
            )
        },
    })

    belt_parts = []
    for facing, yaw in (("south", 0), ("west", 90), ("north", 180), ("east", 270)):
        for part in ("start", "middle", "pulley", "end"):
            mesh = "middle" if part == "pulley" else part
            for suffix in ("", "_bottom"):
                belt_parts.append({
                    "when": {"facing": facing, "part": part, "slope": "horizontal"},
                    "apply": {"model": f"create:block/belt/{mesh}{suffix}", "y": yaw},
                })
            for slope, angle in (("upward", (yaw + 180) % 360), ("downward", yaw)):
                diagonal = {"start": "end", "end": "start"}.get(mesh, mesh) if slope == "downward" else mesh
                belt_parts.append({
                    "when": {"facing": facing, "part": part, "slope": slope},
                    "apply": {"model": f"create:block/belt/diagonal_{diagonal}", "y": angle},
                })
    write_json(assets / "blockstates/belt.json", {"multipart": belt_parts})

    sound_path = "assets/create/sounds.json"
    copy2(generated / sound_path, content / sound_path)
    languages = {
        path.name: path
        for source in (generated, resources)
        for path in (source / "assets/create/lang").glob("*.json")
    }
    for name, source in languages.items():
        translations = json.loads(source.read_text(encoding="utf-8"))
        labels = dict(translations)
        for items, source_key in (
            (CARDBOARD_PACKAGES, "item.create.package"),
            (RARE_PACKAGES, "item.create.rare_package"),
            (CART_CONTRAPTION_ITEMS, "item.create.minecart_contraption"),
            (("clipboard",), "block.create.clipboard"),
            (("factory_gauge",), "block.create.factory_gauge"),
        ):
            if source_key in translations:
                for item in items:
                    labels.setdefault(f"item.create.{item}", translations[source_key])
        write_json(content / "assets/create/lang" / name, labels)
    for name in ITEMS:
        model = {"type": "minecraft:model", "model": f"create:item/{name}"}
        if name == "clipboard":
            empty, written, editing = ({"type": "minecraft:model", "model": f"create:item/clipboard_{mode}"}
                                       for mode in range(3))
            model = {
                "type": "minecraft:condition", "property": "create:clipboard_editing",
                "on_true": editing,
                "on_false": {
                    "type": "minecraft:condition", "property": "create:clipboard_written",
                    "on_true": written, "on_false": empty,
                },
            }
        if name == "goggles":
            model = {
                "type": "minecraft:select",
                "property": "minecraft:display_context",
                "cases": [{"when": "head", "model": {"type": "minecraft:model", "model": "create:block/goggles"}}],
                "fallback": model,
            }
        if name == "cardboard_sword":
            model = {
                "type": "minecraft:select",
                "property": "minecraft:display_context",
                "cases": [{"when": "gui", "model": model}],
                "fallback": {"type": "minecraft:model", "model": "create:item/cardboard_sword/item_in_hand"},
            }
        if name == "handheld_worldshaper":
            model = {
                "type": "minecraft:composite",
                "models": [model, *({"type": "minecraft:model", "model": f"create:item/handheld_worldshaper/{part}"}
                                    for part in ("core", "core_glow", "accelerator"))],
            }
        if name == "wrench":
            model = {
                "type": "minecraft:composite",
                "models": [model, {"type": "minecraft:model", "model": "create:item/wrench/gear"}],
            }
        write_json(content / f"assets/create/items/{name}.json", {"model": model})

    block_loot = [Path(f"loot_table/blocks/{name}.json") for name in BLOCKS if name not in ("crushing_wheel_controller", "honey", "chocolate")]
    milling = sorted((generated / "data/create/recipe/milling").glob("*.json"))
    milling_recipes = [Path("recipe/milling") / recipe.name for recipe in milling]
    applications = [
        Path("recipe/item_application") / recipe.name
        for recipe in sorted((generated / "data/create/recipe/item_application").glob("*.json"))
    ]
    deploying = [
        Path("recipe/deploying") / recipe.name
        for recipe in sorted((generated / "data/create/recipe/deploying").glob("*.json"))
    ]
    pressing = [Path(f"recipe/pressing/{material}.json")
                for material in ("iron_ingot", "copper_ingot", "gold_ingot", "brass_ingot", "sugar_cane", "cardboard", "path", "path_from_grass")]
    processing_recipes = []
    for kind in ("splashing", "haunting", "crushing", "compacting"):
        for file in sorted((generated / f"data/create/recipe/{kind}").glob("*.json")):
            recipe = json.loads(file.read_text(encoding="utf-8"))
            if all(result["id"] in {f"create:{name}" for name in ITEMS} or
                   result["id"].startswith("minecraft:") for result in recipe["results"]):
                processing_recipes.append(Path(f"recipe/{kind}") / file.name)
    copycat_recipes = tuple(Path(f"recipe/copycat_{kind}_from_ingots_zinc_stonecutting.json")
                             for kind in ("panel", "step"))
    cooking_recipes = tuple(Path(f"recipe/{name}.json") for name in ("smelting/bread", "smoking/bread", "campfire_cooking/bread", "smelting/scoria"))
    for path in (*block_loot, *milling_recipes, *applications, *deploying, *pressing, *processing_recipes,
                 *copycat_recipes, *cooking_recipes,
                 Path("recipe/crafting/curiosities/item_copying.json"),
                 Path("tags/item/pulpifiable.json"), Path("tags/item/chain_rideable.json"),
                 Path("tags/block/fan_transparent.json"),
                 Path("tags/block/brittle.json"), Path("tags/block/movable_empty_collider.json"), Path("tags/block/corals.json"),
                 Path("tags/block/copycat_allow.json"),
                 Path("tags/block/copycat_deny.json"),
                 *(Path(f"recipe/mixing/{name}.json")
                   for name in ("brass_ingot", "honey", "chocolate", "chocolate_melting", "cardboard_pulp",
                                "andesite_alloy", "andesite_alloy_from_zinc", "dough_by_mixing", "mud_by_mixing", "tea", "lava_from_cobble")),
                 Path("recipe/mechanical_crafting/crushing_wheel.json"), Path("recipe/mechanical_crafting/extendo_grip.json"), Path("recipe/mechanical_crafting/potato_cannon.json"), Path("recipe/mechanical_crafting/wand_of_symmetry.json"), Path("recipe/sequenced_assembly/track.json"), Path("recipe/sequenced_assembly/precision_mechanism.json"), Path("recipe/sequenced_assembly/sturdy_sheet.json"),
                 Path("tags/item/sleepers.json"), Path("tags/item/valve_handles.json"),
                 Path("tags/block/wrench_pickup.json"),
                 Path("enchantment/capacity.json"),
                 Path("tags/block/windmill_sails.json"),
                 Path("recipe/sandpaper_polishing/rose_quartz.json"),
                 Path("recipe/emptying/honey_bottle.json"), Path("recipe/emptying/builders_tea.json"),
                 *(Path(f"advancement/{name}.json") for name in ADVANCEMENTS),
                 *(Path(f"recipe/filling/{name}.json") for name in ("redstone", "gunpowder", "glowstone", "grass_block", "blaze_cake", "sweet_roll", "chocolate_glazed_berries", "honeyed_apple", "builders_tea", "honey_bottle"))):
        relative = Path("data/create") / path
        (content / relative).parent.mkdir(parents=True, exist_ok=True)
        if path.parent == Path("loot_table/blocks") and path.stem in (*ZINC_BLOCKS, *ALL_PALETTE_BLOCKS, *COPPER_ROOFS, *METAL_SCAFFOLDING, *METAL_DECORATIONS, *BRASS_DIODES, *DYED_NIXIES, *METAL_BLOCKS, *ROSE_QUARTZ_PALETTE, "chain_conveyor", "package_frogport", "lectern_controller", "cuckoo_clock", "mysterious_cuckoo_clock", "nixie_tube", "cardboard_block", "bound_cardboard_block", "factory_gauge", "rose_quartz_lamp", "powered_latch", "powered_toggle_latch", "desk_bell", "placard", "clutch", "gearshift", "turntable", "nozzle", "train_trapdoor", "framed_glass_trapdoor", "experience_block", "item_hatch", "copper_backtank", "netherite_backtank", "encased_fluid_pipe", "fluid_pipe", "glass_fluid_pipe", "smart_fluid_pipe", "track", "railway_casing", "andesite_casing", "brass_casing", "copper_casing", *SEATS, *POSTBOXES):
            table = json.loads((generated / relative).read_bytes())
            upgrade_block_loot(table)
            write_json(content / relative, table)
            continue
        if path.parent == Path("loot_table/blocks") and path.stem in (
            "metal_girder", "metal_girder_encased_shaft", "copycat_panel", "copycat_step", "copycat_base",
            "gearbox", "elevator_contact", "hand_crank", "creative_motor",
            "copper_valve_handle", *DYED_VALVE_HANDLES,
            "cart_assembler", "controller_rail", "content_observer", "stockpile_switch",
        ):
            table = json.loads((generated / relative).read_bytes())
            for pool in table["pools"]:
                for condition in pool["conditions"]:
                    condition["type"] = condition.pop("condition")
            if path.stem == "gearbox":
                axis_condition = {"type": "minecraft:block_state_property", "block": "create:gearbox"}
                for pool in table["pools"]:
                    pool["conditions"].append(axis_condition | {"properties": {"axis": "y"}})
                for axis in ("x", "z"):
                    table["pools"].append({
                        "rolls": 1,
                        "conditions": [axis_condition | {"properties": {"axis": axis}}],
                        "entries": [{"type": "minecraft:item", "name": "create:vertical_gearbox"}],
                    })
            if path.stem == "cart_assembler":
                # Java adds the stored vanilla rail's own drop when the assembler breaks.
                for rail_type, item in (
                    ("regular", "minecraft:rail"),
                    ("powered_rail", "minecraft:powered_rail"),
                    ("detector_rail", "minecraft:detector_rail"),
                    ("activator_rail", "minecraft:activator_rail"),
                    ("controller_rail", "create:controller_rail"),
                ):
                    table["pools"].append({
                        "rolls": 1,
                        "conditions": [
                            {"type": "minecraft:survives_explosion"},
                            {
                                "type": "minecraft:block_state_property",
                                "block": "create:cart_assembler",
                                "properties": {"rail_type": rail_type},
                            },
                        ],
                        "entries": [{"type": "minecraft:item", "name": item}],
                    })
            write_json(content / relative, table)
        elif path in (Path("recipe/filling/sweet_roll.json"), Path("recipe/filling/honeyed_apple.json"),
                      Path("recipe/filling/honey_bottle.json")):
            recipe = json.loads((generated / relative).read_bytes())
            fluid = recipe["ingredients"][1]
            # The runtime represents these Java fluid tags by their supported source fluids.
            fluid["fluid"] = {"c:milk": "minecraft:milk", "c:honey": "create:honey"}[fluid.pop("tag")]
            fluid["type"] = "neoforge:single"
            write_json(content / relative, recipe)
        elif path == Path("recipe/pressing/path.json"):
            recipe = json.loads((generated / relative).read_bytes())
            recipe["ingredients"][0] = [crafting_ingredient(item) for item in recipe["ingredients"][0]]
            write_json(content / relative, recipe)
        elif path in (*copycat_recipes, *cooking_recipes):
            recipe = json.loads((generated / relative).read_bytes())
            recipe["ingredient"] = crafting_ingredient(recipe["ingredient"])
            if path == Path("recipe/smoking/bread.json"):
                # 26.3 applies the fast-fuel multiplier to the declared base time.
                recipe["cookingtime"] *= 2
            write_json(content / relative, recipe)
        else:
            copy2(generated / relative, content / relative)

    # Keep the pinned Java Mud recipe pointing at the original spelling of this tag.
    write_json(content / "data/minecraft/tags/block/convertable_to_mud.json", {
        "values": ["#minecraft:convertible_to_mud"],
    })
    write_json(content / "data/c/tags/item/feathers.json", {"values": ["minecraft:feather"]})
    write_json(content / "data/c/tags/item/eggs.json", {"values": ["minecraft:egg"]})
    write_json(content / "data/c/tags/item/barrels/wooden.json", {"values": ["minecraft:barrel"]})
    write_json(content / "data/c/tags/item/ingots/netherite.json", {"values": ["minecraft:netherite_ingot"]})
    for name in ("foods/dough", "storage_blocks/brass"):
        path = Path(f"data/c/tags/item/{name}.json")
        (content / path).parent.mkdir(parents=True, exist_ok=True)
        copy2(generated / path, content / path)
    write_json(content / "data/c/tags/item/storage_blocks.json", {
        "values": ["create:brass_block", "create:andesite_alloy_block", "create:experience_block"],
    })
    wrench_tag = Path("data/c/tags/item/tools/wrench.json")
    (content / wrench_tag).parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / wrench_tag, content / wrench_tag)
    wheat_flour = Path("data/c/tags/item/flours/wheat.json")
    (content / wheat_flour).parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / wheat_flour, content / wheat_flour)
    for kind in ("ingots", "nuggets"):
        zinc_tag = Path(f"data/c/tags/item/{kind}/zinc.json")
        (content / zinc_tag).parent.mkdir(parents=True, exist_ok=True)
        copy2(generated / zinc_tag, content / zinc_tag)
    for copper_tag in (
        Path("data/c/tags/item/nuggets/copper.json"),
        Path("data/minecraft/tags/item/piglin_loved.json"),
    ):
        (content / copper_tag).parent.mkdir(parents=True, exist_ok=True)
        copy2(generated / copper_tag, content / copper_tag)
    crushed = Path("data/create/tags/item/crushed_raw_materials.json")
    crushed_items = json.loads((generated / crushed).read_bytes())
    known = {f"create:{item}" for item in ITEMS}
    crushed_items["values"] = [item for item in crushed_items["values"] if item in known]
    write_json(content / crushed, crushed_items)
    brass_nuggets = Path("data/c/tags/item/nuggets/brass.json")
    copy2(generated / brass_nuggets, content / brass_nuggets)
    clear_glass = Path("data/c/tags/item/glass_blocks/colorless.json")
    (content / clear_glass).parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / clear_glass, content / clear_glass)
    copper_plate = Path("data/c/tags/item/plates/copper.json")
    copy2(generated / copper_plate, content / copper_plate)
    obsidian_dust = Path("data/c/tags/item/dusts/obsidian.json")
    (content / obsidian_dust).parent.mkdir(parents=True, exist_ok=True)
    copy2(generated / obsidian_dust, content / obsidian_dust)
    obsidian_plate = Path("data/c/tags/item/plates/obsidian.json")
    copy2(generated / obsidian_plate, content / obsidian_plate)
    gold_plate = Path("data/c/tags/item/plates/gold.json")
    copy2(generated / gold_plate, content / gold_plate)
    write_json(content / "data/c/tags/item/ingots/copper.json", {
        "values": ["minecraft:copper_ingot"],
    })
    write_json(content / "data/c/tags/item/netherracks.json", {
        "values": ["minecraft:netherrack"],
    })
    for name, item in (
        ("slimeballs", "minecraft:slime_ball"),
        ("gunpowders", "minecraft:gunpowder"),
        ("dusts/redstone", "minecraft:redstone"),
        ("nuggets/iron", "minecraft:iron_nugget"),
        ("plates/iron", "create:iron_sheet"),
    ):
        write_json(content / f"data/c/tags/item/{name}.json", {"values": [item]})
    for color in VALVE_DYES:
        write_json(content / f"data/c/tags/item/dyes/{color}.json", {"values": [f"minecraft:{color}_dye"]})
    copy_crafting(generated, content)
    bogey_display_blocks(content)
    carriage_port_display_blocks(content)
    prepare_palettes(generated, content, write_json, crafting_ingredient,
                     extra_tag_ids={f"create:{name}" for name in (*METAL_BLOCKS, *ROSE_QUARTZ_PALETTE, "rose_quartz_lamp", *SEATS, "nixie_tube", *DYED_NIXIES)})

    prepare_copper_roofs(generated, content, write_json, crafting_ingredient)
    palettes = content / "data/create/horizon/creative_tab/palettes.json"
    tab = json.loads(palettes.read_bytes())
    tab["items"].extend(f"create:{name}" for name in (*METAL_DECORATIONS, *METAL_BLOCKS, *ROSE_QUARTZ_PALETTE, "red_seat"))
    tab["items"].extend(f"create:{name}" for name in COPPER_ROOFS)
    write_json(palettes, tab)
    stonecutting = {block: METAL_INGREDIENTS[block.split("_", 1)[0]] for block in METAL_DECORATIONS}
    stonecutting.update(dict.fromkeys(IRON_DECORATIONS, "ingots_iron"))
    stonecutting.update(ROSE_QUARTZ_PALETTE)
    for block, ingredient in stonecutting.items():
        name = f"{block}_from_{ingredient}"
        path = Path(f"data/create/recipe/{name}_stonecutting.json")
        recipe = json.loads((generated / path).read_bytes())
        recipe["ingredient"] = crafting_ingredient(recipe["ingredient"])
        write_json(content / path, recipe)
    prepare_windows(generated, content, write_json, crafting_ingredient)
    for tag, vanilla in (("stones", "stone"), ("rods/wooden", "stick")):
        target = content / f"data/c/tags/item/{tag}.json"
        data = json.loads(target.read_bytes()) if target.is_file() else {"values": []}
        if f"minecraft:{vanilla}" not in data["values"]:
            data["values"].append(f"minecraft:{vanilla}")
        write_json(target, data)
    prepare_vertical_windows(resources, content)
    prepare_industrial_window(resources, content)
    prepare_framed_glass(resources, content)
    prepare_copper_casing(resources, content)
    prepare_weathered_window(resources, content)
    prepare_toolboxes(resources, generated, content, write_json, crafting_ingredient, upgrade_block_loot)
    prepare_table_cloths(generated, content, write_json, crafting_ingredient, upgrade_block_loot)
    complete_creative_tab(content)

    for name in FIXTURES:
        relative = Path(f"data/create/structure/gametest/{name}.nbt")
        fixture = ROOT / ".local/fixtures" / relative
        fixture.parent.mkdir(parents=True, exist_ok=True)
        copy2(resources / relative, fixture)
        print(fixture)
    for source in (resources, generated):
        for directory in ("models", "sounds"):
            for path in (source / "assets/create" / directory).rglob("*"):
                if not path.is_file():
                    continue
                target = content / path.relative_to(source)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    copy2(path, target)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        for path in sorted(content.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(content))
    with ZipFile(archive) as package:
        packed = package.read(str(MOTOR_MENU))
    if hashlib.sha256(packed).hexdigest() != menu_hash:
        raise RuntimeError(f"Creative Motor menu changed while packaging: {MOTOR_MENU}")
    print(f"Creative Motor menu packaged: {MOTOR_MENU} sha256={menu_hash}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("create_source", type=Path)
    parser.add_argument("--disable-worldgen", action="store_true",
                        help="omit Create ore generation while keeping materials and recipes")
    args = parser.parse_args()

    source = args.create_source.resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != CREATE_REVISION:
        parser.error(f"expected Create {CREATE_REVISION}, found {revision}")

    work = ROOT / ".local"
    work.mkdir(parents=True, exist_ok=True)
    output = work / "create.hmod"
    with TemporaryDirectory(prefix="create-content-", dir=work) as scratch:
        stage = Path(scratch)
        archive = stage / output.name
        build_pack(source, stage / "content", archive, worldgen=not args.disable_worldgen)
        archive.replace(output)
    print(output)


if __name__ == "__main__":
    main()

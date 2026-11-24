#!/usr/bin/env python3
"""Stage the processing migration probe from tracked production sources."""

import argparse
import json
import zipfile
from pathlib import Path
from shutil import copy2, copytree

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".local/sdk-check/processing-project"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/sdk-check/typed-millstone.hmod")
    args = parser.parse_args()
    output = args.output.resolve()
    pack = args.pack.resolve(strict=True)
    if output.exists():
        if output == DEFAULT_OUTPUT.resolve():
            raise SystemExit(f"Refusing to replace staged output: {output}")
        raise FileExistsError(f"Refusing to replace staged output: {output}")
    output.mkdir(parents=True)
    (output / "src").mkdir()

    source = ROOT / "migration/kinetic-probe"
    copy2(source / "Cargo.toml", output / "Cargo.toml")
    copy2(source / "horizon-mod.toml", output / "horizon-mod.toml")
    manifest = (output / "horizon-mod.toml").read_text()
    manifest = manifest.replace("create_kinetic_probe", "create_processing_probe")
    manifest = manifest.replace("Create Kinetic Probe", "Create Processing Probe")
    (output / "horizon-mod.toml").write_text(manifest)
    cargo = (output / "Cargo.toml").read_text()
    cargo = cargo.replace("mod-create_kinetic_probe", "mod-create_processing_probe")
    (output / "Cargo.toml").write_text(cargo)

    production = ROOT / "native"
    modules = {
        "kinetic_slice.rs": None,
        "kinetic_adapter.rs": ("super::create_kinetic_slice", "super::kinetic_slice"),
        "millstone_processing.rs": None,
        "millstone_adapter.rs": (
            "super::create_millstone_processing",
            "super::millstone_processing",
        ),
        "press_processing.rs": None,
        "press_adapter.rs": None,
        "crushing_adapter.rs": None,
        "basin_adapter.rs": None,
        "burner_adapter.rs": None,
        "motor_board.rs": None,
    }
    for name, rename in modules.items():
        target = output / "src" / name
        copy2(production / name, target)
        if rename:
            target.write_text(target.read_text().replace(*rename))

    (output / "src/lib.rs").write_text(
        "pub(crate) mod kinetic_adapter;\n"
        "pub(crate) mod kinetic_slice;\n"
        "pub(crate) mod millstone_adapter;\n"
        "pub(crate) mod millstone_processing;\n"
        "pub(crate) mod motor_board;\n"
        "pub(crate) mod press_processing;\n\n"
        "pub(crate) mod press_adapter;\n\n"
        "pub(crate) mod crushing_adapter;\n"
        "pub(crate) mod basin_adapter;\n"
        "pub(crate) mod burner_adapter;\n\n"
        "#[derive(Default)]\nstruct Mod;\n\n"
        "#[mod_api::horizon_mod]\n"
        "impl mod_api::Hooks for Mod {\n"
        "    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {\n"
        "        for kind in [\"create:milling\", \"create:pressing\", \"create:crushing\", \"create:mixing\", \"create:compacting\"] {\n"
        "            registrar.register_recipe_type(kind);\n"
        "            registrar.register_raw_recipe_serializer(kind, kind);\n"
        "        }\n"
        "        kinetic_adapter::register(registrar);\n"
        "        motor_board::register(registrar);\n"
        "        millstone_adapter::register(registrar);\n"
        "        press_adapter::register(registrar);\n"
        "        crushing_adapter::register(registrar);\n"
        "        basin_adapter::register(registrar);\n"
        "        burner_adapter::register(registrar);\n"
        "        if let Some(container) = millstone_adapter::container(\"create:millstone\") {\n"
        "            let block = registrar.block_key(\"create:millstone\");\n"
        "            registrar.block_container(&block, container);\n"
        "        }\n"
        "    }\n\n"
        "    fn scheduled_task(&self, host: &mut dyn mod_api::ServerHost, event: &mut mod_api::ScheduledTaskEvent<'_>) {\n"
        "        motor_board::scheduled_task(host, event);\n"
        "        press_adapter::scheduled_task(host, event);\n"
        "    }\n"
        "}\n"
    )

    source_content = ROOT / "content/data/create"
    destination_data = output / "data/create"
    block_names = (
        "creative_motor", "shaft", "cogwheel", "large_cogwheel", "millstone",
        "mechanical_bearing", "mechanical_press", "crushing_wheel",
        "crushing_wheel_controller", "basin", "mechanical_mixer",
        "blaze_burner", "lit_blaze_burner", "empty_blaze_burner",
    )
    blocks = destination_data / "horizon/block"
    blocks.mkdir(parents=True, exist_ok=True)
    for name in block_names:
        source_file = source_content / f"horizon/block/{name}.json"
        if not source_file.is_file():
            continue
        definition = json.loads(source_file.read_text())
        definition.get("properties", {}).pop("waterloggable", None)
        (blocks / source_file.name).write_text(json.dumps(definition, indent=2) + "\n")

    menu = source_content / "horizon/menu/creative_motor.json"
    if menu.is_file():
        destination = destination_data / "horizon/menu"
        destination.mkdir(parents=True, exist_ok=True)
        copy2(menu, destination / menu.name)
    flour = source_content / "horizon/item/wheat_flour.json"
    if flour.is_file():
        destination = destination_data / "horizon/item"
        destination.mkdir(parents=True, exist_ok=True)
        copy2(flour, destination / flour.name)

    processing_items = destination_data / "horizon/item"
    processing_items.mkdir(parents=True, exist_ok=True)
    for name in (
        "iron_sheet", "golden_sheet", "copper_sheet", "brass_sheet",
        "crushed_iron_ore", "crushed_gold_ore", "crushed_copper_ore",
        "crushed_zinc_ore", "crushed_brass", "blaze_cake",
    ):
        item = source_content / f"horizon/item/{name}.json"
        if item.is_file():
            copy2(item, processing_items / item.name)

    recipes = destination_data / "recipe"
    recipes.mkdir(parents=True, exist_ok=True)
    for name in ("milling", "pressing", "crushing", "mixing", "compacting"):
        source_dir = source_content / f"recipe/{name}"
        if source_dir.is_dir():
            copytree(source_dir, recipes / name)

    # The typed adapters read recipes through Host::recipes_of_type. Keep the
    # production family recipes in the staged native package as well as the
    # Create content pack used by the managed fixture.
    with zipfile.ZipFile(pack) as bundle:
        for family in ("pressing", "crushing", "mixing", "compacting"):
            prefix = f"data/create/recipe/{family}/"
            for path in bundle.namelist():
                if not path.startswith(prefix) or not path.endswith(".json"):
                    continue
                target = recipes / family / Path(path).name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(path))
                recipe = json.loads(target.read_text())
                for result in recipe.get("results", []):
                    item_id = result.get("id") if isinstance(result, dict) else None
                    if not item_id or not item_id.startswith("create:"):
                        continue
                    item_name = item_id.split(":", 1)[1]
                    item_file = processing_items / f"{item_name}.json"
                    bundled_item = f"data/create/horizon/item/{item_name}.json"
                    source_item = source_content / f"horizon/item/{item_name}.json"
                    if not item_file.exists() and bundled_item in bundle.namelist():
                        item_file.write_bytes(bundle.read(bundled_item))
                    elif not item_file.exists() and source_item.is_file():
                        copy2(source_item, item_file)
    print(f"Prepared processing probe from tracked sources at {output}")


if __name__ == "__main__":
    main()

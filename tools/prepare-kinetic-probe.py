#!/usr/bin/env python3
"""Stage the bounded kinetic probe from the production adapter sources."""

import argparse
import hashlib
import json
from pathlib import Path
from shutil import copy2, rmtree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "migration/kinetic-probe"
DEFAULT_OUTPUT = ROOT / ".local/sdk-check/project"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output.resolve()
    if output.exists():
        if output == DEFAULT_OUTPUT.resolve():
            rmtree(output)
        else:
            raise FileExistsError(f"Refusing to replace staged output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "src").mkdir(exist_ok=True)
    for name in ("Cargo.toml", "horizon-mod.toml"):
        copy2(SOURCE / name, output / name)
    copy2(SOURCE / "src/lib.rs", output / "src/lib.rs")
    for name in (
        "kinetic_adapter.rs",
        "kinetic_slice.rs",
        "millstone_processing.rs",
        "millstone_adapter.rs",
        "motor_board.rs",
    ):
        source = ROOT / "native" / name
        destination = output / "src" / name
        copy2(source, destination)
        if name == "millstone_adapter.rs":
            # The production mixin calls the generated module by its game.rs
            # name; this standalone crate owns the same logic as a Rust mod.
            destination.write_text(
                destination.read_text().replace(
                    "super::create_millstone_processing", "super::millstone_processing"
                )
            )
        if name == "kinetic_adapter.rs":
            # The production mixin names this sibling `create_kinetic_slice`;
            # the bounded standalone crate keeps the shorter module name.
            destination.write_text(
                destination.read_text().replace(
                    "super::create_kinetic_slice", "super::kinetic_slice"
                )
            )
    copy2(SOURCE / "src/moving_probe.rs", output / "src/moving_probe.rs")
    menu = output / "data/create/horizon/menu"
    menu.mkdir(parents=True, exist_ok=True)
    menu_source = ROOT / "content/data/create/horizon/menu/creative_motor.json"
    menu_target = menu / "creative_motor.json"
    copy2(menu_source, menu_target)
    if hashlib.sha256(menu_source.read_bytes()).digest() != hashlib.sha256(menu_target.read_bytes()).digest():
        raise RuntimeError("Creative Motor menu differs from the production resource")
    recipes = output / "data/create/recipe"
    recipes.mkdir(parents=True, exist_ok=True)
    production_recipe = ROOT / "content/data/create/recipe/milling/wheat.json"
    (recipes / "milling").mkdir(parents=True, exist_ok=True)
    copy2(production_recipe, recipes / "milling/wheat.json")
    items = output / "data/create/horizon/item"
    items.mkdir(parents=True, exist_ok=True)
    copy2(ROOT / "content/data/create/horizon/item/wheat_flour.json",
          items / "wheat_flour.json")
    blocks = output / "data/create/horizon/block"
    blocks.mkdir(parents=True, exist_ok=True)
    for name in (
        "creative_motor", "shaft", "cogwheel", "large_cogwheel",
        "millstone", "mechanical_bearing", "flywheel", "gearbox",
        "clutch", "gearshift",
    ):
        source = ROOT / f"content/data/create/horizon/block/{name}.json"
        definition = json.loads(source.read_text())
        # The pinned SDK rejects this BlockProperties field. The test package
        # is a compile/runtime adapter probe, not waterlogging-equivalent.
        definition.get("properties", {}).pop("waterloggable", None)
        (blocks / f"{name}.json").write_text(
            json.dumps(definition, indent=2) + "\n"
        )
    print(
        "Explicitly omitted unsupported BlockProperties.waterloggable in the "
        "probe; waterlogging behavior remains unverified."
    )
    print(f"Prepared kinetic probe from tracked native sources at {output}")


if __name__ == "__main__":
    main()

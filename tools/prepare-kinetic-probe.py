#!/usr/bin/env python3
"""Stage the bounded kinetic probe from the production adapter sources."""

import json
from pathlib import Path
from shutil import copy2, rmtree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "migration/kinetic-probe"
OUTPUT = ROOT / ".local/sdk-check/project"


def main():
    if OUTPUT.exists():
        rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "src").mkdir(exist_ok=True)
    for name in ("Cargo.toml", "horizon-mod.toml"):
        copy2(SOURCE / name, OUTPUT / name)
    copy2(SOURCE / "src/lib.rs", OUTPUT / "src/lib.rs")
    for name in (
        "kinetic_adapter.rs",
        "kinetic_slice.rs",
        "millstone_processing.rs",
        "millstone_adapter.rs",
        "motor_board.rs",
    ):
        source = ROOT / "native" / name
        destination = OUTPUT / "src" / name
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
    copy2(SOURCE / "src/moving_probe.rs", OUTPUT / "src/moving_probe.rs")
    menu = OUTPUT / "data/create/horizon/menu"
    menu.mkdir(parents=True, exist_ok=True)
    copy2(ROOT / "content/data/create/horizon/menu/creative_motor.json",
          menu / "creative_motor.json")
    recipes = OUTPUT / "data/create/recipe"
    recipes.mkdir(parents=True, exist_ok=True)
    copy2(SOURCE / "data/create/recipe/migration_probe_wheat_to_bread.json",
          recipes / "migration_probe_wheat_to_bread.json")
    blocks = OUTPUT / "data/create/horizon/block"
    blocks.mkdir(parents=True, exist_ok=True)
    for name in (
        "creative_motor", "shaft", "cogwheel", "large_cogwheel",
        "millstone", "mechanical_bearing",
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
    print(f"Prepared kinetic probe from tracked native sources at {OUTPUT}")


if __name__ == "__main__":
    main()

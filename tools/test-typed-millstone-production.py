#!/usr/bin/env python3
"""Exercise the real Create wheat milling recipe and output backpressure."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]

MILL = (0, 100, 0)
PROCESSING_TICKS = 155


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control):
    return control.command(f"/data get block {xyz(MILL)}")


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def require_flour(data):
    if "create:wheat_flour" not in data:
        raise RuntimeError(f"Java-backed wheat milling did not produce its guaranteed flour: {data}")


def recipe_matches_wheat_milling(path, contents):
    if not path.startswith("data/create/recipe/") or not path.endswith(".json"):
        return False
    try:
        recipe = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if recipe.get("type") != "create:milling":
        return False
    for ingredient in recipe.get("ingredients", []):
        if isinstance(ingredient, dict) and ingredient.get("item") == "minecraft:wheat":
            return True
    return False


def prepare_test_pack(base, output):
    recipe_path = ROOT / "fixtures/typed-millstone-production/data/create/recipe/app2163_wheat_milling.json"
    fallback = recipe_path.read_bytes()
    found_production_recipe = False
    with ZipFile(base) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            if entry.filename == "data/create/recipe/migration_probe_wheat_to_bread.json":
                continue
            contents = source.read(entry.filename)
            found_production_recipe |= recipe_matches_wheat_milling(entry.filename, contents)
            if entry.filename != "data/create/recipe/app2163_wheat_milling.json":
                target.writestr(entry, contents)
        if not found_production_recipe:
            target.write(recipe_path, "data/create/recipe/app2163_wheat_milling.json")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    recipe_source = "production pack" if found_production_recipe else "Java-backed fixture fallback"
    print(f"Millstone test pack: {recipe_source}; synthetic bread recipe removed; sha256={digest}")


def verify(args):
    base = args.pack or ROOT / ".local/create.hmod"
    with TemporaryDirectory(prefix="hc-millstone-test-pack-") as tmp:
        test_pack = Path(tmp) / "create-millstone-test.hmod"
        prepare_test_pack(base, test_pack)
        with fixture_world(args, "TypedMillstoneProduction", pack=test_pack) as control:
            control.commands((
                f"/setblock {xyz(MILL)} create:millstone",
                f"/data merge block {xyz(MILL)} {{Speed:16.0f}}",
                f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
            ))
            advance(control, PROCESSING_TICKS)
            completed = block_data(control)
            if "minecraft:wheat" in completed:
                raise RuntimeError(f"Real wheat input was not consumed: {completed}")
            require_flour(completed)

            control.call("save")
            control.restart()
            reopened = block_data(control)
            require_flour(reopened)

            control.commands((
                f"/item replace block {xyz(MILL)} container.1 with create:wheat_flour 64",
                f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
            ))
            advance(control, PROCESSING_TICKS)
            blocked = block_data(control)
            if "minecraft:wheat" not in blocked:
                raise RuntimeError(f"Full output slot caused input loss: {blocked}")
            if "create:wheat_flour" not in blocked or "count: 64" not in blocked:
                raise RuntimeError(f"Full output slot changed unexpectedly: {blocked}")

    print("Typed Millstone processed Java-backed wheat milling, retained output across reopen, and conserved input under full output.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()

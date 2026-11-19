#!/usr/bin/env python3
"""Compare the pinned Java runtime inventory and resources with a Horizon pack."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from zipfile import ZipFile

from fixture_world import fixture_world
from prepare import CREATE_REVISION, ROOT

REGISTRY_LINE = re.compile(r"^CREATE_REGISTRY ([a-z_]+) (create:[a-z0-9_./-]+)$", re.M)
# These Horizon declarations use the registry ID as their relative filename.
PACK_PREFIX = {
    "block": "data/create/horizon/block/",
    "item": "data/create/horizon/item/",
    "menu": "data/create/horizon/menu/",
    "recipe": "data/create/recipe/",
}
PROBES = {
    "block": ("/execute if block ~ ~ ~ {}", ("Test passed", "Test failed"), "<--[HERE]"),
    "item": ("/clear @s {} 0", ("No items were found", "Found "), "<--[HERE]"),
    "recipe": ("/recipe give @s {}", ("Unlocked ", "No new recipes were learned"), "Unknown recipe:"),
}


def java_registry(log):
    text = log.read_text(encoding="utf-8")
    if "All 64 required tests passed :)" not in text:
        raise ValueError("The Java registry log must come from a completed reference run.")
    registry = defaultdict(set)
    for kind, name in REGISTRY_LINE.findall(text):
        registry[kind].add(name)
    required = {*PACK_PREFIX, "block_entity_type", "entity_type", "fluid",
                "particle_type", "recipe_type", "sound_event"}
    if missing := required - registry.keys():
        raise ValueError(f"Missing Java registry inventories: {', '.join(sorted(missing))}")
    return registry


def java_resources(source):
    files = {}
    for directory in ("generated", "main"):
        root = source / "src" / directory / "resources"
        for namespace in ("assets/create", "data/create"):
            for path in (root / namespace).rglob("*"):
                if path.is_file():
                    files[path.relative_to(root).as_posix()] = path
    if not files:
        raise ValueError("Java assets and data were not found.")
    return files


def resource_rows(original, pack, entries):
    for path in sorted(original.keys() | entries):
        group = "/".join(PurePosixPath(path).parts[:3])
        if path not in original:
            status = "horizon_only_path"
        elif path not in entries:
            status = "java_only_path"
        elif pack.read(path) == original[path].read_bytes():
            status = "identical_bytes"
        else:
            status = "different_bytes"
        yield group, path, status


def pack_ids(pack, entries):
    declared = {
        kind: {
            "create:" + path.removeprefix(prefix).removesuffix(".json")
            for path in entries if path.startswith(prefix) and path.endswith(".json")
        }
        for kind, prefix in PACK_PREFIX.items()
    }
    for path in entries:
        if path.startswith(PACK_PREFIX["block"]) and path.endswith(".json"):
            if json.loads(pack.read(path)).get("item") is True:
                declared["item"].add(
                    "create:" + path.removeprefix(PACK_PREFIX["block"]).removesuffix(".json")
                )
    return declared


def runtime_registry(args, java, declared, snapshot):
    names = dict(zip(("ctl", "client", "resources"), args.horizon, strict=True))
    game = SimpleNamespace(**{key: value.resolve(strict=True) for key, value in names.items()})
    results = {}
    with fixture_world(game, "Parity-inventory", pack=snapshot) as world:
        for kind, (command, known, missing) in PROBES.items():
            control = min(declared[kind] & java[kind])
            recognized = world.command(command.format(control))
            unrecognized = world.command(command.format("create:parity_inventory_missing"))
            if not recognized.startswith(known) or missing not in unrecognized:
                raise ValueError(f"Unexpected {kind} probe replies: {recognized!r}, {unrecognized!r}.")
            names = sorted((java[kind] | declared[kind]) - {control})
            confirmed = {control}
            for start in range(0, len(names), 32):
                batch = names[start:start + 32]
                replies = world.commands(command.format(name) for name in batch)
                for name, reply in zip(batch, replies, strict=True):
                    if reply.startswith(known):
                        confirmed.add(name)
                    elif missing not in reply:
                        raise ValueError(f"Unexpected {kind} probe reply for {name}: {reply!r}.")
            results[kind] = confirmed
    return results


def registry_rows(java, declared, live):
    for kind, upstream in sorted(java.items()):
        candidates = declared.get(kind)
        if candidates is None:
            for name in sorted(upstream):
                yield kind, name, "native_review_required"
            continue
        checked = kind in live
        available = live.get(kind, candidates)
        for name in sorted(upstream | candidates | available):
            if name in upstream and name in available:
                status = "same_id_loaded" if checked else "same_id_in_pack"
            elif name in upstream:
                status = "no_same_id_loaded" if checked else "no_same_id_in_pack"
            elif name in available:
                status = "horizon_only_loaded_id" if checked else "horizon_only_pack_id"
            else:
                status = "declared_but_not_loaded"
            yield kind, name, status


def write_report(output, name, headings, rows):
    counts = defaultdict(Counter)
    with (output / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headings)
        for group, path, status in rows:
            writer.writerow((group, path, status))
            counts[group][status] += 1
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("java_source", type=Path)
    parser.add_argument("java_registry_log", type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/parity-inventory")
    parser.add_argument("--horizon", type=Path, nargs=3, metavar=("CTL", "CLIENT", "RESOURCES"),
                        help="check block, item and recipe IDs in an isolated running Horizon world")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(args.java_source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != CREATE_REVISION:
        parser.error(f"expected Java Create {CREATE_REVISION}, found {revision}")

    java = java_registry(args.java_registry_log)
    original = java_resources(args.java_source)
    args.output.mkdir(parents=True, exist_ok=True)
    pack_bytes = args.pack.read_bytes()
    with ZipFile(BytesIO(pack_bytes)) as pack:
        entries = {
            item.filename for item in pack.infolist()
            if not item.is_dir() and item.filename.startswith(("assets/create/", "data/create/"))
        }
        declared = pack_ids(pack, entries)
        live = {}
        if args.horizon:
            with TemporaryDirectory(prefix="hc-inventory-") as temporary:
                snapshot = Path(temporary) / "create.hmod"
                snapshot.write_bytes(pack_bytes)
                live = runtime_registry(args, java, declared, snapshot)
        registry = write_report(args.output, "registries.csv", ("kind", "id", "status"),
                                registry_rows(java, declared, live))
        resources = write_report(args.output, "resources.csv", ("group", "path", "status"),
                                 resource_rows(original, pack, entries))
    summary = {
        "java_revision": revision,
        "pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
        "horizon_build": args.horizon[1].resolve().parent.name if args.horizon else None,
        "registries": registry,
        "resources": resources,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()

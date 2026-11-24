#!/usr/bin/env python3
"""Stage the production Create native package from canonical Rust and content."""
from __future__ import annotations
import argparse
from pathlib import Path, PurePosixPath
from shutil import copy2
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "migration/create"
SOURCES = {
    "create_kinetic_slice.rs": ROOT / "native/kinetic_slice.rs",
    "kinetic_adapter.rs": ROOT / "native/kinetic_adapter.rs",
    "kinetic_controls.rs": ROOT / "native/kinetic_controls.rs",
}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--content-pack", type=Path, required=True,
                        help="0a-compatible full Create content .hmod to merge into this native package")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace staged output: {output}")
    (output / "src").mkdir(parents=True)
    for name in ("Cargo.toml", "horizon-mod.toml"):
        copy2(TEMPLATE / name, output / name)
    copy2(TEMPLATE / "src/lib.rs", output / "src/lib.rs")
    for name, source in SOURCES.items():
        destination = output / "src" / name
        copy2(source, destination)
        if name == "kinetic_adapter.rs":
            destination.write_text(destination.read_text().replace(
                "use super::create_kinetic_slice::{self, Node};",
                "use super::create_kinetic_slice as kinetic_slice;\nuse super::create_kinetic_slice::Node;",
            ))
    with ZipFile(args.content_pack.resolve(strict=True)) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or entry.filename == "horizon-mod.toml":
                continue
            relative = PurePosixPath(entry.filename)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ValueError(f"Unsafe content path in .hmod: {entry.filename}")
            if entry.filename == "icon.png":
                (output / "icon.png").write_bytes(archive.read(entry))
                continue
            if not (entry.filename.startswith("assets/") or entry.filename.startswith("data/")):
                raise ValueError(f"Unexpected package entry: {entry.filename}")
            destination = output.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
    print(f"Prepared production Create native package at {output}")

if __name__ == "__main__":
    main()

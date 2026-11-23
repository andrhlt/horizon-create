#!/usr/bin/env python3
"""Stage the bounded kinetic probe from the production adapter sources."""

from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "migration/kinetic-probe"
OUTPUT = ROOT / ".local/sdk-check/project"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "src").mkdir(exist_ok=True)
    for name in ("Cargo.toml", "horizon-mod.toml"):
        copy2(SOURCE / name, OUTPUT / name)
    copy2(SOURCE / "src/lib.rs", OUTPUT / "src/lib.rs")
    for name in ("kinetic_adapter.rs", "kinetic_slice.rs"):
        copy2(ROOT / "native" / name, OUTPUT / "src" / name)
    print(f"Prepared kinetic probe from tracked native sources at {OUTPUT}")


if __name__ == "__main__":
    main()

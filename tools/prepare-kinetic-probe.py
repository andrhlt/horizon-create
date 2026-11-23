"""Stage the bounded kinetic probe and Creative Motor board probe."""

import json
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
    lib = (SOURCE / "src/lib.rs").read_text()
    lib = lib.replace('#[path = "../../../native/kinetic_slice.rs"]\n', "")
    lib = lib.replace('#[path = "../../../native/kinetic_adapter.rs"]\n', "")
    (OUTPUT / "src/lib.rs").write_text(lib)
    copy2(SOURCE / "src/motor_board.rs", OUTPUT / "src/motor_board.rs")
    for name in ("kinetic_adapter.rs", "kinetic_slice.rs"):
        copy2(ROOT / "native" / name, OUTPUT / "src" / name)
    menu = OUTPUT / "data/create/horizon/menu"
    menu.mkdir(parents=True, exist_ok=True)
    copy2(SOURCE / "data/create/horizon/menu/creative_motor.json", menu / "creative_motor.json")
    blocks = OUTPUT / "data/create/horizon/block"
    blocks.mkdir(parents=True, exist_ok=True)
    for name in ("creative_motor", "shaft", "cogwheel", "large_cogwheel"):
        source = ROOT / f"content/data/create/horizon/block/{name}.json"
        definition = json.loads(source.read_text())
        definition.get("properties", {}).pop("waterloggable", None)
        (blocks / f"{name}.json").write_text(json.dumps(definition, indent=2) + "\n")
    print(f"Prepared kinetic probe and Creative Motor board at {OUTPUT}")


if __name__ == "__main__":
    main()

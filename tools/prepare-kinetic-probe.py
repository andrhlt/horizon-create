"""Stage the bounded kinetic probe and Creative Motor board probe."""

import hashlib
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
    source_menu = SOURCE / "data/create/horizon/menu/creative_motor.json"
    staged_menu = menu / "creative_motor.json"
    copy2(source_menu, staged_menu)
    source_hash = hashlib.sha256(source_menu.read_bytes()).hexdigest()
    staged_hash = hashlib.sha256(staged_menu.read_bytes()).hexdigest()
    if source_hash != staged_hash:
        raise RuntimeError(f"Creative Motor menu staging mismatch: {source_hash} != {staged_hash}")
    blocks = OUTPUT / "data/create/horizon/block"
    blocks.mkdir(parents=True, exist_ok=True)
    for name in ("creative_motor", "shaft", "cogwheel", "large_cogwheel"):
        source = ROOT / f"content/data/create/horizon/block/{name}.json"
        definition = json.loads(source.read_text())
        definition.get("properties", {}).pop("waterloggable", None)
        (blocks / f"{name}.json").write_text(json.dumps(definition, indent=2) + "\n")
    print(f"Creative Motor menu staged: data/create/horizon/menu/creative_motor.json sha256={staged_hash}")
    print(f"Prepared kinetic probe and Creative Motor board at {OUTPUT}")


if __name__ == "__main__":
    main()

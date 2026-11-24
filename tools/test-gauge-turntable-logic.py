#!/usr/bin/env python3
"""Compile and run the source-derived gauge and Turntable math checks."""

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
modules = ("gauge_logic", "turntable_motion", "kinetic_slice")
program = "\n".join(
    f"#[path = {json.dumps(str(ROOT / f'native/{name}.rs'))}]\nmod {name};"
    for name in modules
)
with tempfile.TemporaryDirectory(prefix="gauge-turntable-logic-") as directory:
    source = Path(directory) / "main.rs"
    binary = Path(directory) / "gauge-turntable-logic"
    source.write_text(program + "\nfn main() {}\n")
    subprocess.run(["rustc", "--edition=2024", "--test", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

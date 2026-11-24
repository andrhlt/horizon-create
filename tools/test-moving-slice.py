#!/usr/bin/env python3
"""Compile and run the pure moving-payload lifecycle checks."""
from pathlib import Path
import subprocess
import tempfile
import json

ROOT = Path(__file__).resolve().parents[1]

program = f'''#[path = {json.dumps(str(ROOT / "native/moving_slice.rs"))}]
mod moving_slice;
fn main() {{ println!("moving-slice-ok"); }}
'''

with tempfile.TemporaryDirectory(prefix="moving-slice-") as directory:
    source = Path(directory) / "main.rs"
    binary = Path(directory) / "moving-slice"
    source.write_text(program)
    subprocess.run(["rustc", "--edition=2024", "--test", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

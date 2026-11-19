#!/usr/bin/env python3
"""Capture tank action scripts using the pinned Create GameTest in a disposable clone.

Requires Java 21 and populated offline Gradle caches. Fill actions are fixture setup
through the fluid capability, not evidence of player bucket interaction.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ac0c444d9828da3453ae8cc65338e8de063286fb'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scripts', nargs='+', type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--reference', type=Path, default=ROOT / '.local/java-reference')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--java-home', type=Path, default=Path('/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    patch = ROOT / 'tools/java-tank-script.patch'
    patch_bytes = patch.read_bytes()
    patch_sha256 = hashlib.sha256(patch_bytes).hexdigest()
    archived_patch = output / 'runners' / (patch_sha256 + '.patch')
    archived_patch.parent.mkdir(parents=True, exist_ok=True)
    archived_patch.write_bytes(patch_bytes)
    with tempfile.TemporaryDirectory(prefix='tank-java-oracle-') as scratch:
        checkout = Path(scratch) / 'create'
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(args.reference.resolve()), str(checkout)], check=True)
        subprocess.run(['git', 'checkout', '--detach', REVISION], cwd=checkout, check=True)
        applied_patch = Path(scratch) / 'runner.patch'
        applied_patch.write_bytes(patch_bytes)
        subprocess.run(['git', 'apply', str(applied_patch)], cwd=checkout, check=True)
        env = {**os.environ, 'JAVA_HOME': str(args.java_home)}
        for script in args.scripts:
            shutil.rmtree(checkout / 'run/world', ignore_errors=True)
            script_bytes = script.read_bytes()
            captured_script = Path(scratch) / 'script.json'
            captured_script.write_bytes(script_bytes)
            env['TANK_SCRIPT'] = str(captured_script)
            start = time.monotonic()
            result = subprocess.run(['./gradlew', '--offline', 'runGameTestServer'], cwd=checkout, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            elapsed = time.monotonic() - start
            log = result.stdout.decode('utf-8', errors='replace')
            with gzip.open(output / (script.stem + '.log.gz'), 'wb') as file:
                file.write(result.stdout)
            rows = [json.loads(line.split('TANK_SCRIPT ', 1)[1]) for line in log.splitlines() if 'TANK_SCRIPT {' in line]
            expected = sum(len(a['positions']) if a['op'] == 'probe' else 1 if a['op'] in ('fill', 'drain', 'configure', 'use_item') else 0 for a in json.loads(script_bytes)['actions'])
            if result.returncode or len(rows) != expected or 'BUILD SUCCESSFUL' not in log:
                raise RuntimeError(f'{script.name}: capture failed ({len(rows)}/{expected} rows); see log')
            (output / (script.stem + '.jsonl')).write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
            metadata = {'revision': REVISION, 'minecraft': '1.21.1', 'neoforge': '21.1.219', 'script_sha256': hashlib.sha256(script_bytes).hexdigest(), 'patch_sha256': patch_sha256, 'elapsed_seconds': round(elapsed, 3), 'fill': 'fixture setup through Java fluid capability; not player bucket interaction'}
            (output / (script.stem + '.metadata.json')).write_text(json.dumps(metadata, indent=2) + '\n')
            print(f'{script.name}: {len(rows)} records in {elapsed:.2f}s', flush=True)


if __name__ == '__main__':
    run()

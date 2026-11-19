#!/usr/bin/env python3
"""Run shared tank scripts; core uses production logic, horizon stays headless."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from fixture_world import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, nargs='?', type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--backend', choices=('core', 'horizon'), default='horizon')
    parser.add_argument('--jobs', type=int, default=1, help='independent isolated worlds/processes in parallel')
    parser.add_argument('--script', type=lambda p: Path(p).resolve(strict=True))
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.backend == 'horizon' and any(getattr(args, key) is None for key in ('ctl', 'client', 'resources')):
        parser.error('horizon requires ctl, client and resources')
    scripts = [args.script] if args.script else sorted((ROOT / 'fixtures/tank-scripts').glob('*.json'))
    if args.backend == 'core' and not args.script:
        scripts = [p for p in scripts if not json.loads(p.read_text()).get('integration_only', False)]
    if not scripts:
        parser.error('no tank scripts')
    if args.backend == 'core':
        cached = sorted((ROOT / '.local/patched-launcher/rust').glob('*/bin/cargo'))
        cargo = str(cached[-1]) if cached else shutil.which('cargo')
        if not cargo:
            parser.error('Rust toolchain required for production-core checks')
        env = dict(os.environ)
        cache = ROOT / '.local/patched-launcher/cargo'
        if cache.is_dir():
            env['CARGO_HOME'] = str(cache)
        env['PATH'] = str(Path(cargo).parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([cargo, 'build', '--locked', '--offline', '--release', '--manifest-path',
                        str(ROOT / 'tools/tank-replay/Cargo.toml'), '--target-dir',
                        str(ROOT / '.local/tank-replay-target')], cwd=ROOT, env=env, check=True)
    output = ROOT / '.local/parity/tank-scripts' / args.backend
    def run_script(script):
        command = [sys.executable, str(ROOT / 'tools/run-tank-script.py'), args.backend, str(script),
                   '--output', str(output / (script.stem + '.jsonl')),
                   '--timing', str(output / (script.stem + '.timing.json'))]
        if args.backend == 'horizon':
            for key in ('ctl', 'client', 'resources'):
                command.extend(('--' + key, str(getattr(args, key))))
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        return script.name, result
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        for name, result in workers.map(run_script, scripts):
            if result.stdout:
                print(result.stdout, end='', flush=True)
            if result.returncode:
                failures.append(name)
                print(result.stderr, file=sys.stderr, end='', flush=True)
    print(f'{len(scripts) - len(failures)}/{len(scripts)} tank scripts matched Java through {args.backend}.')
    if failures:
        raise SystemExit('Failed tank scenarios: ' + ', '.join(failures))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Validate tracked scripts and data without importing code or launching games."""
import ast
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    counts = Counter()
    errors = []
    for name in filter(None, paths):
        path = ROOT / name
        kind = path.suffix
        if kind not in {'.py', '.json', '.jsonl', '.toml', '.sh'}:
            continue
        try:
            text = path.read_text(encoding='utf-8')
            if kind == '.py':
                ast.parse(text, filename=name)
            elif kind == '.json':
                json.loads(text)
            elif kind == '.jsonl':
                for number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        try:
                            json.loads(line)
                        except ValueError as error:
                            raise ValueError(f'line {number}: {error}') from error
            elif kind == '.toml':
                tomllib.loads(text)
            else:
                # Use Bash for Bash scripts, POSIX sh for the repository's sh scripts.
                shell = 'bash' if 'bash' in text.splitlines()[0] else 'sh'
                result = subprocess.run([shell, '-n', str(path)], capture_output=True, text=True)
                if result.returncode:
                    raise ValueError(result.stderr.strip())
            counts[kind] += 1
        except (OSError, SyntaxError, ValueError) as error:
            errors.append(f'{name}: {error}')
    for error in errors:
        print(error, file=sys.stderr)
    print('Syntax checks: ' + ', '.join(f'{number} {kind}' for kind, number in sorted(counts.items())))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())

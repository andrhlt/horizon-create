#!/usr/bin/env python3
"""Locate/download the official launcher used by the pinned mixin build."""
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'launcher@0.2.67'
ARCHIVE = 'horizon-launcher-macos-arm64.zip'

def main():
    if sys.platform != 'darwin':
        raise SystemExit('Automatic bootstrap currently supports macOS arm64 only; supply a compatible launcher explicitly.')
    import platform
    if platform.machine() != 'arm64':
        raise SystemExit('Automatic bootstrap currently supports macOS arm64 only.')
    directory = ROOT / '.local/toolchains/launcher-0.2.67'
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / ARCHIVE
    checksums = directory / 'SHA256SUMS'
    if not archive.exists() or not checksums.exists():
        subprocess.run(['gh', 'release', 'download', TAG, '--repo', 'horizon-rust/horizon',
                        '--pattern', ARCHIVE, '--pattern', 'SHA256SUMS', '--skip-existing',
                        '--dir', str(directory)], check=True, stdout=sys.stderr)
    expected = next(line.split()[0] for line in checksums.read_text().splitlines()
                    if line.split()[-1].lstrip('*') == ARCHIVE)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Checksum mismatch: {archive}; remove the bad download and retry.')
    with zipfile.ZipFile(archive) as package:
        member = next(name for name in package.namelist()
                      if name.endswith('/Contents/MacOS/horizon-launcher'))
        payload = package.read(member)
    executable = directory / 'horizon-launcher'
    if not executable.exists() or executable.read_bytes() != payload:
        executable.write_bytes(payload)
        executable.chmod(0o755)
    print(executable)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Check the pinned upstream snapshot without executing its code."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'vendor' / 'pstack')
    args = parser.parse_args()
    root = args.root.resolve()
    receipt = json.loads((root / 'upstream.json').read_text())
    failures = []
    for name, expected in receipt['files'].items():
        path = root / name
        if not path.resolve().is_relative_to(root):
            failures.append(f'Unsafe receipt path: {name}')
        elif not path.is_file():
            failures.append(f'Missing: {name}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f'Changed: {name}')
    allowed = set(receipt['files']) | {'upstream.json', 'UPSTREAM.md'}
    for path in root.rglob('*'):
        if path.is_file() and path.relative_to(root).as_posix() not in allowed:
            failures.append(f'Unrecorded: {path.relative_to(root)}')
    if failures:
        print('\n'.join(failures))
        return 1
    print(f"PASS: {len(receipt['files'])} upstream files match pstack {receipt['version']} at {receipt['commit']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

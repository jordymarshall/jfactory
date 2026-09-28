#!/usr/bin/env python3
"""Render docs/diagrams/*.mmd to PNG so diagrams show everywhere, including GitHub's mobile app.

GitHub's web view renders Mermaid code blocks, but its mobile app shows them as raw code, so the README
links committed images. Edit the .mmd source, run this script, and commit the source, the PNG and
manifest.json together; tests/test_links.py fails when a source changed without a re-render.
Needs Node/npm and Chrome (set CHROME to its path if it is not google-chrome).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / 'docs' / 'diagrams'
MERMAID_CLI = '@mermaid-js/mermaid-cli@11'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    chrome = os.environ.get('CHROME') or shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome or not shutil.which('npx'):
        print('Needs npx and Chrome; set CHROME to the browser path', file=sys.stderr)
        return 1
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as config:
        json.dump({'executablePath': chrome, 'args': ['--no-sandbox']}, config)
    manifest = {}
    for source in sorted(DIAGRAMS.glob('*.mmd')):
        target = source.with_suffix('.png')
        subprocess.run(['npx', '-y', MERMAID_CLI, '-p', config.name, '-i', str(source), '-o', str(target),
                        '-w', '1200', '-s', '2', '-b', 'white'], check=True, capture_output=True)
        manifest[source.name] = digest(source)
        print(f'Rendered {target.relative_to(ROOT)}')
    (DIAGRAMS / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

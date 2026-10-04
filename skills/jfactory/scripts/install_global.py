#!/usr/bin/env python3
"""Install jfactory's user-level skills (agent-coordinator) into the user's GLOBAL skill folders.

The agent hub must work in any repository and in a fresh session, so setup also copies it to:

    ~/.claude/skills/agent-coordinator        Claude Code
    $CODEX_HOME/skills/agent-coordinator      Codex (CODEX_HOME defaults to ~/.codex)

Each copy carries a receipt (.jfactory-global.json) with its files' hashes. A rerun updates an older copy that
nobody edited, does nothing when the copy is current, and refuses to overwrite a copy that someone edited by hand
(it says so and leaves it). Cloud workspaces are fresh machines, so run this from the repository's setup script:

    python3 <bundle>/scripts/install_global.py            # from an installed bundle
    python3 <bundle>/scripts/install_global.py --check    # exit 1 when a copy is missing or stale
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

GLOBAL_SKILLS = ('agent-coordinator',)
RECEIPT = '.jfactory-global.json'


def targets(home=None, env=None):
    env = os.environ if env is None else env
    home = Path(home or Path.home())
    codex = Path(env.get('CODEX_HOME') or home / '.codex')
    return {'claude': home / '.claude' / 'skills', 'codex': codex / 'skills'}


def files(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*'))
            if p.is_file() and p.name != RECEIPT and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def install_one(source, dest, check=False):
    """Install or update one skill folder. Returns (state, message): installed, updated, current, edited, stale."""
    wanted = files(source)
    if dest.is_symlink():
        return 'edited', f'{dest} is a symlink; leaving it alone'
    if dest.exists():
        receipt = dest / RECEIPT
        if not receipt.is_file():
            return 'edited', f'{dest} exists without a jfactory receipt; leaving it alone'
        recorded = json.loads(receipt.read_text()).get('files', {})
        present = files(dest)
        if present != recorded:
            return 'edited', f'{dest} was edited by hand; leaving it alone (delete it to reinstall)'
        if present == wanted:
            return 'current', f'{dest} is current'
        if check:
            return 'stale', f'{dest} is older than this bundle'
    elif check:
        return 'stale', f'{dest} is missing'
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.jfactory-global-', dir=dest.parent) as tmp:
        stage = Path(tmp) / 'new'
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', RECEIPT))
        (stage / RECEIPT).write_text(json.dumps({'schema': 1, 'source': str(source), 'files': wanted}, indent=1) + '\n')
        old = Path(tmp) / 'old'
        existed = dest.exists()
        if existed:
            os.replace(dest, old)
        try:
            os.replace(stage, dest)
        except BaseException:
            if existed:
                os.replace(old, dest)
            raise
    return ('updated' if existed else 'installed'), f'{dest} {"updated" if existed else "installed"}'


def install_global(bundle, home=None, env=None, check=False, log=print):
    """Install every user-level skill from an installed or source bundle. Returns True when all are current."""
    bundle = Path(bundle)
    ok = True
    for name in GLOBAL_SKILLS:
        source = bundle / 'skills' / name
        if not (source / 'SKILL.md').is_file():
            log(f'{source} has no SKILL.md; skipped')
            ok = False
            continue
        for host, folder in targets(home, env).items():
            state, text = install_one(source, folder / name, check=check)
            log(f'{host}: {text}')
            ok = ok and state in ('installed', 'updated', 'current')
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='report missing or stale copies without writing')
    parser.add_argument('--home', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    bundle = Path(__file__).resolve().parents[1]
    return 0 if install_global(bundle, home=args.home, check=args.check) else 1


if __name__ == '__main__':
    sys.exit(main())

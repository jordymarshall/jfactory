#!/usr/bin/env python3
"""Install a reviewed local jstack checkout without replacing user instructions."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

START = '<!-- jstack:start -->'
END = '<!-- jstack:end -->'
LAYOUTS = {'codex': ('.agents/skills/jstack', 'AGENTS.md'),
           'claude': ('.claude/skills/jstack', 'CLAUDE.md'),
           'cursor': ('.cursor/skills/jstack', 'AGENTS.md')}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError(f'Symlinks are not supported in payload: {p}')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
            result[p.relative_to(root).as_posix()] = p.read_bytes()
    return result


def managed_block(skill_path):
    return (f'{START}\n\n**Engineering workflow.** '
            f'Use [jstack]({skill_path}/SKILL.md) proactively for repository setup and engineering work. '
            'Establish or resume the agreed objective, map acceptance criteria to actual verification, '
            'implement/check/correct within scope, and update existing canonical records. '
            'Required application behavior needs application evidence; component checks alone cannot close it. '
            'Deliver authorized changes as a PR on a task branch. Use a draft when required proof is blocked; '
            'do not merge, push the base branch or deploy without explicit authorization. '
            'Preserve this repository’s product decisions and applicable instructions.\n\n'
            f'{END}')


def install(source, target, agent='codex', update=False):
    target = target.resolve()
    if not target.is_dir():
        raise ValueError('Target must be an existing project directory')
    relative, entry_name = LAYOUTS[agent]
    dest = target / relative
    entry = target / entry_name
    for path in [entry, dest, *(p for p in dest.parents if p.is_relative_to(target))]:
        if path.is_symlink():
            raise ValueError(f'Refusing symlink target: {path}')
    bundle = source / 'skills/jstack'
    if bundle.is_symlink() or not bundle.is_dir() or not (bundle / 'SKILL.md').is_file():
        raise ValueError('Source bundle must contain skills/jstack/SKILL.md')
    files = payload(bundle)
    hashes = {name: digest(data) for name, data in files.items()}
    receipt_path = dest / '.jstack-install.json'
    old = None
    if dest.exists():
        if not receipt_path.is_file():
            raise ValueError('Existing skill has no installation receipt; reconcile manually')
        old = json.loads(receipt_path.read_text())
        if old.get('agent') != agent:
            raise ValueError('Installation host mismatch')
        existing = payload(dest)
        existing.pop('.jstack-install.json', None)
        if {n: digest(b) for n, b in existing.items()} != old['files']:
            raise ValueError('Installed files were modified; reconcile before updating')
        if hashes != old['files'] and not update:
            raise ValueError('New payload requires --update after reviewing changes')
    original = entry.read_text() if entry.exists() else ''
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError('Malformed or duplicate jstack instruction block')
    block = managed_block(relative)
    if START in original:
        a, b = original.index(START), original.index(END) + len(END)
        if b < a or old is None or original[a:b] != old['instruction_block']:
            raise ValueError('Existing instruction block is unmanaged or modified')
        updated = original[:a] + block + original[b:]
    elif old:
        raise ValueError('Managed instruction block was removed; reconcile manually')
    else:
        updated = original + ('\n\n' if original else '') + block + '\n'
    # All conflict checks above precede any write.
    try:
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                           stderr=subprocess.DEVNULL, text=True).strip()
    except subprocess.CalledProcessError:
        revision = None
    try:
        source_dirty = bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'],
                                                    stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        source_dirty = None
    receipt = {'schema': 1, 'repository': 'https://github.com/jordymarshall/jstack',
        'source_commit': revision, 'source_dirty': source_dirty, 'agent': agent,
        'files': hashes, 'instruction_block': block}
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Stage the complete payload so file/directory layout changes cannot strand
    # a half-updated installation. Keep the old tree until both replacements succeed.
    with tempfile.TemporaryDirectory(prefix='.jstack-install-', dir=dest.parent) as tmp:
        stage = Path(tmp) / 'new'
        backup = Path(tmp) / 'old'
        for name, data in files.items():
            p = stage / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            shutil.copymode(source / 'skills/jstack' / name, p)
        (stage / '.jstack-install.json').write_text(json.dumps(receipt, indent=2) + '\n')
        next_entry = Path(tmp) / 'instructions'
        next_entry.write_text(updated)
        if entry.exists():
            shutil.copymode(entry, next_entry)
        if (entry.read_text() if entry.exists() else '') != original:
            raise ValueError('Instructions changed during installation; retry after reviewing')
        if old:
            current = payload(dest)
            current.pop('.jstack-install.json', None)
            if {n: digest(b) for n, b in current.items()} != old['files']:
                raise ValueError('Installed files changed during installation')
        try:
            if old:
                os.replace(dest, backup)
            os.replace(stage, dest)
            os.replace(next_entry, entry)
        except BaseException:
            # Cancellation must restore the backup before TemporaryDirectory
            # cleanup can remove it. Re-raise rather than swallowing interrupts.
            if backup.exists():
                if dest.exists():
                    shutil.rmtree(dest)
                os.replace(backup, dest)
            elif not old and not stage.exists() and dest.exists():
                shutil.rmtree(dest)
            if not next_entry.exists():
                if original:
                    restored = Path(tmp) / 'restored-instructions'
                    restored.write_text(original)
                    os.replace(restored, entry)
                elif entry.exists():
                    entry.unlink()
            raise
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    parser.add_argument('--agent', choices=LAYOUTS, default='codex')
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    try:
        dest = install(Path(__file__).resolve().parents[1], args.target, args.agent, args.update)
        print(f'Installed {dest}. Review the diff, then follow its repository setup; reload the agent session.')
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f'Installation refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

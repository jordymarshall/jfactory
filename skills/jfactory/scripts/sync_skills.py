#!/usr/bin/env python3
"""Keep every project skill discoverable in both Codex (.agents/skills) and Claude Code (.claude/skills).

Each host finds skills only in its own folder, one level deep. A skill that lives in one folder, or inside the
jfactory bundle (jfactory-ux, show-me), is invisible to the other host. This writes a short pointer skill in the
other folder: the same frontmatter, then "read the real SKILL.md". Pointers carry a marker line, so the tool only
ever rewrites or removes files it wrote.

    python3 <bundle>/scripts/sync_skills.py          # write missing and stale pointers, remove orphaned ones
    python3 <bundle>/scripts/sync_skills.py --check  # exit 1 and list drift without writing (CI and setup_check)
"""
import argparse
import re
import sys
from pathlib import Path

HOSTS = ('.agents/skills', '.claude/skills')
MARKER = '<!-- jfactory sync_skills: pointer to {path}; edit the real skill, then run sync_skills.py -->'
MARK_RE = re.compile(r'<!-- jfactory sync_skills: pointer to (\S+);')


def frontmatter(text):
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return match.group(1) if match else None


# The installer's Claude Code entry for a bundle installed under another host's folder (scripts/install.py).
INSTALLER_ENTRY = 'This is the Claude Code entry for jfactory.'


def is_pointer(path, ours_only=False):
    """A pointer is not a real skill. Only pointers this tool wrote (the marker) are rewritten or removed."""
    try:
        text = path.read_text()
    except OSError:
        return False
    return bool(MARK_RE.search(text)) or (not ours_only and INSTALLER_ENTRY in text)


def sources(root):
    """name -> path of each real skill: top-level skills in either host folder, then skills nested one level inside
    a top-level skill (a bundle's own skills). The first found keeps the name; a later one with that name is skipped."""
    found, skipped = {}, []
    tops = [p for host in HOSTS for p in sorted((root / host).glob('*/SKILL.md'))]
    nested = [p for host in HOSTS for p in sorted((root / host).glob('*/skills/*/SKILL.md'))]
    for path in tops + nested:
        if path.parent.is_symlink() or is_pointer(path):
            continue
        meta = frontmatter(path.read_text())
        name = re.search(r'^name:\s*(\S+)', meta or '', re.M)
        if not name:
            continue
        key = name.group(1)
        if key in found:
            if path in nested:
                skipped.append(f'{path.relative_to(root)} (name "{key}" is taken by {found[key].relative_to(root)})')
            continue
        found[key] = path
    return found, skipped


def pointer_text(root, path):
    real = path.relative_to(root).as_posix()
    return (f'---\n{frontmatter(path.read_text())}\n---\n\n{MARKER.format(path=real)}\n\n'
            f'Read `{real}` now and follow it. Its links are relative to `{path.parent.relative_to(root).as_posix()}/`.\n')


def plan(root):
    """Return (writes {path: text}, removals [path], kept [reason]) needed to make both hosts list every skill."""
    found, kept = sources(root)
    writes, removals = {}, []
    for name, path in found.items():
        for host in HOSTS:
            target = root / host / name / 'SKILL.md'
            if target == path:
                continue
            if target.exists() and not is_pointer(target, ours_only=True):
                # Someone else's file, such as the installer's Claude entry (it records its hash): leave it alone.
                kept.append(f'{target.relative_to(root)} (not written by sync_skills)')
                continue
            text = pointer_text(root, path)
            if not target.exists() or target.read_text() != text:
                writes[target] = text
    wanted = {root / host / name / 'SKILL.md' for name in found for host in HOSTS}
    for host in HOSTS:
        for target in sorted((root / host).glob('*/SKILL.md')):
            if is_pointer(target, ours_only=True) and target not in wanted:
                removals.append(target)
    return writes, removals, kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default='.')
    parser.add_argument('--check', action='store_true', help='report drift and exit 1 instead of writing')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    writes, removals, kept = plan(root)
    for line in kept:
        print(f'Kept: {line}')
    if args.check:
        for path in writes:
            print(f'FAIL: {path.relative_to(root)} is missing or stale')
        for path in removals:
            print(f'FAIL: {path.relative_to(root)} points to a skill that no longer exists')
        if writes or removals:
            print('Run sync_skills.py (without --check) and commit the result.')
            return 1
        print('PASS: every skill is listed for Codex (.agents/skills) and Claude Code (.claude/skills)')
        return 0
    for path, text in writes.items():
        if any(p.is_symlink() for p in (path, path.parent)):
            raise SystemExit(f'Refusing symlink: {path.relative_to(root)}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f'Wrote {path.relative_to(root)}')
    for path in removals:
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()
        print(f'Removed {path.relative_to(root)}')
    print(f'{len(writes)} written, {len(removals)} removed')
    return 0


if __name__ == '__main__':
    sys.exit(main())

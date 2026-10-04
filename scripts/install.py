#!/usr/bin/env python3
"""Install a reviewed local jfactory checkout without replacing user instructions."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

START = '<!-- jfactory:start -->'
END = '<!-- jfactory:end -->'
LEGACY_START = '<!-- jstack:start -->'
LEGACY_END = '<!-- jstack:end -->'
LAYOUTS = {'codex': ('.agents/skills/jfactory', 'AGENTS.md'),
           'claude': ('.claude/skills/jfactory', 'CLAUDE.md'),
           'cursor': ('.cursor/skills/jfactory', 'AGENTS.md')}


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
            f'Use [jfactory]({skill_path}/SKILL.md) proactively for repository setup and engineering work. '
            'For "Setup jfactory" or an update, follow its complete repository adoption procedure after installation: reconcile stale docs and instructions, interview the owner about the product, prepare tools/environments and delivery gates, and report readiness with evidence and exact gaps. Setup is finished only when its scripts/setup_check.py passes or reports only owner-blocked areas. '
            'Resume the same setup record on subsequent runs. '
            f'Before setup or establishing/revising objectives and goals, read the complete [grilling skill]({skill_path}/skills/grilling/SKILL.md), then reuse settled answers. '
            f'Before explaining changes, PRs or choices needing understanding or feedback, read the complete [show-me skill]({skill_path}/skills/show-me/SKILL.md). '
            'These skills include Matt Pocock\'s and HumanLayer\'s full pinned methods with jfactory host integration. '
            'Keep the project-owned product, engineering and UI/UX intent and job goals current for verifiers. '
            'Establish or resume the agreed objective, map acceptance criteria to actual verification, '
            'implement/check/correct within scope, and update existing canonical records. '
            'For meaningful UI changes, use its UX skill to inspect real interactions and motion; '
            'research approved reference apps when requested or needed for a design decision. '
            'When that work needs login, proactively prepare a supported browser handoff and guide the owner through sign-in. '
            'Required application behavior needs application evidence; component checks alone cannot close it. '
            'Prove key job goals with goal tests (Playwright specs from job goals), and verifiers add a UX explore of each changed journey. '
            'Verify only what changed: run the suites of features whose code changed, give a document-only edit a review of those documents, '
            'keep full journeys and full verdicts for risky areas, and review the diff and the features it touches, not unrelated areas. '
            f'Write everything people read with the ASD-STE100 writing rules ({skill_path}/references/writing.md): short sentences, one point each, active voice, common words, and technical terms explained. '
            'Obey the waiting budget: wait on notifications, at most 5 checks per wait, the same failure twice means stop and report, '
            'and launch nothing while sessions are idle, failing or out of usage. '
            'Deliver authorized changes as a ready-for-review PR on a task branch by default; use drafts only when requested or required by repository rules. '
            'Report the objective, decisions/assumptions, implemented behavior, actual verification evidence and gaps, and PR link in the completion message. '
            'Check the installed version and overlapping PRs when working across worktrees. '
            'Review status does not establish verification or merge readiness. After verification, enable protected auto-merge under the repository\'s standing authorization; follow jfactory\'s auto-merge procedure. '
            'In-session subagents only do read-only research; work that splits into independent units or is too big for one session goes to separate Conductor workspaces launched with coord.py. '
            'CI confirms what you already checked: run the planned checks before each push, classify a CI failure before re-running it (infrastructure gets one re-run), and fix a red base branch first. '
            'Keep auto-merge off when required proof, permissions or enforced checks are missing. Never bypass checks or push the base branch directly. Respect the repository\'s release policy. '
            'Preserve this repository’s product decisions and applicable instructions.\n\n'
            f'{END}')


CLAUDE_POINTER = '.claude/skills/jfactory/SKILL.md'


def claude_pointer(skill_path, skill_text):
    """A Claude Code skill entry for a bundle installed under another host's layout.

    Claude Code discovers skills only under .claude/skills. Without this entry, "use jfactory" loads nothing there
    and the agent falls back to its own habits, such as in-session subagents for parallel work.
    """
    description = ''
    if skill_text.startswith('---'):
        for line in skill_text.split('---', 2)[1].splitlines():
            if line.startswith('description:'):
                description = line[len('description:'):].strip()
    return (f'---\nname: jfactory\ndescription: {description}\n---\n\n'
            f'# jfactory\n\nThis is the Claude Code entry for jfactory. The bundle is installed at `{skill_path}/`, '
            f'where it is shared with other agent hosts. Read `{skill_path}/SKILL.md` now and follow it. Its links are '
            'relative to that folder.\n\nThis file is written by the jfactory installer; do not edit it.\n')


def uses_claude(target):
    return (target / 'CLAUDE.md').exists() or (target / '.claude').is_dir()


def install(source, target, agent='codex', update=False):
    target = target.resolve()
    if not target.is_dir():
        raise ValueError('Target must be an existing project directory')
    relative, entry_name = LAYOUTS[agent]
    dest = target / relative
    legacy = dest.with_name('jstack')
    entry = target / entry_name
    for path in [entry, dest, legacy, *(p for p in dest.parents if p.is_relative_to(target))]:
        if path.is_symlink():
            raise ValueError(f'Refusing symlink target: {path}')
    pointer = target / CLAUDE_POINTER if agent != 'claude' and uses_claude(target) else None
    if pointer:
        for path in [pointer, *(p for p in pointer.parents if p.is_relative_to(target) and p != target)]:
            if path.is_symlink():
                raise ValueError(f'Refusing symlink target: {path}')
        ours = ('SKILL.md', '.SKILL.md.jfactory-tmp')
        if pointer.parent.is_dir() and any(p.name not in ours for p in pointer.parent.iterdir()):
            raise ValueError(f'{pointer.parent.relative_to(target)} holds another jfactory installation; '
                             'reconcile before installing for a second host')
    if legacy.exists() and dest.exists():
        raise ValueError('Both jstack and jfactory exist; reconcile before updating')
    migrating = legacy.exists()
    if migrating and not update:
        raise ValueError('Legacy installation migration requires --update')
    previous = legacy if migrating else dest
    receipt_name = '.jstack-install.json' if migrating else '.jfactory-install.json'
    bundle = source / 'skills/jfactory'
    if bundle.is_symlink() or not bundle.is_dir() or not (bundle / 'SKILL.md').is_file():
        raise ValueError('Source bundle must contain skills/jfactory/SKILL.md')
    files = payload(bundle)
    hashes = {name: digest(data) for name, data in files.items()}
    receipt_path = previous / receipt_name
    old = None
    if previous.exists():
        if not receipt_path.is_file():
            raise ValueError('Existing skill has no installation receipt; reconcile manually')
        old = json.loads(receipt_path.read_text())
        if old.get('agent') != agent:
            raise ValueError('Installation host mismatch')
        existing = payload(previous)
        existing.pop(receipt_name, None)
        if {n: digest(b) for n, b in existing.items()} != old['files']:
            raise ValueError('Installed files were modified; reconcile before updating')
        if hashes != old['files'] and not update:
            raise ValueError('New payload requires --update after reviewing changes')
    original = entry.read_text() if entry.exists() else ''
    start, end = (LEGACY_START, LEGACY_END) if migrating else (START, END)
    other_start, other_end = (START, END) if migrating else (LEGACY_START, LEGACY_END)
    if (other_start in original or other_end in original
            or original.count(start) != original.count(end) or original.count(start) > 1):
        raise ValueError('Malformed, mixed or duplicate instruction blocks; reconcile manually')
    pointer_text = claude_pointer(relative, files['SKILL.md'].decode()) if pointer else None
    if pointer and pointer.exists():
        current = pointer.read_bytes()
        recorded = (old or {}).get('host_pointers', {}).get(CLAUDE_POINTER)
        if current != pointer_text.encode() and digest(current) != recorded:
            raise ValueError(f'{CLAUDE_POINTER} exists and was not written by this installer; reconcile manually')
    block = managed_block(relative)
    if start in original:
        a, b = original.index(start), original.index(end) + len(end)
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
    except (subprocess.CalledProcessError, FileNotFoundError):  # not a checkout, or no git
        revision = None
    try:
        source_dirty = bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'],
                                                    stderr=subprocess.DEVNULL))
    except (subprocess.CalledProcessError, FileNotFoundError):
        source_dirty = None
    receipt = {'schema': 1, 'repository': 'https://github.com/jordymarshall/jfactory',
        'source_commit': revision, 'source_dirty': source_dirty, 'agent': agent,
        'files': hashes, 'instruction_block': block,
        **({'host_pointers': {CLAUDE_POINTER: digest(pointer_text.encode())}} if pointer else {})}
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Stage the complete payload so file/directory layout changes cannot strand
    # a half-updated installation. Keep the old tree until both replacements succeed.
    with tempfile.TemporaryDirectory(prefix='.jfactory-install-', dir=dest.parent) as tmp:
        stage = Path(tmp) / 'new'
        backup = Path(tmp) / 'old'
        for name, data in files.items():
            p = stage / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            shutil.copymode(source / 'skills/jfactory' / name, p)
        (stage / '.jfactory-install.json').write_text(json.dumps(receipt, indent=2) + '\n')
        next_entry = Path(tmp) / 'instructions'
        next_entry.write_text(updated)
        if entry.exists():
            shutil.copymode(entry, next_entry)
        if (entry.read_text() if entry.exists() else '') != original:
            raise ValueError('Instructions changed during installation; retry after reviewing')
        if old:
            current = payload(previous)
            current.pop(receipt_name, None)
            if {n: digest(b) for n, b in current.items()} != old['files']:
                raise ValueError('Installed files changed during installation')
        try:
            if old:
                os.replace(previous, backup)
            os.replace(stage, dest)
            os.replace(next_entry, entry)
        except BaseException:
            # Cancellation must restore the backup before TemporaryDirectory
            # cleanup can remove it. Re-raise rather than swallowing interrupts.
            if backup.exists():
                if dest.exists():
                    shutil.rmtree(dest)
                os.replace(backup, previous)
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
    if pointer:
        # After the bundle is in place, so the entry never points at a missing installation.
        pointer.parent.mkdir(parents=True, exist_ok=True)
        staged = pointer.with_name('.SKILL.md.jfactory-tmp')
        staged.write_text(pointer_text)
        os.replace(staged, pointer)
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    parser.add_argument('--agent', choices=LAYOUTS, default='codex')
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    try:
        dest = install(Path(__file__).resolve().parents[1], args.target, args.agent, args.update)
        print(f'Installed {dest}. Repository adoption is still pending. Read {dest / "SKILL.md"} '
              'and follow references/setup.md now, including the owner interview. Finish by running '
              f'python3 {dest / "scripts" / "setup_check.py"} --remote. Reload skill discovery afterward if needed; '
              'do not report the project ready from installation alone.')
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f'Installation refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

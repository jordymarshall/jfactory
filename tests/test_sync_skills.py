import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/scripts/sync_skills.py'
spec = importlib.util.spec_from_file_location('sync_skills', SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def skill(path, name, body='Real instructions.\n'):
    path.mkdir(parents=True, exist_ok=True)
    (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Does {name} things.\n---\n\n{body}')


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], capture_output=True,
                              text=True)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout

    def test_every_skill_reaches_both_hosts_and_check_then_passes(self):
        skill(self.root / '.agents/skills/ux-check', 'ux-check')
        skill(self.root / '.claude/skills/only-claude', 'only-claude')
        skill(self.root / '.agents/skills/bundle/skills/inner', 'inner')
        out = self.run_cli('--check', code=1)
        self.assertIn('.claude/skills/ux-check/SKILL.md is missing or stale', out)
        self.run_cli()
        pointer = (self.root / '.claude/skills/ux-check/SKILL.md').read_text()
        self.assertTrue(pointer.startswith('---\nname: ux-check\ndescription: Does ux-check things.\n---\n'))
        self.assertIn('Read `.agents/skills/ux-check/SKILL.md` now', pointer)
        self.assertTrue((self.root / '.agents/skills/only-claude/SKILL.md').is_file())
        for host in sync.HOSTS:
            self.assertIn('.agents/skills/bundle/skills/inner/SKILL.md', (self.root / host / 'inner/SKILL.md').read_text())
        self.assertIn('PASS', self.run_cli('--check'))

    def test_a_changed_description_or_removed_skill_is_drift(self):
        skill(self.root / '.agents/skills/a', 'a')
        skill(self.root / '.agents/skills/b', 'b')
        self.run_cli()
        skill(self.root / '.agents/skills/a', 'a', body='new body only; frontmatter same\n')
        self.assertIn('PASS', self.run_cli('--check'))
        (self.root / '.agents/skills/a/SKILL.md').write_text('---\nname: a\ndescription: Changed.\n---\n')
        self.assertIn('.claude/skills/a/SKILL.md is missing or stale', self.run_cli('--check', code=1))
        (self.root / '.agents/skills/b/SKILL.md').unlink()
        (self.root / '.agents/skills/b').rmdir()
        self.assertIn('.claude/skills/b/SKILL.md points to a skill that no longer exists', self.run_cli('--check', code=1))
        self.run_cli()
        self.assertFalse((self.root / '.claude/skills/b').exists())

    def test_files_it_did_not_write_are_left_alone(self):
        skill(self.root / '.agents/skills/jfactory', 'jfactory')
        entry = self.root / '.claude/skills/jfactory/SKILL.md'
        entry.parent.mkdir(parents=True)
        entry.write_text('---\nname: jfactory\n---\n\nThis is the Claude Code entry for jfactory. Read it.\n')
        skill(self.root / '.claude/skills/mine', 'mine')
        skill(self.root / '.agents/skills/mine', 'mine', body='A different real skill with the same name.\n')
        before = entry.read_text()
        out = self.run_cli()
        self.assertEqual(entry.read_text(), before)  # The installer records this file's hash.
        self.assertIn('Kept: .claude/skills/jfactory/SKILL.md', out)
        self.assertIn('Real instructions', (self.root / '.claude/skills/mine/SKILL.md').read_text())

    def test_a_bundle_skill_never_takes_a_project_skills_name(self):
        skill(self.root / '.agents/skills/grilling', 'grilling', body='Project grilling.\n')
        skill(self.root / '.agents/skills/jfactory/skills/grilling', 'grilling', body='Bundle grilling.\n')
        out = self.run_cli()
        self.assertIn('.agents/skills/jfactory/skills/grilling/SKILL.md (name "grilling" is taken', out)
        self.assertIn('.agents/skills/grilling/SKILL.md', (self.root / '.claude/skills/grilling/SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()

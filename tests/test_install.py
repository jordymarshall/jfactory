import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / 'project'
        self.target.mkdir()

    def test_preserves_instructions_and_is_idempotent(self):
        entry = self.target / 'AGENTS.md'
        entry.write_text('# My project\nDo not erase this.\n')
        dest = installer.install(ROOT, self.target)
        once = entry.read_bytes()
        installer.install(ROOT, self.target)
        self.assertEqual(once, entry.read_bytes())
        self.assertTrue(once.startswith(b'# My project\nDo not erase this.\n'))
        receipt = json.loads((dest / '.jstack-install.json').read_text())
        self.assertIn('vendor/pstack/LICENSE', receipt['files'])

    def test_modified_payload_refuses_update_without_mutation(self):
        dest = installer.install(ROOT, self.target)
        skill = dest / 'SKILL.md'
        skill.write_text('local custom version')
        entry = (self.target / 'AGENTS.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'modified'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(skill.read_text(), 'local custom version')
        self.assertEqual((self.target / 'AGENTS.md').read_bytes(), entry)

    def test_changed_instruction_block_refuses_before_payload_write(self):
        dest = installer.install(ROOT, self.target)
        entry = self.target / 'AGENTS.md'
        entry.write_text(entry.read_text().replace('Deliver authorized', 'Never deliver'))
        before = (dest / '.jstack-install.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'modified'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(before, (dest / '.jstack-install.json').read_bytes())

    def test_reviewed_update_removes_old_payload_preserves_surrounding_text(self):
        source = Path(self.tmp.name) / 'source'
        shutil.copytree(ROOT / 'skills', source / 'skills')
        removed = source / 'skills/jstack/obsolete.txt'
        removed.write_text('old')
        dest = installer.install(source, self.target)
        entry = self.target / 'AGENTS.md'
        entry.write_text(entry.read_text() + '\nOwner addition\n')
        removed.unlink()
        (source / 'skills/jstack/new.txt').write_text('new')
        with self.assertRaisesRegex(ValueError, '--update'):
            installer.install(source, self.target)
        installer.install(source, self.target, update=True)
        self.assertFalse((dest / 'obsolete.txt').exists())
        self.assertEqual((dest / 'new.txt').read_text(), 'new')
        self.assertTrue(entry.read_text().endswith('Owner addition\n'))

    def test_host_layouts(self):
        for host, (directory, filename) in installer.LAYOUTS.items():
            with self.subTest(host=host):
                target = self.target / host
                target.mkdir()
                installer.install(ROOT, target, host)
                self.assertTrue((target / directory / 'SKILL.md').is_file())
                self.assertIn(directory, (target / filename).read_text())

    def test_update_handles_directory_to_file_transition(self):
        source = Path(self.tmp.name) / 'source'
        shutil.copytree(ROOT / 'skills', source / 'skills')
        nested = source / 'skills/jstack/transition/old.md'
        nested.parent.mkdir()
        nested.write_text('old')
        dest = installer.install(source, self.target)
        shutil.rmtree(nested.parent)
        nested.parent.write_text('replacement file')
        installer.install(source, self.target, update=True)
        self.assertEqual((dest / 'transition').read_text(), 'replacement file')
        installer.install(source, self.target)

    def test_missing_source_cannot_erase_installation(self):
        dest = installer.install(ROOT, self.target)
        before = (dest / 'SKILL.md').read_bytes()
        missing = Path(self.tmp.name) / 'missing'
        with self.assertRaisesRegex(ValueError, 'Source bundle'):
            installer.install(missing, self.target, update=True)
        self.assertEqual(before, (dest / 'SKILL.md').read_bytes())

    def test_cancellation_during_replacement_restores_installation(self):
        dest = installer.install(ROOT, self.target)
        before = (dest / 'SKILL.md').read_bytes()
        entry = (self.target / 'AGENTS.md').read_bytes()
        replace = installer.os.replace

        def cancel(src, dst):
            if Path(src).name == 'new':
                raise KeyboardInterrupt()
            return replace(src, dst)

        with patch.object(installer.os, 'replace', side_effect=cancel):
            with self.assertRaises(KeyboardInterrupt):
                installer.install(ROOT, self.target, update=True)
        self.assertEqual(before, (dest / 'SKILL.md').read_bytes())
        self.assertEqual(entry, (self.target / 'AGENTS.md').read_bytes())
        installer.install(ROOT, self.target)

    def test_unmanaged_or_symlink_destination_refused(self):
        dest = self.target / '.agents/skills/jstack'
        dest.mkdir(parents=True)
        (dest / 'mine.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'no installation receipt'):
            installer.install(ROOT, self.target)
        shutil.rmtree(dest)
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        dest.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            installer.install(ROOT, self.target)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

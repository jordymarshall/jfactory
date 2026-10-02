import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
        receipt = json.loads((dest / '.jfactory-install.json').read_text())
        self.assertIn('vendor/pstack/LICENSE', receipt['files'])

    def test_installed_instructions_carry_the_spending_rules(self):
        # Every adopting repository's agents get these as standing rules, not only inside the skill.
        block = installer.managed_block('.agents/skills/jfactory')
        self.assertIn('Verify only what changed', block)
        self.assertIn('review the diff and the features it touches, not unrelated areas', block)
        self.assertIn('at most 5 checks per wait', block)
        self.assertIn('the same failure twice means stop and report', block)

    def test_installs_without_git_and_records_unknown_revision(self):
        real = installer.subprocess.check_output

        def no_git(cmd, *args, **kwargs):
            if cmd[0] == 'git':
                raise FileNotFoundError('git')
            return real(cmd, *args, **kwargs)
        with patch.object(installer.subprocess, 'check_output', side_effect=no_git):
            dest = installer.install(ROOT, self.target)
        receipt = json.loads((dest / '.jfactory-install.json').read_text())
        self.assertEqual((receipt['source_commit'], receipt['source_dirty']), (None, None))

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
        before = (dest / '.jfactory-install.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'modified'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(before, (dest / '.jfactory-install.json').read_bytes())

    def test_reviewed_update_removes_old_payload_preserves_surrounding_text(self):
        source = Path(self.tmp.name) / 'source'
        shutil.copytree(ROOT / 'skills', source / 'skills')
        removed = source / 'skills/jfactory/obsolete.txt'
        removed.write_text('old')
        dest = installer.install(source, self.target)
        entry = self.target / 'AGENTS.md'
        entry.write_text(entry.read_text() + '\nOwner addition\n')
        removed.unlink()
        (source / 'skills/jfactory/new.txt').write_text('new')
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

    def test_installed_methods_are_reachable_and_pinned_on_every_host(self):
        for host, (directory, filename) in installer.LAYOUTS.items():
            with self.subTest(host=host):
                target = self.target / host
                target.mkdir()
                # Preserve an existing owner skill outside the managed bundle.
                owner_skill = target / Path(directory).parent / 'show-me/SKILL.md'
                owner_skill.parent.mkdir(parents=True)
                owner_skill.write_text('Owner method')
                dest = installer.install(ROOT, target, host)
                receipt = json.loads((dest / '.jfactory-install.json').read_text())
                for method, source in (('show-me', 'humanlayer'), ('grilling', 'mattpocock')):
                    adapter = dest / f'skills/{method}/SKILL.md'
                    original = dest / f'vendor/{source}/skills/{method}/SKILL.md'
                    self.assertTrue(adapter.is_file())
                    self.assertIn(str(adapter.relative_to(target)), (target / filename).read_text())
                    self.assertIn(f'../../vendor/{source}/skills/{method}/SKILL.md', adapter.read_text())
                    self.assertEqual(original.read_bytes(), (ROOT / 'skills/jfactory' / original.relative_to(dest)).read_bytes())
                    # Loading one routed skill must load the actual method, not
                    # merely a wrapper that an agent can read without its source.
                    method_body = original.read_text().split('---\n', 2)[2].strip()
                    self.assertIn(method_body, adapter.read_text())
                    if method == 'show-me':
                        # Critical workflow guidance precedes the long upstream
                        # examples, so a first-page read cannot hide it.
                        self.assertLess(adapter.read_text().index('# jfactory integration'),
                                        adapter.read_text().index(method_body))
                        # Feedback can establish goals. The routed explanation
                        # skill must load that method without another file hop.
                        grilling = dest / 'vendor/mattpocock/skills/grilling/SKILL.md'
                        self.assertIn(grilling.read_text().split('---\n', 2)[2].strip(), adapter.read_text())
                    self.assertEqual(receipt['files'][str(original.relative_to(dest))], installer.digest(original.read_bytes()))
                    self.assertIn(f'vendor/{source}/LICENSE', receipt['files'])
                subprocess.run([sys.executable, str(dest / 'scripts/check-upstream.py')],
                               check=True, capture_output=True, cwd=target)
                installer.install(ROOT, target, host, update=True)
                self.assertEqual(owner_skill.read_text(), 'Owner method')
                original.write_text('Consumer customization')
                before = installer.payload(target)
                with self.assertRaisesRegex(ValueError, 'modified'):
                    installer.install(ROOT, target, host, update=True)
                self.assertEqual(before, installer.payload(target))

    def test_bundle_gitignore_keeps_bytecode_out_of_the_installing_repository(self):
        git = lambda *args: subprocess.run(['git', '-C', str(self.target), *args], check=True,
                                           capture_output=True, text=True).stdout
        git('init', '-q')
        dest = installer.install(ROOT, self.target)
        receipt = json.loads((dest / '.jfactory-install.json').read_text())
        self.assertIn('.gitignore', receipt['files'])
        self.assertEqual((dest / '.gitignore').read_bytes(), (ROOT / 'skills/jfactory/.gitignore').read_bytes())
        # Running an installed script that imports its neighbours writes bytecode next to them.
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONDONTWRITEBYTECODE'}
        subprocess.run([sys.executable, str(dest / 'scripts/coord.py'), '--help'], check=True, capture_output=True,
                       env=env, cwd=self.target)
        self.assertTrue(list((dest / 'scripts/__pycache__').glob('*.pyc')), 'the script wrote no bytecode')
        status = git('status', '--porcelain', '--untracked-files=all')
        self.assertIn('.agents/skills/jfactory/SKILL.md', status)
        self.assertNotIn('.pyc', status)
        self.assertNotIn('__pycache__', status)
        # Bytecode is not a local edit, so a later reviewed update still goes through.
        installer.install(ROOT, self.target, update=True)

    def test_update_adds_the_bundle_gitignore_to_an_older_installation(self):
        source = Path(self.tmp.name) / 'source'
        shutil.copytree(ROOT / 'skills', source / 'skills')
        (source / 'skills/jfactory/.gitignore').unlink()
        dest = installer.install(source, self.target)
        self.assertFalse((dest / '.gitignore').exists())
        shutil.copy(ROOT / 'skills/jfactory/.gitignore', source / 'skills/jfactory/.gitignore')
        with self.assertRaisesRegex(ValueError, '--update'):
            installer.install(source, self.target)
        installer.install(source, self.target, update=True)
        self.assertTrue((dest / '.gitignore').is_file())
        self.assertIn('.gitignore', json.loads((dest / '.jfactory-install.json').read_text())['files'])

    def test_update_handles_directory_to_file_transition(self):
        source = Path(self.tmp.name) / 'source'
        shutil.copytree(ROOT / 'skills', source / 'skills')
        nested = source / 'skills/jfactory/transition/old.md'
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
        dest = self.target / '.agents/skills/jfactory'
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

    def legacy_install(self, target=None, agent='codex'):
        target = target or self.target
        relative, entry_name = installer.LAYOUTS[agent]
        legacy = (target / relative).with_name('jstack')
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text('---\nname: jstack\n---\nOld workflow\n')
        block = '<!-- jstack:start -->\nUse the old workflow.\n<!-- jstack:end -->'
        receipt = {'schema': 1, 'agent': agent,
                   'files': {'SKILL.md': installer.digest((legacy / 'SKILL.md').read_bytes())},
                   'instruction_block': block}
        (legacy / '.jstack-install.json').write_text(json.dumps(receipt))
        (target / entry_name).write_text('# Owner instructions\n\n' + block + '\n\nKeep this appendix.\n')
        return legacy, target / entry_name

    def test_legacy_upgrade_all_hosts_preserves_owner_text_and_is_idempotent(self):
        for agent, (relative, entry_name) in installer.LAYOUTS.items():
            with self.subTest(agent=agent):
                target = self.target / agent
                legacy, entry = self.legacy_install(target, agent)
                dest = installer.install(ROOT, target, agent, update=True)
                self.assertEqual(dest, target / relative)
                self.assertFalse(legacy.exists())
                self.assertIn('name: jfactory\n', (dest / 'SKILL.md').read_text())
                self.assertTrue((dest / 'skills/jfactory-ux/SKILL.md').is_file())
                self.assertFalse((dest / '.jstack-install.json').exists())
                receipt = json.loads((dest / '.jfactory-install.json').read_text())
                self.assertEqual(receipt['repository'], 'https://github.com/jordymarshall/jfactory')
                self.assertEqual(entry.read_text(), '# Owner instructions\n\n'
                                 + receipt['instruction_block'] + '\n\nKeep this appendix.\n')
                before = installer.payload(target)
                installer.install(ROOT, target, agent, update=True)
                self.assertEqual(before, installer.payload(target))

    def test_legacy_requires_opt_in_and_refuses_local_edits(self):
        legacy, entry = self.legacy_install()
        before = installer.payload(self.target)
        with self.assertRaisesRegex(ValueError, '--update'):
            installer.install(ROOT, self.target)
        self.assertEqual(before, installer.payload(self.target))
        skill = legacy / 'SKILL.md'
        skill.write_text('Owner customized this skill')
        before = installer.payload(self.target)
        with self.assertRaisesRegex(ValueError, 'modified'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(before, installer.payload(self.target))

    def test_legacy_refuses_modified_or_mixed_instruction_blocks(self):
        for edit in ('modified', 'mixed'):
            with self.subTest(edit=edit):
                target = self.target / edit
                legacy, entry = self.legacy_install(target)
                if edit == 'modified':
                    entry.write_text(entry.read_text().replace('old workflow', 'custom workflow'))
                else:
                    entry.write_text(entry.read_text() + '\n<!-- jfactory:start -->\n<!-- jfactory:end -->')
                before = installer.payload(target)
                with self.assertRaises(ValueError):
                    installer.install(ROOT, target, update=True)
                self.assertEqual(before, installer.payload(target))

    def test_legacy_refuses_dual_installation(self):
        self.legacy_install()
        dest = self.target / '.agents/skills/jfactory'
        dest.mkdir()
        (dest / 'mine.txt').write_text('keep')
        before = installer.payload(self.target)
        with self.assertRaisesRegex(ValueError, 'Both'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(before, installer.payload(self.target))

    def test_legacy_symlink_refused(self):
        legacy = self.target / '.agents/skills/jstack'
        legacy.parent.mkdir(parents=True)
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        legacy.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            installer.install(ROOT, self.target, update=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_cancelled_migration_restores_old_path_and_instructions(self):
        legacy, entry = self.legacy_install()
        before = installer.payload(self.target)
        replace = installer.os.replace
        for point in ('new', 'instructions'):
            with self.subTest(point=point):
                def cancel(src, dst):
                    if Path(src).name == point:
                        raise KeyboardInterrupt()
                    return replace(src, dst)
                with patch.object(installer.os, 'replace', side_effect=cancel):
                    with self.assertRaises(KeyboardInterrupt):
                        installer.install(ROOT, self.target, update=True)
                self.assertEqual(before, installer.payload(self.target))
                self.assertTrue(legacy.is_dir())
                self.assertFalse(legacy.with_name('jfactory').exists())


if __name__ == '__main__':
    unittest.main()

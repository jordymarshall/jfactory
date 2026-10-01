import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/jfactory/scripts/evidence.py'


@unittest.skipUnless(os.name == 'posix', 'POSIX capture')
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'Initial')
        self.task = self.root / 'task.json'
        self.task.write_text(json.dumps({'objective': 'Keep saved edits', 'criteria': [
            {'id': 'save', 'expected': 'Saved edits survive reload', 'required_scopes': ['application']}]}))

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root, capture_output=True, text=True)

    def capture(self, scope='application', code='print("observed")', timeout='10'):
        return self.invoke('run', '--task', str(self.task), '--criterion', 'save', '--scope', scope,
                           '--environment', 'disposable', '--timeout', timeout, '--', sys.executable, '-c', code)

    def check(self):
        return self.invoke('check', '--task', str(self.task))

    def test_success_and_scope_boundary(self):
        self.assertNotEqual(self.check().returncode, 0)
        self.assertEqual(self.capture(scope='component').returncode, 0)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['gaps'][0]['scope'], 'application')
        self.assertEqual(self.capture().returncode, 0)
        self.assertEqual(self.check().returncode, 0)

    def test_judgment_needs_rubric_independent_judge_and_inspected_artifacts(self):
        self.task.write_text(json.dumps({'objective': 'Clear saving', 'criteria': [
            {'id': 'clear', 'expected': 'Saving is obvious', 'required_scopes': ['judgment']}]}))
        self.assertIn('needs a judgment rubric', self.check().stderr)
        self.task.write_text(json.dumps({'objective': 'Clear saving', 'criteria': [
            {'id': 'clear', 'expected': 'Saving is obvious', 'required_scopes': ['judgment'],
             'rubric': '1 visible without scrolling; 2 at most two actions'}]}))
        command = self.invoke('run', '--task', str(self.task), '--criterion', 'clear', '--scope', 'judgment',
                              '--environment', 'x', '--', 'true')
        self.assertIn('A command cannot prove a judgment', command.stderr)
        shot = self.root / 'shot.png'
        shot.write_bytes(b'png')

        def judge(judge='codex/gpt-6-luna', result='pass', inspected='shot.png'):
            return self.invoke('judge', '--task', str(self.task), '--criterion', 'clear', '--judge', judge,
                               '--implementer', 'claude/opus-5-5-1m', '--result', result, '--scores', '1 yes; 2 yes',
                               '--inspected', inspected)
        self.assertIn('must be independent', judge(judge='claude/sonnet-5-1m').stderr)
        self.assertIn('is not a file', judge(inspected='missing.png').stderr)
        self.assertNotEqual(judge(result='fail').returncode, 0)
        self.assertNotEqual(self.check().returncode, 0)
        self.assertEqual(judge().returncode, 0, judge().stderr)
        self.assertEqual(self.check().returncode, 0, self.check().stdout)

    def test_new_failure_does_not_reuse_old_success(self):
        self.assertEqual(self.capture().returncode, 0)
        self.assertNotEqual(self.capture(code='raise SystemExit(7)').returncode, 0)
        self.assertNotEqual(self.check().returncode, 0)

    def test_changed_source_and_task_invalidate_proof(self):
        self.assertEqual(self.capture().returncode, 0)
        (self.root / 'app.py').write_text('changed')
        self.assertIn('stale', self.check().stdout)
        self.assertEqual(self.capture().returncode, 0)
        self.task.write_text(self.task.read_text() + '\n')
        self.assertIn('stale', self.check().stdout)

    def test_modified_log_is_rejected(self):
        self.assertEqual(self.capture().returncode, 0)
        log = next((self.root / '.context/jfactory').glob('*/output.log'))
        log.write_text('different output')
        self.assertIn('changed output', self.check().stdout)

    def test_command_changing_source_is_not_a_pass(self):
        result = self.capture(code='from pathlib import Path; Path("app.py").write_text("new")')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source-changed', result.stdout)

    def test_launch_failure_and_timeout_preserve_evidence(self):
        failed = self.invoke('run', '--task', str(self.task), '--criterion', 'save', '--scope', 'application',
                             '--environment', 'disposable', '--', '/nonexistent-jfactory-command')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('launch-failed', failed.stdout)
        result = self.capture(code='import time; print("started", flush=True); time.sleep(30)', timeout='0.1')
        self.assertEqual(result.returncode, 124)
        self.assertIn('timeout', result.stdout)
        self.assertNotEqual(self.check().returncode, 0)
        self.assertEqual(len(list((self.root / '.context/jfactory').glob('*/receipt.json'))), 2)

    def test_cancellation_preserves_receipt_and_kills_owned_child(self):
        self.assertEqual(self.capture().returncode, 0)
        marker = self.root / '.context/jfactory/child.pid'
        code = f'import os,time; from pathlib import Path; Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(30)'
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'run', '--task', str(self.task),
            '--criterion', 'save', '--scope', 'application', '--environment', 'disposable', '--',
            sys.executable, '-c', code], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            self.assertNotEqual(self.check().returncode, 0, 'Pending rerun must not reuse older success')
            child = int(marker.read_text())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 143, stderr)
            self.assertIn('interrupted', stdout)
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
            self.assertNotEqual(self.check().returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


    def regression_fixture(self, base_total='16.2', head_total='18.0'):
        """A committed bug at the base, its fix in the working tree, and a new untracked regression test."""
        (self.root / '.gitignore').write_text('__pycache__/\n')
        (self.root / 'cart.py').write_text(f'def total():\n    return {base_total}\n')
        self.git('add', 'cart.py', '.gitignore')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'Cart')
        self.base = self.git('rev-parse', 'HEAD').stdout.decode().strip()
        (self.root / 'cart.py').write_text(f'def total():\n    return {head_total}\n')
        (self.root / 'test_cart.py').write_text(
            'import cart\nassert cart.total() == 18.0, f"total is {cart.total()}, expected 18.0"\n')
        self.task.write_text(json.dumps({'objective': 'Discount once', 'criteria': [
            {'id': 'save', 'expected': 'The coupon applies once', 'required_scopes': ['unit'], 'regression': True}]}))

    def contrast(self, *extra, expect='total is 16.2'):
        return self.invoke('contrast', '--task', str(self.task), '--criterion', 'save', '--scope', 'unit',
                           '--environment', 'disposable', '--base', self.base, '--expect-failure', expect,
                           *extra, '--', sys.executable, 'test_cart.py')

    def test_contrast_proves_a_fix_fails_on_the_base_and_passes_on_the_tree(self):
        self.regression_fixture()
        self.assertEqual(self.invoke('run', '--task', str(self.task), '--criterion', 'save', '--scope', 'unit',
                                     '--environment', 'disposable', '--', sys.executable, 'test_cart.py').returncode, 0)
        gaps = json.loads(self.check().stdout)['gaps']
        self.assertEqual(gaps, [{'criterion': 'save', 'scope': 'contrast', 'reason': 'missing'}],
                         'A passing check alone must not prove a regression fix')
        result = self.contrast('--keep', 'test_cart.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        receipt = json.loads(result.stdout)
        self.assertEqual((receipt['base'], receipt['base_matched']), ('failed', True))
        self.assertEqual(self.git('worktree', 'list').stdout.decode().count('\n'), 1, 'The base worktree is removed')
        (self.root / 'cart.py').write_text('def total():\n    return 18\n')
        self.assertIn('stale', self.check().stdout)

    def test_contrast_refuses_a_base_that_fails_for_another_reason(self):
        self.regression_fixture()
        # Without --keep the base has no regression test, so it fails with a missing file, not the bug.
        result = self.contrast()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['base_matched'], False)
        self.assertIn('base-failed-differently', self.check().stdout)

    def test_contrast_refuses_a_bug_that_does_not_reproduce_or_a_fix_that_fails(self):
        self.regression_fixture(base_total='18.0')
        self.assertIn('"base-passed"', self.contrast('--keep', 'test_cart.py').stdout + self.check().stdout)
        self.assertNotEqual(self.check().returncode, 0)
        self.tmp.cleanup()
        self.setUp()
        self.regression_fixture(head_total='16.2')
        result = self.contrast('--keep', 'test_cart.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')
        self.assertNotEqual(self.check().returncode, 0)

    def test_contrast_rejects_paths_outside_the_repository_and_bad_patterns(self):
        self.regression_fixture()
        self.assertIn('inside the repository', self.contrast('--keep', '../elsewhere').stderr)
        self.assertIn('not a valid regular expression', self.contrast('--keep', 'test_cart.py', expect='(').stderr)
        self.task.write_text(json.dumps({'objective': 'x', 'criteria': [
            {'id': 'save', 'expected': 'y', 'required_scopes': ['unit'], 'regression': 'yes'}]}))
        self.assertIn('must be true or false', self.check().stderr)


if __name__ == '__main__':
    unittest.main()

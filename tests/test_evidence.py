import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/jstack/scripts/evidence.py'


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
        log = next((self.root / '.context/jstack').glob('*/output.log'))
        log.write_text('different output')
        self.assertIn('changed output', self.check().stdout)

    def test_command_changing_source_is_not_a_pass(self):
        result = self.capture(code='from pathlib import Path; Path("app.py").write_text("new")')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source-changed', result.stdout)

    def test_launch_failure_and_timeout_preserve_evidence(self):
        failed = self.invoke('run', '--task', str(self.task), '--criterion', 'save', '--scope', 'application',
                             '--environment', 'disposable', '--', '/nonexistent-jstack-command')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('launch-failed', failed.stdout)
        result = self.capture(code='import time; print("started", flush=True); time.sleep(30)', timeout='0.1')
        self.assertEqual(result.returncode, 124)
        self.assertIn('timeout', result.stdout)
        self.assertNotEqual(self.check().returncode, 0)
        self.assertEqual(len(list((self.root / '.context/jstack').glob('*/receipt.json'))), 2)

    def test_cancellation_preserves_receipt_and_kills_owned_child(self):
        self.assertEqual(self.capture().returncode, 0)
        marker = self.root / '.context/jstack/child.pid'
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


if __name__ == '__main__':
    unittest.main()

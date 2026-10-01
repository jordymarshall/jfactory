import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/jfactory/scripts/feedback.py'
spec = importlib.util.spec_from_file_location('feedback', SCRIPT)
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)
REPO = 'https://github.com/jordymarshall/jfactory'


class FeedbackTests(unittest.TestCase):
    def test_redaction_removes_secrets_private_urls_people_and_project_names(self):
        environ = {'STRIPE_SECRET_KEY': 'rk_live_abcdef123456', 'HOME': '/home/someone', 'PATH': '/usr/bin'}
        text = ('Using rk_live_abcdef123456 and ghp_' + 'a' * 36 + ' with Bearer abcdefghijklmnop12 at '
                'https://acme-internal.example.com/admin?id=7 (see https://github.com/jordymarshall/jfactory/issues/3) '
                'for ada@acme.io in /home/ada/acme-portal; acme/acme-portal broke, but the app still runs')
        out = feedback.redact(text, REPO, environ, {'acme/acme-portal', 'acme-portal'})
        for private in ('rk_live', 'ghp_', 'abcdefghijklmnop12', 'acme-internal', 'ada@acme.io', '/home/ada',
                        'acme-portal'):
            self.assertNotIn(private, out)
        self.assertIn('<STRIPE_SECRET_KEY>', out)
        self.assertIn('https://github.com/jordymarshall/jfactory/issues/3', out, 'Links to jfactory itself stay')
        self.assertIn('the app still runs', out, 'Ordinary words are not project names')

    def test_dry_run_prints_the_issue_and_sends_nothing(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--type', 'docs', '-m', 'mapping.md step 7 names a '
                                 'flag that smoke does not accept', '--command', 'verify_plan.py smoke --fresh'],
                                capture_output=True, text=True, env={**os.environ, 'PATH': '/nonexistent'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Would open an issue in jordymarshall/jfactory', result.stdout)
        self.assertIn('# [feedback:docs] mapping.md step 7', result.stdout)
        self.assertIn('Nothing was sent', result.stdout)

    def test_a_vague_message_is_refused(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--type', 'bug', '-m', 'broken'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('one or two sentences', result.stderr)

    def test_send_comments_on_an_open_report_with_the_same_title_or_opens_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            log, gh = Path(tmp) / 'calls.jsonl', Path(tmp) / 'gh'
            gh.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                          f'open({str(log)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")\n'
                          'if sys.argv[1:3] == ["issue", "list"]: print(os.environ.get("EXISTING", "[]"))\n'
                          'elif sys.argv[1:3] == ["issue", "create"]: print("https://github.com/jordymarshall/jfactory/issues/9")\n')
            gh.chmod(0o755)
            env = {**os.environ, 'PATH': f'{tmp}:{os.environ["PATH"]}'}
            args = [sys.executable, str(SCRIPT), '--type', 'bug', '-m', 'smoke crashes when a target has no ready URL',
                    '--send']
            made = subprocess.run(args, capture_output=True, text=True, env=env)
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertIn('issues/9', made.stdout)
            title = '[feedback:bug] smoke crashes when a target has no ready URL'
            existing = json.dumps([{'number': 4, 'title': title, 'url': 'https://github.com/jordymarshall/jfactory/issues/4'}])
            again = subprocess.run(args, capture_output=True, text=True, env={**env, 'EXISTING': existing})
            self.assertIn('issues/4 (added to the existing report)', again.stdout)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([c[:2] for c in calls], [['issue', 'list'], ['issue', 'create'], ['issue', 'list'],
                                                      ['issue', 'comment']])
            self.assertTrue(all('jordymarshall/jfactory' in c for c in calls))


if __name__ == '__main__':
    unittest.main()

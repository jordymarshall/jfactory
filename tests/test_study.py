import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/jfactory/skills/jfactory-ux/scripts/study.py'
spec = importlib.util.spec_from_file_location('study', SCRIPT)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = study.init(self.root, 'example', 'https://example.com', 'Study <items>')

    def report(self, evidence='artifacts/item.png'):
        (self.folder / 'artifacts/item.png').write_bytes(b'test fixture')
        value = {'summary': '<script>alert(1)</script>', 'context': 'Local demo',
                 'app_map': 'List -> detail', 'journeys': [{
                     'name': 'Open item', 'status': 'observed', 'steps': [{
                         'action': 'Click item', 'observed': 'Detail visible', 'evidence': [evidence]}]}],
                 'findings': [], 'unknowns': ['No customer study']}
        study.write_json(self.folder / 'report.json', value)

    def fake_browser(self, calls, fail_screenshot=False):
        def run(folder, args):
            calls.append(args)
            if args[0] == 'screenshot':
                if fail_screenshot:
                    return 1
                (folder / args[1].split('=', 1)[1]).write_bytes(b'png')
            return 0
        return run

    def test_every_step_captures_what_the_user_now_sees(self):
        calls = []
        run = self.fake_browser(calls)
        self.assertEqual(study.step(self.folder, ['open', 'https://example.com'], run), (1, 'artifacts/steps/001.png'))
        study.step(self.folder, ['click', "getByRole('button', { name: 'Load more' })"], run)
        self.assertEqual([c[0] for c in calls], ['open', 'screenshot', 'click', 'screenshot'])
        steps = json.loads((self.folder / 'steps.json').read_text())
        self.assertEqual([s['screenshot'] for s in steps], ['artifacts/steps/001.png', 'artifacts/steps/002.png'])
        self.assertTrue(all((self.folder / s['screenshot']).is_file() for s in steps))
        # The trail refuses to render until someone looked at, and described, every step.
        with self.assertRaisesRegex(ValueError, 'no note for step\\(s\\) 1, 2'):
            study.walkthrough(self.folder)
        study.note(self.folder, 1, 'Briefs list, 40 rows, header readable')
        with self.assertRaisesRegex(ValueError, 'no note for step\\(s\\) 2'):
            study.walkthrough(self.folder)
        with self.assertRaisesRegex(ValueError, 'says what the screenshot shows'):
            study.note(self.folder, 2, '   ')
        study.note(self.folder, 2, '80 rows; <b>focus</b> on brief 041')
        html = study.walkthrough(self.folder).read_text()
        self.assertIn('&lt;b&gt;focus&lt;/b&gt;', html)
        self.assertIn('artifacts/steps/002.png', html)
        self.assertIn('2. **click', (self.folder / 'steps.md').read_text())

    def test_step_refuses_non_actions_and_a_missing_screenshot(self):
        with self.assertRaisesRegex(ValueError, 'one user action'):
            study.step(self.folder, ['screenshot'], self.fake_browser([]))
        with self.assertRaisesRegex(ValueError, 'No steps recorded'):
            study.walkthrough(self.folder)
        # A failed capture still records the action, and the trail refuses to render around it.
        study.step(self.folder, ['open', 'https://example.com'], self.fake_browser([]))
        with self.assertRaisesRegex(ValueError, 'screenshot was not captured'):
            study.step(self.folder, ['click', 'Open item'], self.fake_browser([], fail_screenshot=True))
        study.step(self.folder, ['click', 'Save item'], self.fake_browser([]))
        steps = json.loads((self.folder / 'steps.json').read_text())
        self.assertEqual([s['action'] for s in steps], ['open https://example.com', 'click Open item', 'click Save item'])
        for n in (1, 2, 3):
            study.note(self.folder, n, 'seen')
        with self.assertRaisesRegex(ValueError, 'Step\\(s\\) 2 have no screenshot'):
            study.walkthrough(self.folder)

    def test_trail_validates_what_it_renders(self):
        study.step(self.folder, ['open', 'https://example.com'], self.fake_browser([]))
        steps = json.loads((self.folder / 'steps.json').read_text())
        steps[0]['note'] = '   '
        study.write_json(self.folder / 'steps.json', steps)
        with self.assertRaisesRegex(ValueError, 'no note for step\\(s\\) 1'):
            study.walkthrough(self.folder)
        steps[0].update(note='seen', screenshot='study.json')
        study.write_json(self.folder / 'steps.json', steps)
        with self.assertRaisesRegex(ValueError, 'no screenshot inside artifacts/steps'):
            study.walkthrough(self.folder)
        (self.folder / 'artifacts' / 'steps').rename(self.folder / 'moved')
        (self.folder / 'artifacts' / 'steps').symlink_to(self.folder / 'moved')
        with self.assertRaisesRegex(ValueError, 'must not be symlinks'):
            study.step(self.folder, ['click', 'x'], self.fake_browser([]))

    def test_step_never_writes_through_a_planted_capture_link(self):
        sentinel = self.root / 'outside.txt'
        sentinel.write_text('keep me')
        (self.folder / 'artifacts' / 'steps').mkdir()
        leaf = self.folder / 'artifacts/steps/001.png'
        leaf.symlink_to(sentinel)
        calls = []
        with self.assertRaisesRegex(ValueError, 'not a link'):
            study.step(self.folder, ['open', 'https://example.com'], self.fake_browser(calls))
        self.assertEqual(calls, [])
        self.assertFalse((self.folder / 'steps.json').exists())
        leaf.unlink()
        leaf.mkdir()
        with self.assertRaisesRegex(ValueError, 'not a link'):
            study.step(self.folder, ['open', 'https://example.com'], self.fake_browser(calls))
        self.assertEqual(calls, [])
        leaf.rmdir()
        # A link planted while the action runs is replaced, not written through.
        capture = self.fake_browser(calls)

        def plant(folder, args):
            if args[0] == 'click':
                leaf.symlink_to(sentinel)
            return capture(folder, args)
        study.step(self.folder, ['click', 'Open item'], plant)
        self.assertEqual(sentinel.read_text(), 'keep me')
        self.assertFalse(leaf.is_symlink())
        self.assertEqual(leaf.read_bytes(), b'png')
        self.assertEqual(sorted(p.name for p in leaf.parent.iterdir()), ['001.png'])

    def test_trail_refuses_redirected_capture_directories(self):
        study.step(self.folder, ['open', 'https://example.com'], self.fake_browser([]))
        study.note(self.folder, 1, 'seen')
        study.walkthrough(self.folder)
        for moved in ('artifacts/steps', 'artifacts'):
            with self.subTest(moved=moved):
                outside = self.root / ('outside-' + moved.replace('/', '-'))
                (self.folder / moved).rename(outside)
                (self.folder / moved).symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'must not be symlinks'):
                    study.walkthrough(self.folder)
                (self.folder / moved).unlink()
                outside.rename(self.folder / moved)
        # A path that passes through a link below the study is refused too.
        (self.folder / 'artifacts/steps/sub').symlink_to(self.root, target_is_directory=True)
        (self.root / '001.png').write_bytes(b'png')
        steps = json.loads((self.folder / 'steps.json').read_text())
        steps[0]['screenshot'] = 'artifacts/steps/sub/001.png'
        study.write_json(self.folder / 'steps.json', steps)
        with self.assertRaisesRegex(ValueError, 'Step\\(s\\) 1 have no screenshot'):
            study.walkthrough(self.folder)

    def test_serve_prints_the_page_the_study_has(self):
        self.assertEqual(study.review_urls(self.folder, 8000), ['http://127.0.0.1:8000/walkthrough.html'])
        study.step(self.folder, ['open', 'https://example.com'], self.fake_browser([]))
        self.assertEqual(study.review_urls(self.folder, 8000), ['http://127.0.0.1:8000/steps.html'])
        study.note(self.folder, 1, 'seen')
        study.walkthrough(self.folder)
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'serve', str(self.folder)],
                                   stdout=subprocess.PIPE, text=True)
        try:
            url = process.stdout.readline().strip()
            self.assertTrue(url.endswith('/steps.html'), url)
            with urlopen(url) as response:
                self.assertEqual(response.status, 200)
        finally:
            process.terminate()
            process.wait()
            process.stdout.close()
        self.report()
        study.render(self.folder)
        self.assertEqual(study.review_urls(self.folder, 8000),
                         ['http://127.0.0.1:8000/steps.html', 'http://127.0.0.1:8000/walkthrough.html'])
        (self.folder / 'steps.html').unlink()
        self.assertEqual(study.review_urls(self.folder, 8000), ['http://127.0.0.1:8000/walkthrough.html'])

    def test_private_distinct_sessions_and_no_overwrite(self):
        second = study.init(self.root, 'other', 'https://example.com', 'Other study')
        first_id = json.loads((self.folder / 'study.json').read_text())['session']
        second_id = json.loads((second / 'study.json').read_text())['session']
        self.assertNotEqual(first_id, second_id)
        self.assertEqual((self.folder.parent / '.gitignore').read_text(), '*\n')
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(FileExistsError):
            study.init(self.root, 'example', 'https://example.com', 'Replace')
        self.assertEqual(json.loads((self.folder / 'study.json').read_text())['session'], first_id)

    def test_rejects_path_traversal_and_credentials(self):
        for name, url in [('../outside', 'https://example.com'), ('other', 'file:///etc/passwd'),
                          ('other', 'https://user:password@example.com')]:
            with self.assertRaises(ValueError):
                study.init(self.root, name, url, 'Test')
        linked = self.root / '.context/ux/linked'
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            study.init(self.root, 'linked', 'https://example.com', 'Test')

    def test_renders_escaped_text_and_real_artifact_link(self):
        self.report()
        html = study.render(self.folder).read_text()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('src="artifacts/item.png"', html)
        self.assertIn('No customer study', html)

    def test_rejects_missing_external_and_active_evidence(self):
        (self.root / 'secret.txt').write_text('secret')
        (self.folder / 'artifacts/linked.txt').symlink_to(self.root / 'secret.txt')
        (self.folder / 'artifacts/active.html').write_text('<script>bad()</script>')
        for evidence in ('artifacts/missing.png', '../../secret.txt', 'artifacts/linked.txt', 'artifacts/active.html'):
            self.report(evidence)
            with self.assertRaises(ValueError):
                study.render(self.folder)

    def test_incomplete_research_cannot_render_as_complete(self):
        with self.assertRaises(ValueError):
            study.render(self.folder)
        self.report()
        record = json.loads((self.folder / 'report.json').read_text())
        record['journeys'][0]['steps'] = []
        study.write_json(self.folder / 'report.json', record)
        with self.assertRaisesRegex(ValueError, 'action evidence'):
            study.render(self.folder)
        record['journeys'][0].update(status='blocked', gaps='Login unavailable')
        study.write_json(self.folder / 'report.json', record)
        self.assertIn('Login unavailable', study.render(self.folder).read_text())

    def test_refuses_global_cleanup_or_session_takeover(self):
        for args in (['close-all'], ['kill-all'], ['attach'], ['-s=other', 'close'],
                     ['open', '--profile=/tmp/other'], ['open', '--config=other.json']):
            with self.assertRaises(ValueError):
                study.browser(self.folder, args)

    def test_review_server_serves_the_step_trail(self):
        study.step(self.folder, ['open', 'https://example.com'], self.fake_browser([]))
        study.note(self.folder, 1, 'Landing page, readable')
        study.walkthrough(self.folder)
        server = study.review_server(self.folder)
        Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for path, text in (('/steps.html', b'Landing page, readable'), ('/steps.md', b'Landing page, readable'),
                               ('/artifacts/steps/001.png', b'png')):
                with urlopen(base + path) as response:
                    self.assertIn(text, response.read())
        finally:
            server.shutdown()
            server.server_close()

    def test_review_server_serves_evidence_but_not_profile_or_traversal(self):
        self.report()
        study.render(self.folder)
        (self.folder / 'profile').mkdir()
        secret = self.folder / 'profile/token.txt'
        secret.write_text('private session')
        (self.folder / 'artifacts/leak.txt').symlink_to(secret)
        server = study.review_server(self.folder)
        Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/walkthrough.html') as response:
                self.assertIn(b'Detail visible', response.read())
                self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
            with urlopen(base + '/artifacts/item.png') as response:
                self.assertEqual(response.read(), b'test fixture')
            for requested, expected in [('bytes=2-5', b'st f'), ('bytes=-3', b'ure')]:
                with urlopen(Request(base + '/artifacts/item.png', headers={'Range': requested})) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), expected)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + '/artifacts/item.png', headers={'Range': 'bytes=99-'}))
            self.assertEqual(error.exception.code, 416)
            for path in ('/profile/token.txt', '/study.json', '/artifacts/',
                         '/artifacts/../profile/token.txt', '/artifacts/%2e%2e/profile/token.txt', '/artifacts/leak.txt'):
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    urlopen(base + path)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()

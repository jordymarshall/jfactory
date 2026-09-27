#!/usr/bin/env python3
"""Run with `python3 tests/browser_smoke.py`. Requires Node/npm and Chrome.

Drives a disposable local app through the installed CLI, retains success evidence
under .context/ux/smoke-<id>, and fails on missing state, motion or captures.
"""
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/skills/jfactory-ux/scripts/study.py'
spec = importlib.util.spec_from_file_location('study', SCRIPT)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)

HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Fieldnotes demo</title>
<style>
body{font:18px/1.5 system-ui;background:#f4f2fa;color:#252038;margin:0;padding:60px}
main{max-width:1100px;margin:auto}small{color:#6c598f}h1{font-size:44px;margin:14px 0}
button{font:inherit;border:0;border-radius:10px;padding:14px 22px;background:#6540bf;color:white;cursor:pointer}
article{background:white;padding:32px;border-radius:18px;border:1px solid #ddd5ef;margin-top:32px}
aside{margin-top:24px;background:#eae3fa;border-radius:14px;padding:24px}#saved{font-weight:600;color:#46337b}
</style><main><small>FIELDNOTES / LOCAL BROWSER TEST</small><h1>A place for useful ideas</h1>
<p>This disposable demo exercises the jfactory browser workflow. It is not competitor research.</p>
<article><h2>Research collection</h2><p>Open an item, save it, then reload to check the result.</p>
<button id="open">Open item</button><aside id="panel" hidden><h2>Keeping context while exploring</h2>
<p>The detail panel opens alongside the collection. The save action persists across reloads.</p>
<button id="save">Save item</button><p id="saved" role="status"></p></aside></article></main>
<script>
const panel=document.querySelector('#panel');
function readback(){document.querySelector('#saved').textContent=localStorage.getItem('saved')==='yes'?'Saved to collection':'';}
document.querySelector('#open').onclick=()=>{panel.hidden=false;panel.animate([{transform:'translateX(90px)',opacity:0},{transform:'translateX(0)',opacity:1}],{duration:1200,easing:'ease-out'});readback();};
document.querySelector('#save').onclick=()=>{localStorage.setItem('saved','yes');readback();};
</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML.encode())

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    folder = study.init(ROOT, 'smoke-' + uuid.uuid4().hex[:8], url, 'Save an item and return to it')

    def cli(*args):
        result = subprocess.run([sys.executable, str(SCRIPT), 'browser', str(folder), *args],
                                capture_output=True, text=True, timeout=90)
        output = result.stdout + result.stderr
        if result.returncode or '### Error' in output or '### TimeoutError' in output:
            raise AssertionError(output)
        return output

    try:
        cli('open', url)
        cli('video-start', 'artifacts/journey.webm', '--size=1440x900', '--fps=30')
        cli('tracing-start')
        cli('screenshot', '--filename=artifacts/before.png')
        output = cli('run-code', '''async page => {
          await page.getByRole('button', {name:'Open item', exact:true}).click();
          const animations = await page.evaluate(() => document.getAnimations().map(a => a.effect.getComputedTiming().duration));
          if (!animations.includes(1200)) throw new Error('No 1200ms transition observed');
          await page.getByRole('button', {name:'Save item', exact:true}).click();
          await page.reload();
          await page.getByRole('button', {name:'Open item', exact:true}).click();
          if (await page.getByRole('status').textContent() !== 'Saved to collection') throw new Error('Readback failed');
          await page.evaluate(() => Promise.all(document.getAnimations().map(a => a.finished)));
          console.log('MOTION_AND_READBACK_VERIFIED');
        }''')
        assert 'MOTION_AND_READBACK_VERIFIED' in output, output
        cli('screenshot', '--filename=artifacts/after.png')
        cli('video-stop')
        cli('tracing-stop')
        cli('close')
        # The helper's dedicated persistent profile survives closing the browser.
        cli('open', url)
        output = cli('run-code', '''async page => {
          await page.getByRole('button', {name:'Open item', exact:true}).click();
          if (await page.getByRole('status').textContent() !== 'Saved to collection') throw new Error('Profile lost saved state');
          console.log('PROFILE_REOPEN_VERIFIED');
        }''')
        assert 'PROFILE_REOPEN_VERIFIED' in output, output
        for name in ('before.png', 'after.png', 'journey.webm'):
            assert (folder / 'artifacts' / name).stat().st_size > 1000, name
        traces = list((folder / 'artifacts').rglob('*.trace'))
        assert traces, 'Missing trace'
        events = [json.loads(line) for line in traces[0].read_text().splitlines()]
        assert any(event.get('type') == 'before' for event in events), 'Missing trace actions'
        assert list(traces[0].parent.glob('*.network')), 'Missing trace network log'
        assert list((traces[0].parent / 'resources').iterdir()), 'Missing trace resources'
        study.write_json(folder / 'report.json', {
            'summary': 'The real browser opened a panel, observed its animation, saved an item and verified readback after reload and browser restart.',
            'context': 'Linux / Chrome / disposable local demo / 1440 × 900. No competitor account or customer usability study.',
            'app_map': 'Collection → item detail → save → reload → reopen. One item uses browser localStorage. The dedicated study profile retains it after browser restart.',
            'journeys': [{'name': 'Open, save and return', 'status': 'observed', 'steps': [
                {'action': 'Open the collection', 'observed': 'The item has an Open item control.', 'evidence': ['artifacts/before.png']},
                {'action': 'Open the item, save, reload and reopen', 'observed': 'The panel animates for 1200ms. Saved to collection remains visible after reload and session restart.',
                 'evidence': ['artifacts/after.png', 'artifacts/journey.webm', traces[0].relative_to(folder).as_posix()]}],
                'gaps': 'This fixture has no server persistence, real login, mobile design or error handling.'}],
            'findings': [{'observed': 'The list stays on screen while the detail panel appears.',
                          'inferred': 'Keeping context may help when comparing items.',
                          'recommendation': 'Evaluate this pattern against the real customer task; the demo does not establish usability.',
                          'evidence': ['artifacts/journey.webm']}],
            'unknowns': ['Authenticated competitor access has not been tested.', 'No smoothness or reduced-motion measurements.'],
        })
        walkthrough = study.render(folder)
        review = study.review_server(folder)
        Thread(target=review.serve_forever, daemon=True).start()
        try:
            cli('goto', f'http://127.0.0.1:{review.server_port}/walkthrough.html')
            output = cli('run-code', '''async page => {
          if (await page.locator('img').count() !== 2) throw new Error('Missing walkthrough images');
          await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0));
          if (await page.locator('video').count() !== 2) throw new Error('Missing walkthrough clips');
          await page.locator('video').first().evaluate(v => v.load());
          await page.waitForFunction(() => {
            const v = document.querySelector('video');
            return v.readyState >= 2 && v.videoWidth > 0 && v.duration > 0;
          });
          await page.locator('video').first().evaluate(v => new Promise(resolve => {
            v.onseeked = resolve;
            v.currentTime = v.duration / 2;
          }));
          if (!await page.locator('video').first().evaluate(v => v.currentTime >= v.duration * 0.4)) throw new Error('Video cannot seek');
          console.log('WALKTHROUGH_VERIFIED');
            }''')
            assert 'WALKTHROUGH_VERIFIED' in output, output
            cli('screenshot', '--filename=artifacts/walkthrough.png')
        finally:
            review.shutdown()
            review.server_close()
        print('Browser smoke passed. Review:', walkthrough)
    finally:
        try:
            cli('close')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()

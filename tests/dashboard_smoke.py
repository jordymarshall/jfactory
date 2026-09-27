#!/usr/bin/env python3
"""Prove a second browser can control one isolated study through the dashboard.

Uses a disposable local page; does not test Conductor SSO or real app login.
Requires the same Node/npm/Chrome prerequisites as browser_smoke.py.
"""
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from threading import Thread
import time
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/skills/jfactory-ux/scripts/study.py'
spec = importlib.util.spec_from_file_location('study', SCRIPT)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)

HTML = b'''<!doctype html><title>Cloud handoff fixture</title>
<style>body{font:22px system-ui;padding:60px;background:#f5f3ff}input,button{font:inherit;padding:12px}</style>
<h1>Cloud handoff fixture</h1><label>Demo name <input></label><button>Continue</button><p role="status"></p>
<script>
const status=document.querySelector('[role=status]');
function read(){status.textContent=localStorage.getItem('name')?'Welcome, '+localStorage.getItem('name'):'';}
document.querySelector('button').onclick=()=>{localStorage.setItem('name',document.querySelector('input').value);read();};read();
</script>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *args):
        pass


def cli(folder, *args):
    process = subprocess.run([sys.executable, str(SCRIPT), 'browser', str(folder), *args],
                             capture_output=True, text=True, timeout=60)
    output = process.stdout + process.stderr
    if process.returncode or '### Error' in output:
        raise AssertionError(output)
    return output


def evaluate(folder, code):
    output = cli(folder, 'run-code', code)
    # Parse the returned value, never the generated code printed after it.
    return json.loads(output.split('### Result\n', 1)[1].split('\n###', 1)[0].strip())


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    target = study.init(ROOT, 'handoff-' + uuid.uuid4().hex[:8], url, 'Test dashboard handoff')
    viewer = study.init(ROOT, 'viewer-' + uuid.uuid4().hex[:8], url, 'Operate dashboard as a human would')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    dashboard = None
    try:
        cli(target, 'open', url)
        controls = evaluate(target, '''async page => ({
          input: await page.getByRole('textbox').boundingBox(),
          button: await page.getByRole('button', {name:'Continue', exact:true}).boundingBox()
        })''')
        with (target / 'dashboard.log').open('w') as log:
            dashboard = subprocess.Popen([sys.executable, str(SCRIPT), 'dashboard', str(target), '--port', str(port)],
                                         stdout=log, stderr=log, start_new_session=True)
        dashboard_url = f'http://127.0.0.1:{port}'
        for attempt in range(100):
            if dashboard.poll() is not None:
                raise AssertionError((target / 'dashboard.log').read_text())
            try:
                with urlopen(dashboard_url, timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError('Dashboard did not start')
        cli(viewer, 'open', dashboard_url)
        session = json.loads((target / 'study.json').read_text())['session']
        operator = '''async page => {
          await page.getByRole('option').filter({hasText:'Cloud handoff fixture'}).click();
          const screen = page.getByRole('img', {name:'screencast'});
          await screen.waitFor({state:'visible'});
          const sessions = await page.getByRole('region', {name:/^Session /}).allTextContents();
          await page.getByRole('button', {name:'Enable interactive mode', exact:true}).click();
          const box = await screen.boundingBox();
          const controls = CONTROLS;
          const point = r => ({x:(r.x+r.width/2)*box.width/1440, y:(r.y+r.height/2)*box.height/900});
          await screen.click({position:point(controls.input)});
          return sessions;
        }'''.replace('CONTROLS', json.dumps(controls))
        sessions = evaluate(viewer, operator)
        assert len(sessions) == 1 and session in sessions[0], sessions
        # The dashboard forwards input asynchronously over its browser bridge.
        # Observe focus before typing instead of racing the first key against it.
        evaluate(target, "async page => {await page.waitForFunction(() => document.activeElement?.tagName === 'INPUT'); return true;}")
        evaluate(viewer, '''async page => {
          await page.keyboard.type('cloud-probe', {delay:30});
          return true;
        }''')
        evaluate(target, "async page => {await page.waitForFunction(() => document.querySelector('input').value === 'cloud-probe'); return true;}")
        evaluate(viewer, '''async page => {
          const screen=page.getByRole('img', {name:'screencast'});
          const box=await screen.boundingBox();
          const r=BUTTON;
          await screen.click({position:{x:(r.x+r.width/2)*box.width/1440,y:(r.y+r.height/2)*box.height/900}});
          await page.keyboard.press('Escape');
          return true;
        }'''.replace('BUTTON', json.dumps(controls['button'])))
        evaluate(target, "async page => {await page.waitForFunction(() => document.querySelector('[role=status]').textContent !== ''); return true;}")
        # Independent readback through the study browser, after dashboard input.
        readback = evaluate(target, "async page => await page.getByRole('status').textContent()")
        assert readback == 'Welcome, cloud-probe', readback
        cli(viewer, 'screenshot', '--filename=artifacts/dashboard-handoff.png')
        cli(target, 'close')
        cli(target, 'open', url)
        assert evaluate(target, "async page => await page.getByRole('status').textContent()") == 'Welcome, cloud-probe'
        print('PASS: isolated dashboard, remote input, independent readback and profile reuse.', target)
    finally:
        for folder in (viewer, target):
            try:
                cli(folder, 'close')
            except Exception as error:
                print('Browser cleanup:', error, file=sys.stderr)
        if dashboard and dashboard.poll() is None:
            os.killpg(dashboard.pid, signal.SIGTERM)
            try:
                dashboard.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(dashboard.pid, signal.SIGKILL)
                dashboard.wait()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()

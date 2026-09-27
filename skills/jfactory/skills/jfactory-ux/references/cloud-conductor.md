# Sign into a study browser in cloud Conductor

Use this procedure when the owner wants to study an authenticated app without moving the agent to a local workspace. The browser runs in the cloud. The owner sees and controls it through Playwright's dashboard at a Conductor preview URL, then hands the same session back to the agent.

## Prepare the study

Read the [browser guide](browser.md) for scope, capture and account rules. Establish the app URL, customer task and allowed data actions. Do not start captures or navigate account-management pages while the owner is entering credentials. The owner signs in through the remote browser; never request passwords in chat or command arguments.

Check `CONDUCTOR_IS_LOCAL` and the installed `conductor preview set --help`. The cloud preview must require Conductor authentication and workspace read access. Check existing sharing with `conductor preview get`: there is one preview port per workspace. Preserve an existing preview and agree on a temporary switch if it belongs to another active task. Do not publish the dashboard through an anonymous tunnel.

From the repository, adapt the installed path for the chosen agent host:

```sh
UX="$PWD/.agents/skills/jfactory/skills/jfactory-ux/scripts/study.py"
python3 "$UX" init reference-study --url https://app.example.com --objective 'Understand how users organize saved items'
STUDY="$PWD/.context/ux/reference-study"
python3 "$UX" browser "$STUDY" install-browser ffmpeg
python3 "$UX" browser "$STUDY" open https://app.example.com
```

Replace the example URL. Reuse an existing study instead of rerunning `init` over it. No `--headed` is needed in the cloud. The helper uses a dedicated persistent Chrome profile and isolates Playwright's browser discovery, CLI registry and dashboard sockets per study. Do not launch an unscoped global `playwright-cli show` and assume that selecting a session hides other sessions.

## Give the owner control

In an owned terminal session that stays running:

```sh
python3 "$UX" dashboard "$STUDY" --port 8931 --host 0.0.0.0
```

Choose an available port. The server prints a listening address. Binding to `0.0.0.0` lets the authenticated Conductor proxy forward requests with its external hostname; the default loopback host is for local testing. The dashboard has browser-control privileges and relies on Conductor's access gate. It must never be exposed through an unprotected public port.

In a second terminal:

```sh
conductor preview set --port 8931
```

Share the URL that command actually returns. Verify an anonymous HTTP request cannot fetch dashboard content and that the owner can load it after Conductor sign-in. A local dashboard test alone does not prove the cloud gateway or WebSocket works.

Tell the owner:

1. Open the preview link while signed into Conductor with access to this workspace.
2. Select the intended app tab in the dashboard. Enable interactive mode or click inside its browser view to take control.
3. Click the login field, wait until it visibly has focus, then sign in normally, including MFA. Do not enter a real password into a demo page.
4. Press Escape to release control and tell the agent that login is complete.

While the owner has control, stop agent clicks/navigation in that study. Turning off trace/video capture does not make the browser session secret from the cloud host or other authorized workspace members. Choose an appropriate account/workspace for the study.

## Resume research and close the handoff

After the owner responds, inspect a safe signed-in page and confirm the expected account and role without dumping cookies, tokens or storage. Keep authentication separate from research claims: successful login does not prove a feature works. Resume the agreed research and capture only the necessary non-login paths.

Close the shared control link when the handoff is complete. If the preview still points to this dashboard, restore the previous port, or run `conductor preview delete` if none existed. Recheck ownership before changing the preview because another task may have repointed it. Stop only the terminal process running this dashboard. The study browser may remain open for research; close it later with `browser "$STUDY" close`. Do not use global cleanup commands.

## Continue later or recover

- In the same surviving workspace, `browser "$STUDY" open <app URL>` reuses that study's profile. Check whether it is still signed in. The app controls expiration and additional login challenges.
- If the workspace sleeps, its preview stops serving. Restart owned browser/dashboard processes after wake and check the session again. New/reset/archived workspaces must not be assumed to preserve login.
- If the link shows an authentication error, verify Conductor sign-in and workspace access. If the shell loads but the browser stays disconnected, inspect the dashboard's WebSocket connection before requesting app credentials.
- If the app rejects the cloud browser, record the blocked journey. Do not promise that this mechanism bypasses provider restrictions. A different approved browser environment may be required.

The per-study isolation uses internal environment hooks in the pinned Playwright CLI. `tests/dashboard_smoke.py` checks actual discovery and browser interaction when the dependency changes. Close active browsers with the old helper before upgrading from a version that used the shared registry. The cloud gateway, human SSO/MFA and a real competitor's access rules remain separate from local automated smoke coverage.

During the September 27, 2026 setup, an owner opened the Conductor-protected preview, entered a disposable demo value and submitted it; the agent confirmed the resulting state in the same cloud browser. Anonymous access returned HTTP 401. A separate automated test verified isolated session discovery, dashboard input, independent readback and profile reuse. This establishes the demo handoff, not successful authentication to every app.

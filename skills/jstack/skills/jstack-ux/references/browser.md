# Browser sessions and capture

Use an existing host browser tool if it can interact with the actual app and capture the necessary evidence. Otherwise the helper drives [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli), pinned to `@playwright/cli@0.1.21`. Python 3.10+, Node/npm and Chrome are prerequisites. The first browser command downloads that npm package through `npx`; installing jstack itself does not install browser tools. The CLI's transitive dependencies follow its published package metadata, so the pin is not a complete dependency lock.

## Start and explore

From the target repository, substitute its installed skill path for `UX`. Claude/Cursor installations use their host directory instead of `.agents`.

```sh
UX="$PWD/.agents/skills/jstack/skills/jstack-ux/scripts/study.py"
python3 "$UX" init reference-study --url https://app.example.com --objective 'Understand how users organize saved items'
STUDY="$PWD/.context/ux/reference-study"
python3 "$UX" browser "$STUDY" --help
python3 "$UX" browser "$STUDY" open https://app.example.com
python3 "$UX" browser "$STUDY" snapshot
```

Replace the example domain with the approved app. Read `study.json`, fill its account/scope fields, and keep one study per objective. The helper creates a unique session and dedicated persistent profile. It runs CLI calls from the private study folder, directs automatic captures to `artifacts/`, and refuses global browser cleanup. It does not enforce URL or mutation permissions. Edit `browser.json` to use an installed browser executable or appropriate viewport when necessary. `install-browser --help` describes the CLI's browser installation. Do not use another agent's profile.

Read the snapshot file the CLI returns. Use fresh element references or semantic locators, then inspect the new snapshot and screenshot. References can become stale after navigation. Some command failures appear in the CLI response even with a zero process exit; inspect the response and resulting page instead of treating exit status as verification. Use `--help <command>` to check the pinned CLI's options. Never enter passwords or tokens through command arguments.

```sh
python3 "$UX" browser "$STUDY" click "getByRole('button', { name: 'Saved items', exact: true })"
python3 "$UX" browser "$STUDY" screenshot --filename=artifacts/saved-items.png
python3 "$UX" browser "$STUDY" resize 390 844
python3 "$UX" browser "$STUDY" snapshot
```

Keep success captures deliberately; failure-only screenshot/trace defaults do not produce a UX review packet. Use screenshots for layout and visible state, snapshots for controls/semantics, and traces plus video for action sequences. Inspect images through the host's image viewer. If video playback is unavailable, extract and inspect timestamped frames with a video tool; disclose that this does not measure smoothness.

## Sign into a subscribed app

On a machine with a visible browser, use `open <url> --headed` and let the owner sign in themselves, including MFA. Reuse that study's dedicated profile. Stop trace/video capture before authentication, then start capture after confirming the expected account. Avoid recording login forms, credentials or account-management pages. The CLI may still save snapshots/console output, so the entire study is private.

Cloud Conductor does not inherit the Mac's browser login. Use a local Conductor workspace or a supported owner-accessible remote browser for the login. If `RunLocalCommand` is available, it can launch the dedicated local workflow with the owner's authorization; it does not automatically expose the cloud folder or an existing Mac session. Do not copy everyday browser cookies. An explicitly authorized storage-state handoff can be used when the app supports it, but it contains credentials and may omit required browser/device state. Never commit it or put it in chat. If access cannot be established, record the blocked journey and continue independent work.

## Capture a transition

After login and before the action:

```sh
python3 "$UX" browser "$STUDY" video-start artifacts/open-item.webm --size=1440x900 --fps=60
python3 "$UX" browser "$STUDY" tracing-start
python3 "$UX" browser "$STUDY" click "getByRole('button', { name: 'Open item', exact: true })"
python3 "$UX" browser "$STUDY" screenshot --filename=artifacts/item-open.png
python3 "$UX" browser "$STUDY" video-stop
python3 "$UX" browser "$STUDY" tracing-stop
```

Use the trace path returned by the CLI. This version writes a `.trace`, companion `.network` file and `resources/` directory rather than a ZIP. Keep them together for replay. Stop recordings before closing the session so files finalize. For natural-motion study, leave cursor/action overlays off; they alter pacing. An annotated walkthrough can be a separate recording. Requesting 60 fps does not prove the browser or recording achieved it.

Inspect recorded frames for cropping, scaling and timing before using a clip as evidence. Trials of this CLI version showed a small page inside a larger gray video canvas when tracing started first. Start video before tracing and check the result. If a recording is defective, retain it as a failed capture and retake a safe authorized path, or capture trace and video separately. Do not repeat consequential actions merely to improve a recording.

For short animations, put the action and observation together in a study-local `motion.js` file, then run `browser "$STUDY" run-code --filename=motion.js`:

```js
async page => {
  await page.getByRole('button', { name: 'Open item', exact: true }).click();
  return await page.evaluate(() => document.getAnimations().map(animation => ({
    target: animation.effect?.target?.tagName,
    state: animation.playState,
    timing: animation.effect?.getComputedTiming(),
    keyframes: animation.effect?.getKeyframes()
  })));
}
```

Adapt the locator to what actually exists. Empty animation results mean none were observed at that instant, not that the app has no motion. Canvas/video and some scripted effects need different observation. Compare normal motion with `set-reduced-motion reduce` when relevant, then `clear-reduced-motion`. Do not disable animations or force states for a recording presented as natural behavior.

## Review and close

Fill `report.json` using [the research record](research.md), then:

```sh
python3 "$UX" report "$STUDY"
python3 "$UX" browser "$STUDY" close
```

Open `walkthrough.html` locally with its neighboring artifacts. Do not expose it through a public preview without reviewing private content and authorization. Trace Viewer can open the trace locally using an available Playwright installation. Keep login state out of the review packet. Remove a profile only after closing its session and when the owner no longer needs it; do not run global `kill-all` or `close-all` in a multi-agent workspace.

The CLI blocks `file://` navigation. To inspect the walkthrough through it, run `python3 "$UX" serve "$STUDY"` in an owned terminal session, then navigate to the printed loopback URL. The server exposes only the walkthrough and artifacts, not the profile or scope files. It is reachable on that machine only; a Mac cannot use a cloud localhost URL directly. Stop that owned server when finished. Private captures remain sensitive even on localhost; do not tunnel or publish the server as an incidental review step.

The helper is a study driver, not a deterministic app verifier. Convert stable expectations into the repository's actual tests and use jstack's [verification contract](../../../references/verification.md) for completion claims. Browser exploration can reveal a problem without proving a regression test exists.

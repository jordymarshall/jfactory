# jstack

## 1. Value

### What

jstack is a set of skills and tools that your coding agent uses inside a project. It helps the agent agree on a clear goal, build or investigate, check what actually happened, and return a result you can understand and review.

It connects four loops:

| Loop | What it does |
| --- | --- |
| **Product** | Clarifies the customer, their problem and the outcome worth building. |
| **UX** | Studies real apps and tests whether the experience is understandable, usable and appropriate for that customer. |
| **Engineering** | Implements the agreed behavior, runs checks, inspects results and fixes failures. |
| **Workflow improvement** | Examines recurring agent mistakes and improves the skills, tools or automated checks. |

### Why

You should be able to leave an agent working and return to a result you can evaluate. jstack gives it a bounded objective and feedback it can use while you are away. You make consequential product decisions and review the experience; the agent handles routine implementation, checks and corrections within that scope.

Every handoff should distinguish **what you decided, what the agent inferred, what exists, what was verified, and what you accepted**. The default delivery is a pull request open for human review, without draft status. Missing proof stays visible; opening a PR does not mean it is verified or safe to merge. Merging and release need your authorization.

## 2. How to use

### Initial setup

**Do this once per project. Your agent performs the technical setup.**

1. **Open the project in your coding agent**, locally or in a Conductor cloud workspace.
2. **Paste this prompt:**

   > Set up https://github.com/jordymarshall/jstack in this repository. Read its README and installer before installing. Preserve our existing instructions and documents. Inspect what actually exists, interview me about unresolved customer and experience goals, and establish one useful first objective. Set up and demonstrate the checks needed to verify it. Return a setup PR with what works, what is missing and how we will use it. Do not merge or release.

3. **Answer the product questions.** The agent should recommend options and clarify who the product serves, what the customer needs to accomplish and what is out of scope. Existing settled decisions carry forward.
4. **Provide the access needed for verification.** That might mean a development account, test data or a running app. For a subscribed reference app, use the browser login process below. Missing access stays an explicit gap.
5. **Review the setup result.** Expect a short `AGENTS.md` linking to the product brief, system map, feature/status map and agent instructions. Detailed facts have one home. Expect at least one demonstrated check of the first runnable journey, or a precise explanation of what blocks it.
6. **Review and merge the setup PR when satisfied.** Start a fresh agent session after installation and have it confirm that it can see jstack, state the current objective and name the checks it will use.

An empty repository starts with an agreed first runnable slice. An existing repository starts by reconciling its current code, decisions and checks. Installation alone does not mean the app has been verified.

#### Signing into an app from cloud Conductor

You can keep the agent and browser in the cloud. Ask:

> Set up a dedicated cloud browser for [app URL] using jstack. Give me the Conductor preview link so I can sign in myself, then wait for me to hand control back before researching [customer task].

The agent starts that study's browser and interactive dashboard, then shares it through Conductor's authenticated workspace preview. You open the link, select the browser, click inside the page and sign in normally, including MFA. Press Escape to release control and tell the agent you are done. It checks that the expected account is open and continues in the same session.

You do not send your password in chat. Workspace members with preview access can reach the dashboard, so use a suitable account and workspace. The agent closes the dashboard link after handoff; the browser can remain signed in until its session expires. A new or reset workspace may require login again. Some apps restrict cloud or automated browsers; access must be checked for the actual app.

The agent's exact commands, access checks and cleanup are in [cloud browser handoff](skills/jstack/skills/jstack-ux/references/cloud-conductor.md). For local work, you sign into a dedicated visible browser instead.

### Continued use

**Describe the outcome in ordinary language. You do not need to invoke each skill.**

1. **Give the agent one useful outcome.** For example: “Let someone save a reference and find it again after returning later.” Include constraints you already know.
2. **Settle consequential choices.** The agent clarifies unresolved customer/experience decisions and records observable completion criteria. A routine fix with settled behavior can proceed directly.
3. **Let it run the relevant loops.** It investigates, implements, exercises the real path, inspects state and side effects, and corrects failures. Meaningful UI changes also get an experience review. It updates the existing documents as decisions change.
4. **Review the result.** The final message must include the outcome, decisions/assumptions, what changed, actual checks/results and evidence links, remaining gaps, and a ready-for-review PR with its commit. Try the customer task yourself. A screenshot, passing build or bare "confirmed" does not prove the whole journey.
5. **Give specific feedback or approve the next step.** “Saving works, but finding the item adds an unnecessary step” starts another iteration. Owner acceptance, merge and release are separate decisions. The agent does not silently start another feature when the objective is complete.

Copy this for normal feature work:

> Implement [customer outcome] within [scope]. Clarify consequential choices, verify the agreed behavior through the real application, review the UX, update the existing records and return a PR with a walkthrough. Continue routine work and corrections without waiting for “keep going.” Do not merge or release.

Copy this to learn from another app:

> Study [app URL] for [customer tasks]. Use a dedicated browser and arrange login if needed. Map navigation, objects, journeys, states and motion. Return a visual walkthrough separating observations, inferred intent, recommendations for our customer and unexplored areas. Do not change shared data or implement the findings yet.

An in-depth study begins with an inventory, then covers prioritized journeys across successive passes. The coverage map makes remaining work visible. Competitor choices inform proposals; they do not automatically become requirements. Customer usability claims still need customer evidence.

For the feedback paths between these loops and the distinction between app checks and skill evals, read [how the loops work together](skills/jstack/references/methodology.md).

#### Working in several worktrees

Use one worktree, branch and PR per coherent task. Agents check open PRs for overlapping files and dependencies before implementing and again before delivery. Independent work targets the base branch. Dependent work waits or uses an explicit PR stack with a stated merge order. Before integrating overlapping PRs, refresh the branches, resolve conflicts and rerun affected checks, including the combined user journey. Worktrees isolate files; they cannot promise conflict-free behavior.

Update jstack through one adoption PR in each project. Once merged, new workspaces starting from that updated branch inherit it. Existing workspaces must integrate the update and reload their instructions. Updating this upstream repository or one workspace does not update every worktree. The agent should identify its loaded jstack version when it starts work. See [worktree coordination](skills/jstack/references/worktrees.md).

If an agent returns an unsupported success claim, ask:

> Show the agreed criteria, what you actually ran on this revision, observed results and evidence links, and remaining gaps. Identify the jstack version and instructions you loaded. Finish any missing verification and open the PR for review; do not merge.

This should already be part of its handoff. The prompt helps recover a missed step; an installed skill alone does not guarantee the agent followed it. Repository CI can enforce configured tests, while evidence review checks whether those tests prove the intended behavior.

<details>
<summary>Manual installation and updates</summary>

Inspect a checkout, then install with Python 3.10+:

```sh
git clone https://github.com/jordymarshall/jstack.git /tmp/jstack
python3 /tmp/jstack/scripts/install.py /path/to/project
```

The default installer copies the bundle into `.agents/skills/jstack` and adds a managed section to `AGENTS.md`. It preserves surrounding text and refuses conflicting local edits. `--agent claude` uses `.claude/skills/jstack` and `CLAUDE.md`; `--agent cursor` uses `.cursor/skills/jstack` and `AGENTS.md`. Other agents can read [SKILL.md](skills/jstack/SKILL.md) directly. Verify instruction discovery in your chosen host.

To update, inspect the newer checkout, then rerun the installer with `--update`. Locally modified managed files still cause a refusal. Close active study browsers with the old helper before upgrading their session tooling. Installation does not install dependencies, sign into apps, commit, push or deploy. Browser commands fetch the pinned Playwright CLI and need Node/npm, Chrome and the documented video encoder. Python process control and the dashboard helper support POSIX; use WSL or host-native tools on Windows.

</details>

<details>
<summary>Develop, verify and understand the limits</summary>

```sh
python3 -m unittest discover -s tests -v
python3 skills/jstack/scripts/check-upstream.py
npx --yes @playwright/cli@0.1.21 install-browser ffmpeg
python3 tests/browser_smoke.py
python3 tests/dashboard_smoke.py
```

Tests cover installation preservation, evidence freshness/scopes, private report serving, real browser actions and dashboard handoff. CI uses disposable local pages, not real competitor accounts. Conductor's external authentication gateway and a real user's login require separate validation. See [browser setup](skills/jstack/skills/jstack-ux/references/browser.md) and [cloud handoff](skills/jstack/skills/jstack-ux/references/cloud-conductor.md) for current limits.

Instructions guide the agent during a session. They do not schedule background work or guarantee compliance. No customer brief, application tests, production credentials, automatic merge or branch protection is bundled. A component check cannot prove an authenticated application journey. [Verification scopes](skills/jstack/references/verification.md) define those distinctions. Command receipts check freshness and coverage, not whether a test is meaningful.

Skill changes should also be evaluated on realistic isolated tasks using [the evaluation cases](evals/scenarios.md) and the bundled pstack eval playbook. Packaging tests are not a cross-model reliability benchmark.

</details>

## Attribution

Built around selected [Lauren Tan pstack](https://github.com/cursor/plugins/tree/ecc249f1e306fc64ddf83c7bed16cacf7c2239db/pstack) skills. Original files remain unchanged, MIT, copyright Lauren Tan 2026, version 0.15.5 at `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`. See [provenance](skills/jstack/vendor/pstack/UPSTREAM.md) and [license](skills/jstack/vendor/pstack/LICENSE). jstack additions are MIT, copyright Jordan Marshall 2026.

This is an independent adaptation. Microsoft Playwright CLI is an optional runtime dependency; its upstream skill is not vendored. Update pinned dependencies in a separate change, review compatibility and rerun the applicable integrity and behavior checks.

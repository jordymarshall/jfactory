# jfactory

## 1. Value

### What

jfactory is a set of skills and tools that your coding agent uses inside a project. It helps the agent agree on a clear goal, build or investigate, check what actually happened, and return a result you can understand and review.

It connects four loops:

| Loop | What it does |
| --- | --- |
| **Product** | Clarifies the customer, their problem and the outcome worth building. |
| **UX** | Studies real apps and tests whether the experience is understandable, usable and appropriate for that customer. |
| **Engineering** | Implements the agreed behavior, runs checks, inspects results and fixes failures. |
| **Workflow improvement** | Examines recurring agent mistakes and improves the skills, tools or automated checks. |

### Why

You should be able to leave an agent working and return to a result you can evaluate. jfactory gives it a bounded objective and feedback it can use while you are away. You make consequential product decisions and review the experience; the agent handles routine implementation, checks and corrections within that scope.

Every handoff should distinguish **what you decided, what the agent inferred, what exists, what was verified, and what you accepted**. The default delivery is a pull request open for human review, without draft status. Missing proof stays visible; opening a PR does not mean it is verified or safe to merge. After verification, the agent enables protected auto-merge under your standing repository policy. Missing proof or unavailable merge gates keeps the PR open. During setup, establish whether merging also deploys.

## 2. How to use

### Initial setup

**Do this once per project. Tell the agent to set up jfactory; it handles the technical steps.**

1. **Open the project in your coding agent**, locally or in a Conductor cloud workspace.
2. **Paste this prompt:**

   > Set up https://github.com/jordymarshall/jfactory for this project. Help me clarify what we are building and establish the product, UX and engineering workflow. Preserve our existing work and configure verified PR delivery with auto-merge.

3. **Answer the product questions.** The agent should recommend options and clarify who the product serves, what the customer needs to accomplish and what is out of scope. Existing settled decisions carry forward.
4. **Respond when the agent needs access.** It identifies missing accounts, test data or environment setup and guides you through the necessary step. If an app needs you to sign in, it prepares the browser and gives you access to it. You do not need to know which tool or skill to request.
5. **Review the setup result.** Expect a short `AGENTS.md` linking to the product brief, system map, feature/status map and agent instructions. Detailed facts have one home. Expect at least one demonstrated check of the first runnable journey, or a precise explanation of what blocks it.
6. **Establish merge gates.** The agent configures authorized required checks and auto-merge, or names the exact access/plan blocker. Verified PRs can merge automatically once the required checks and reviews pass; you may see the final result after merge. Start a fresh agent session after installation and have it confirm the loaded jfactory version, current objective and checks.

An empty repository starts with an agreed first runnable slice. An existing repository starts by reconciling its current code, decisions and checks. Installation alone does not mean the app has been verified.

#### When an app needs you to sign in

You do not need to ask for a browser or know the setup commands. When your requested work needs a signed-in app, the agent checks for a usable session and initiates the login handoff if necessary.

In cloud Conductor, the agent starts a dedicated browser and gives you an authenticated preview link. It tells you how to select the app and take control. You sign in, including MFA, then hand control back as instructed. The agent checks the resulting session and continues the task. Locally, it prepares a dedicated visible browser instead.

Your part is signing in; the agent handles setup, access checks and cleanup. Do not put passwords in chat. Workspace members with preview access can reach the cloud dashboard. A new workspace or expired session may need another login. If the host or app cannot support the handoff, the agent explains the specific blocker and continues work that does not require that access.

The [cloud handoff procedure](skills/jfactory/skills/jfactory-ux/references/cloud-conductor.md) contains the technical steps for the agent.

### Continued use

**Describe the outcome in ordinary language. You do not need to invoke each skill or tell the agent to set up its tools.** The installed instructions tell it to choose the relevant loops, arrange access, verify its work and deliver a PR. This happens during an active agent session; jfactory does not run a background service.

1. **Give the agent one useful outcome.** For example: “Let someone save a reference and find it again after returning later.” Include constraints you already know.
2. **Settle consequential choices.** The agent clarifies unresolved customer/experience decisions and records observable completion criteria. A routine fix with settled behavior can proceed directly.
3. **Let it run the relevant loops.** It investigates, implements, exercises the real path, inspects state and side effects, and corrects failures. Meaningful UI changes also get an experience review. It updates the existing documents as decisions change.
4. **Review the result.** The final message must include the outcome, decisions/assumptions, what changed, actual checks/results and evidence links, remaining gaps, and a ready-for-review PR with its commit. Try the customer task yourself. A screenshot, passing build or bare "confirmed" does not prove the whole journey.
5. **Give specific feedback or approve the next step.** “Saving works, but finding the item adds an unnecessary step” starts another iteration. Customer acceptance remains separate from technical verification. Auto-merge follows the agreed repository policy; release follows its recorded deployment policy. The agent does not silently start another feature when the objective is complete.

Copy this for normal feature work:

> Let users save a reference and find it again when they return later.

Copy this to learn from another app:

> Study [app URL] to understand how people organize and find saved items, including the interactions and animations. Show me what we can learn for our product.

An in-depth study begins with an inventory, then covers prioritized journeys across successive passes. The coverage map makes remaining work visible. Competitor choices inform proposals; they do not automatically become requirements. Customer usability claims still need customer evidence.

See [auto-merge setup](skills/jfactory/references/auto-merge.md) for the exact gates, GitHub settings and failure behavior. If the connection cannot change repository settings, the agent reports what the owner must configure.

For the feedback paths between these loops and the distinction between app checks and skill evals, read [how the loops work together](skills/jfactory/references/methodology.md).

#### Working in several worktrees

Use one worktree, branch and PR per coherent task. Agents check open PRs for overlapping files and dependencies before implementing and again before delivery. Independent work targets the base branch. Dependent work waits or uses an explicit PR stack with a stated merge order. Before integrating overlapping PRs, refresh the branches, resolve conflicts and rerun affected checks, including the combined user journey. Worktrees isolate files; they cannot promise conflict-free behavior.

Update jfactory through one adoption PR in each project. Once merged, new workspaces starting from that updated branch inherit it. Existing workspaces must integrate the update and reload their instructions. Updating this upstream repository or one workspace does not update every worktree. The agent should identify its loaded jfactory version when it starts work. See [worktree coordination](skills/jfactory/references/worktrees.md).

If an agent returns an unsupported success claim, ask:

> Show the agreed criteria, what you actually ran on this revision, observed results and evidence links, and remaining gaps. Identify the jfactory version and instructions you loaded. Finish any missing verification and open the PR for review. Enable auto-merge only when the agreed proof and repository gates are satisfied.

This should already be part of its handoff. The prompt helps recover a missed step; an installed skill alone does not guarantee the agent followed it. Repository CI can enforce configured tests, while evidence review checks whether those tests prove the intended behavior.

<details>
<summary>Manual installation and updates</summary>

Inspect a checkout, then install with Python 3.10+:

```sh
git clone https://github.com/jordymarshall/jfactory.git /tmp/jfactory
python3 /tmp/jfactory/scripts/install.py /path/to/project
```

The default installer copies the bundle into `.agents/skills/jfactory` and adds a managed section to `AGENTS.md`. It preserves surrounding text and refuses conflicting local edits. `--agent claude` uses `.claude/skills/jfactory` and `CLAUDE.md`; `--agent cursor` uses `.cursor/skills/jfactory` and `AGENTS.md`. Other agents can read [SKILL.md](skills/jfactory/SKILL.md) directly. Verify instruction discovery in your chosen host.

To update, inspect the newer checkout, then rerun the installer with `--update`. This also migrates an unmodified legacy `jstack` installation to `jfactory`, including its managed instruction block and receipt. It refuses ambiguous dual installations and conflicting local edits. Update any project-owned references outside that managed block from the old skill paths to the new ones, then reload the agent session. Historical evidence under `.context/jstack/` stays untouched; run fresh checks into `.context/jfactory/` instead of relabeling old receipts. Locally modified managed files still cause a refusal. Close active study browsers with the old helper before upgrading their session tooling. Installation does not install dependencies, sign into apps, commit, push or deploy. Browser commands fetch the pinned Playwright CLI and need Node/npm, Chrome and the documented video encoder. Python process control and the dashboard helper support POSIX; use WSL or host-native tools on Windows.

</details>

<details>
<summary>Develop, verify and understand the limits</summary>

```sh
python3 -m unittest discover -s tests -v
python3 skills/jfactory/scripts/check-upstream.py
npx --yes @playwright/cli@0.1.21 install-browser ffmpeg
python3 tests/browser_smoke.py
python3 tests/dashboard_smoke.py
```

Tests cover installation preservation, evidence freshness/scopes, private report serving, real browser actions and dashboard handoff. CI uses disposable local pages, not real competitor accounts. Conductor's external authentication gateway and a real user's login require separate validation. See [browser setup](skills/jfactory/skills/jfactory-ux/references/browser.md) and [cloud handoff](skills/jfactory/skills/jfactory-ux/references/cloud-conductor.md) for current limits.

Instructions guide the agent during a session. They do not schedule background work or guarantee compliance. No customer brief, application tests or production credentials are bundled. The auto-merge procedure requires actual repository settings and enforced checks; the installer itself does not configure them. A component check cannot prove an authenticated application journey. [Verification scopes](skills/jfactory/references/verification.md) define those distinctions. Command receipts check freshness and coverage, not whether a test is meaningful.

Skill changes should also be evaluated on realistic isolated tasks using [the evaluation cases](evals/scenarios.md) and the bundled pstack eval playbook. Packaging tests are not a cross-model reliability benchmark.

</details>

## Attribution

Built around selected [Lauren Tan pstack](https://github.com/cursor/plugins/tree/ecc249f1e306fc64ddf83c7bed16cacf7c2239db/pstack) skills. Original files remain unchanged, MIT, copyright Lauren Tan 2026, version 0.15.5 at `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`. See [provenance](skills/jfactory/vendor/pstack/UPSTREAM.md) and [license](skills/jfactory/vendor/pstack/LICENSE). jfactory additions are MIT, copyright Jordan Marshall 2026.

This is an independent adaptation. Microsoft Playwright CLI is an optional runtime dependency; its upstream skill is not vendored. Update pinned dependencies in a separate change, review compatibility and rerun the applicable integrity and behavior checks.

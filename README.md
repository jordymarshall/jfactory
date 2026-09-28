# jfactory

## 1. Value

### What

jfactory gives your coding agent a repeatable way to clarify a goal, build it, verify the result and ship it. It installs into your project and adapts to its existing code, documentation and tools.

It connects four loops:

| Loop | The question it answers |
| --- | --- |
| Product | Who is this for, what problem are we solving, and what would success look like? |
| UX | Can someone understand and complete the task in the running product? What can we learn from relevant apps? |
| Engineering | Does the implementation behave correctly, including its saved state and side effects? |
| Workflow improvement | Where did the agent's method fail, and does a revised skill or automated check improve its behavior? |

### Why

You can give the agent a bounded outcome and let it work through routine implementation and verification without repeatedly saying "keep going." You stay involved in consequential product choices and customer feedback.

The result distinguishes **what you decided, what the agent inferred, what exists, what was verified, and what you accepted**. Changes ship through a PR and default to protected squash auto-merge once the agreed verification and repository requirements pass. Missing proof keeps the PR open. Setup establishes whether merging also deploys.

## 2. How to use

### Initial setup

Open your project in your coding agent and say:

> Setup jfactory from https://github.com/jordymarshall/jfactory in this project.

If the project already has the current workflow installed, **"Setup jfactory"** is enough. The agent handles installation and adoption; you do not need to invoke each skill.

During setup, it:

1. **Reconciles the project foundation.** It cleans up stale documents, duplicate status records and conflicting instructions while preserving unique decisions and historical evidence. A short `AGENTS.md` links to the product brief, system map, feature/status map and agent instructions. Existing detailed documents keep their purpose.
2. **Clarifies the product with you.** It investigates first, then asks about unresolved customer needs, the intended experience and evidence of success. It carries forward settled answers and proposes one bounded next outcome.
3. **Prepares development and verification.** It reuses or repairs setup commands, diagnostics and tests; establishes browser access where needed; and identifies safe accounts, data and environments. It exercises an existing customer journey when access permits.
4. **Establishes delivery.** It configures authorized CI and protected auto-merge, checks deployment triggers, and opens one adoption PR with evidence and remaining gaps.

Your part is answering unresolved product questions and providing access the agent cannot obtain itself. For a signed-in app, it prepares a browser handoff, gives you the local window or authenticated cloud link, and waits while you sign in and hand control back. Do not put passwords in chat. Missing settings permissions get an exact owner action, such as importing a prepared ruleset.

Setup returns a readiness report for documentation, product direction, tools, verification, environments and delivery. It identifies what was verified, what is configured but unverified, and what is blocked. An installed skill alone does not make a repository operational. An empty project first needs agreement on a runnable product slice.

The portable tools have automated tests. Full adoption across projects and models still needs behavioral trials; installing them is not evidence that every agent will follow the method. See [setup completion criteria](skills/jfactory/references/setup.md#5-deliver-an-honest-setup-result).

### Continued use

Describe one useful outcome in ordinary language:

> Let users save a reference and find it again when they return later.

The agent clarifies consequential choices, records observable completion criteria, implements, checks the real behavior and fixes failures. Before substantial features, it reviews the customer hypothesis and intended experience in depth. Routine fixes with settled behavior can proceed directly.

For relevant app research, say:

> Study [app URL] to understand how people organize and find saved items, including the interactions and animations. Show me what we can learn for our product.

The agent arranges access, records observations and remaining coverage, and distinguishes useful proposals from agreed requirements. Competitor behavior does not automatically become your product specification.

At handoff, expect an explanation of the change, actual verification evidence, remaining gaps and the PR's merge state. Try the customer task and give concrete feedback. "Saving works, but finding the item takes too many steps" starts another iteration. Customer acceptance remains separate from passing tests. The agent stops at the agreed objective instead of silently starting another feature.

### Keeping it up to date

| What changes | How it stays current |
| --- | --- |
| Product decisions, architecture and feature status | The agent updates the existing canonical documents in the same change. It preserves history and avoids adding competing plans. |
| Application controls and verification recipes | The agent repairs affected recipes and feature-map entries when behavior changes, then reruns them. Request a broader verification audit when coverage or instructions have drifted. |
| The installed jfactory bundle | Request an update. The agent reviews upstream changes, respects any version pin, uses the supported installer and delivers one adoption PR. It reconciles local customizations rather than overwriting them. |
| Worktrees and agent sessions | New workspaces inherit the adoption when their starting branch includes it. Existing worktrees integrate that commit and reload instructions as needed. The agent checks its loaded version. |
| Vendored pstack methods | jfactory maintainers review and test an upstream update before changing the pinned bundle. A project update receives that reviewed version. |

Use this when you want the latest workflow and a setup refresh:

> Update jfactory from https://github.com/jordymarshall/jfactory and reconcile this project's setup. Preserve our product decisions and existing work.

Repeating setup resumes the same adoption record and repairs drift. Ordinary feature work uses the installed revision; it does not silently upgrade the workflow. There is no background updater or automatic rollout across repositories.

For a verification audit:

> Audit our verification skill and feature map against the current app. Repair stale instructions and show which journeys were actually exercised.

### Workspaces, previews and staging

Use one worktree or cloud workspace per coherent task. Agents check overlapping PRs and dependencies, update shared branches from current main, and recheck affected behavior before merging. Extra sessions in the same workspace share its files. jfactory does not start the next workspace or agent session after a merge.

### Several features at once

Ask one coordinating agent in Conductor:

> Use jfactory to deliver [feature A], [feature B] and [feature C] in parallel. Clarify each outcome and its acceptance criteria with me first, then run at most three workspaces at a time.

The coordinator agrees outcomes and open decisions with you, prototypes unresolved design questions, and writes a complete task contract per feature. It launches each feature in its own Conductor workspace, then tracks units, verdicts and your pending decisions in one durable program record. It checks each worker's actual PR and evidence rather than trusting its summary, and merges overlapping PRs one at a time under protected auto-merge. If the coordinator is interrupted, a new session resumes from that record. See the [coordination procedure](skills/jfactory/references/coordination.md).

This runs only while an agent follows the procedure. jfactory has no background supervisor, and parallel workspaces multiply cost, so it starts them only when you ask.

Each launched agent's model is chosen by task tier and current usage. Core coding uses Opus 5.5, or GPT Astra 6 when Claude usage is exhausted. Faster work uses GPT Sol 6, or Opus 5.5 at low effort. Very simple tasks use GPT Luna 6. Agents check the session and weekly limits for each account before launching and record any fallback. See [model selection](skills/jfactory/references/models.md).

In Conductor cloud, setup prepares the repository bootstrap command and registers it when authorized tools allow, or gives you the exact settings step. Committing a local setup file alone does not configure cloud workspaces. See [environment setup](skills/jfactory/references/environments.md) and [worktree coordination](skills/jfactory/references/worktrees.md).

A workspace preview exposes a running dev server. A PR preview is a hosted build. Staging is a deliberately configured non-production environment, including its backing services and data. A preview can use staging services, but its URL alone does not prove isolation. Setup records where checks can safely run and which revision they exercised.

### Relationship to Lauren Tan's methodology

jfactory uses pinned pstack skills for creating and maintaining real-app verification, investigating code, reviewing changes and evaluating agent workflows. Its coordination procedure adapts her prototype, multi-PR planning and orchestration playbooks to Conductor workspaces and GitHub. It adds explicit product alignment, UX research, documentation reconciliation and portable repository setup. See [the methodology and its current evidence limits](skills/jfactory/references/methodology.md).

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

For this repository, [the main ruleset](.github/rulesets/main.json) requires the GitHub Actions `checks` job against current `main`, PRs and squash merges. An administrator must activate the rule in GitHub; committing its JSON does not activate it. Agents enable auto-merge only after verifying both the task and the active server rules.

Tests cover installation preservation, evidence freshness/scopes, private report serving, real browser actions and dashboard handoff. CI uses disposable local pages, not real competitor accounts. Conductor's external authentication gateway and a real user's login require separate validation. See [browser setup](skills/jfactory/skills/jfactory-ux/references/browser.md) and [cloud handoff](skills/jfactory/skills/jfactory-ux/references/cloud-conductor.md) for current limits.

Instructions guide the agent during a session. They do not schedule background work or guarantee compliance. No customer brief, application tests or production credentials are bundled. The auto-merge procedure requires actual repository settings and enforced checks; the installer itself does not configure them. A component check cannot prove an authenticated application journey. [Verification scopes](skills/jfactory/references/verification.md) define those distinctions. Command receipts check freshness and coverage, not whether a test is meaningful.

Skill changes should also be evaluated on realistic isolated tasks using [the evaluation cases](evals/scenarios.md) and the bundled pstack eval playbook. Packaging tests are not a cross-model reliability benchmark.

</details>

## Attribution

Built around selected [Lauren Tan pstack](https://github.com/cursor/plugins/tree/ecc249f1e306fc64ddf83c7bed16cacf7c2239db/pstack) skills. Original files remain unchanged, MIT, copyright Lauren Tan 2026, version 0.15.5 at `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`. See [provenance](skills/jfactory/vendor/pstack/UPSTREAM.md) and [license](skills/jfactory/vendor/pstack/LICENSE). jfactory additions are MIT, copyright Jordan Marshall 2026.

This is an independent adaptation. Microsoft Playwright CLI is an optional runtime dependency; its upstream skill is not vendored. Update pinned dependencies in a separate change, review compatibility and rerun the applicable integrity and behavior checks.

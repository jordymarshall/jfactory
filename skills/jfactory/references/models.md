# Choose models by task and remaining usage

Use this when jfactory launches or delegates to another agent: a Conductor workspace, session or routine, a reviewer, or a host subagent whose model can be set. The current session cannot change its own model. Repository instructions and the owner's current request take precedence over this default policy.

## 1. Pick the tier from the task

| Tier | Use for | Primary | Fallback when the primary has no usage remaining |
| --- | --- | --- | --- |
| Frontier | Core coding that needs strong intelligence: implementation, debugging, architecture and coordination | Opus 5.5 at medium effort: `--agent claude --model opus-5-5-1m --effort medium` | GPT Astra 6: `--agent codex --model gpt-6-astra` |
| Fast | Well-scoped work where speed matters more than depth: routine edits, follow-up fixes with a clear cause, CI triage, focused checks | GPT Sol 6: `--agent codex --model gpt-6-sol` | Opus 5.5 at low effort: `--agent claude --model opus-5-5-1m --effort low` |
| Trivial | Very simple or very fast tasks: lookups, renames, formatting, short summaries | GPT Luna 6: `--agent codex --model gpt-6-luna` | Opus 5.5 at low effort: `--agent claude --model opus-5-5-1m --effort low` |
| Verify | Verifying or reviewing another agent's work: judge whether it is right (its criteria, its jobs' goals, the standards and the outcomes) at the PR head, look at the changed screens and report a verdict | GPT Sol 6.1 at high effort: `--agent codex --model gpt-6.1-sol --effort high` | Opus 5.5 at high effort: `--agent claude --model opus-5-5-1m --effort high` |

- The task decides the tier. Remaining usage only decides between a tier's primary and fallback. Do not move core coding down a tier to save usage.
- Core coding runs Opus 5.5 at `medium` by default; raise it for ambiguous, cross-cutting or high-risk work when the owner or the task contract calls for it. A launch through the coordination tool uses the unit's effort, chosen by difficulty (default `medium`). Other launches use the host's default effort unless a row names one. The fast and trivial fallbacks run Opus 5.5 at `low` only, never a higher effort.
- Verification runs GPT Sol 6.1 at high effort (owner, 2026-09-30): a verdict decides whether work is right, so it gets a strong model rather than the fastest one. The Opus fallback also runs at high effort and without fast mode, because Claude fast mode can draw on extra usage and this setup must not depend on it.
- A verifier comes from a different family than the agent that implemented the work. When a Codex model implemented it, verify with Opus 5.5 at high effort: `usage.py --tier verify --implementer codex`. If the other family has no usage remaining, hold the verdict until its reset rather than verifying with the same family. The `jfactory verified` gate rejects same-family verdicts unless the owner has recorded `allow_same_family`. The coordination tool applies these rules through its `verify` role.
- Do not substitute models outside this table, such as other Claude, GPT or Cursor models, unless the owner asks.
- [`usage.py`](../scripts/usage.py) encodes this table and the coordination tool builds its roles from it; change both together. A test compares them. Confirm the ids with `conductor model` before launching. If an id is missing, use the tier's other model and report the missing id.
- Host subagents can use only the host's own models. Apply the tier where the host offers its model; otherwise inherit the current model and say so. Launch a Conductor session on another provider only when the task warrants a separate agent.

## 2. Read remaining usage for both accounts

Run the usage reader before choosing a model for a new launch, before each launch batch during [coordination](coordination.md), and when an agent stops at a usage limit:

```sh
python3 .agents/skills/jfactory/scripts/usage.py              # readings and a choice for every tier
python3 .agents/skills/jfactory/scripts/usage.py --tier fast --json
```

Use the host's installed skill path. It reports the used percentage and reset time of each window the provider returns (Claude's five-hour and weekly windows, Codex's weekly window and five-hour window when present), when each reading was observed and where it came from. It then prints the `--agent`, `--model` and `--effort` to launch for each tier, with the reason. Exit status 3 means some requested tier has no model with usage remaining.

Sources, read through supported interfaces only:

| Account | Source | Cost |
| --- | --- | --- |
| Claude | The `rate_limit_event` that Claude Code records in a Conductor Claude session transcript, read with `conductor session message`. It carries five-hour and seven-day utilization and reset times. Claude Code emits it when the reading changes, so the session's later responses confirm the value. The reader checks the current session and other Claude sessions in the workspace. | None |
| Codex | `account/rateLimits/read` from `codex app-server` where the Codex CLI is signed in, such as the owner's Mac. Otherwise the newest `rate_limits` entry in the Codex session logs under `$CODEX_HOME/sessions`, which Conductor-run Codex sessions write in the workspace. | None |
| Either, when missing or older than `--max-age` minutes (default 20) | A probe: a new Conductor session in the current workspace (Claude `haiku-4-5`, or Codex `gpt-6-luna` at low effort) asked to reply "ok". Its reading is then read from the sources above, and the probe session is archived. | One small turn on that account |

Use `--no-probe` to report missing or stale readings without launching a probe. Do not open credential files, copy tokens out of agent processes or call provider endpoints with the owner's tokens. Conductor keeps the Claude token out of shell commands deliberately.

If the reader cannot run, such as outside Conductor with neither CLI signed in, record usage as unknown, start on the primary and apply the usage-limit rule below if a launch or turn fails at a limit.

## 3. Decide, record and revisit

The reader treats a primary as having no usage remaining when a reported window is at least 90% used, or the provider reports the limit reached. `--reserve` sets another threshold when the owner chooses one. Also move to the fallback when:

- The provider rejected or stopped work because a usage limit was reached, even if the last reading was lower.
- The planned batch would push the account past the reserve. Split the batch between primary and fallback rather than launching every unit on one account.

Then:

- Use the tier's fallback until the exhausted window resets. Return to the primary for launches after that reset.
- If both models in a tier have no usage remaining, do not escalate to an unlisted model. Hold the affected units until the reported reset, continue work that does not need that tier and tell the owner in the next batched update.
- A worker stopped by a usage limit has not failed. Start a fallback session in the same workspace with `conductor session create`, pointing it to the pushed branch and the original task contract. This does not count toward the retry limit.
- Record the chosen agent, model and effort for each launch with the reader's reason, for example "fallback: claude weekly 94%, observed 3 min ago". Name the model actually used in the report or PR.

Readings are snapshots. Parallel sessions on the same account keep consuming it, so rerun the reader before each launch batch rather than reusing an old result.

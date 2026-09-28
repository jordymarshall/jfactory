# Choose models by task and remaining usage

Use this when jfactory launches or delegates to another agent: a Conductor workspace, session or routine, a reviewer, or a host subagent whose model can be set. The current session cannot change its own model. Repository instructions and the owner's current request take precedence over this default policy.

## 1. Pick the tier from the task

| Tier | Use for | Primary | Fallback when the primary has no usage remaining |
| --- | --- | --- | --- |
| Frontier | Core coding that needs strong intelligence: implementation, debugging, architecture, coordination and judgment-heavy review | Opus 5.5: `--agent claude --model opus-5-5-1m` | GPT Astra 6: `--agent codex --model gpt-6-astra` |
| Fast | Well-scoped work where speed matters more than depth: routine edits, follow-up fixes with a clear cause, CI triage, focused checks | GPT Sol 6: `--agent codex --model gpt-6-sol` | Opus 5.5 at low effort: `--agent claude --model opus-5-5-1m --effort low` |
| Trivial | Very simple or very fast tasks: lookups, renames, formatting, short summaries | GPT Luna 6: `--agent codex --model gpt-6-luna` | Opus 5.5 at low effort, as for the fast tier |

- The task decides the tier. Remaining usage only decides between a tier's primary and fallback. Do not move core coding down a tier to save usage.
- Use the host's default effort unless a row names one. The fast and trivial fallbacks run Opus 5.5 at `low` only, never a higher effort.
- Do not substitute models outside this table, such as other Claude, GPT or Cursor models, unless the owner asks.
- Confirm the ids with `conductor model` before launching. If an id is missing, use the tier's other model and report the missing id.
- Host subagents can use only the host's own models. Apply the tier where the host offers its model; otherwise inherit the current model and say so. Launch a Conductor session on another provider only when the task warrants a separate agent.

## 2. Check remaining usage for each account

Check before choosing a model for a new launch, before each launch batch during [coordination](coordination.md), and when an agent stops at a usage limit. For each provider account, read the used percentage and reset time of the session window (five hours), the weekly window and any model-specific weekly limit the provider reports.

| Account | Where usage is observable |
| --- | --- |
| Claude | `/usage` in Claude Code shows plan usage for the signed-in account. A Claude Code status line command receives `rate_limits.five_hour` and `rate_limits.seven_day` with used percentage and reset time. |
| Codex | `/status` in Codex shows the five-hour and weekly limits. The Codex app server's `account/rateLimits/read` method returns them to a program. |
| Either | The owner's statement of current usage, recorded with the time it was given. A launch or turn that fails because a usage limit was reached. |

Read usage only through these interfaces. Do not open credential files or call provider endpoints with the owner's tokens.

In a Conductor cloud workspace, provider sign-in can belong to Conductor rather than the workspace CLI. There, `claude -p /usage` may report only the session's cost and Codex may report no signed-in account. Record usage as unknown, start with the primary and apply the usage-limit rule below if a launch or turn fails at a limit. When a large program is being framed and usage is unknown, ask the owner for current usage alongside the other limits instead of blocking on it.

## 3. Decide, record and revisit

Treat a primary as having no usage remaining when any of these holds:

- Its session, weekly or model-specific weekly window is at least 90% used. The owner can set another reserve.
- The provider rejected or stopped work because a usage limit was reached.
- The planned batch would push the account past the reserve. Split the batch between primary and fallback rather than launching every unit on one account.

Then:

- Use the tier's fallback until the exhausted window resets. Return to the primary for launches after that reset.
- If both models in a tier have no usage remaining, do not escalate to an unlisted model. Hold the affected units, record the earliest reset time, continue work that does not need that tier and tell the owner in the next batched update.
- A worker stopped by a usage limit has not failed. Start a fallback session in the same workspace with `conductor session create`, pointing it to the pushed branch and the original task contract. This does not count toward the retry limit.
- Record the chosen agent, model and effort for each launch. When a fallback or unknown usage affected the choice, record the reason and the reading used, for example "Codex weekly 94% at 14:05 UTC, resets Friday". Name the model actually used in the report or PR.

Usage readings are snapshots. Parallel sessions on the same account keep consuming it, so recheck before each launch batch rather than reusing an old reading.

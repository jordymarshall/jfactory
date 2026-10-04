# Host and tool compatibility

jfactory is an instruction bundle with Python 3.10+ utilities. The installer supports repository layouts for Codex (`.agents/skills`), Claude Code (`.claude/skills`) and Cursor (`.cursor/skills`). Claude Code discovers skills only under `.claude/skills`, so when a repository also uses Claude Code (it has `CLAUDE.md` or `.claude/`), the installer writes a short entry at `.claude/skills/jfactory/SKILL.md` that points to the installed bundle. Without it, "use jfactory" loads nothing in Claude Code. Native discovery/tool behavior must still be checked in the chosen host. Other agents can read this SKILL.md directly. No claim of equal behavior across models or platforms.

- Read source methods from `../vendor/pstack/skills/<name>/SKILL.md` relative to this directory. Preserve originals, including Lauren Tan's MIT license and pinned receipt. Imported Cursor-specific paths/commands are translated below, not executed blindly.
- Cursor Task becomes the host's subagent facility **only for read-only work**: exploration, review and watching. A Task that writes code, local or `environment: "cloud"`, becomes a Conductor workspace launched with `coord.py` ([coordination translations](#coordination-translations)); this rule overrides the vendored playbooks' "only through the Task tool". On Claude Code, register `scripts/claude_subagent_guard.py` as a PreToolUse hook ([template](../templates/claude-settings.json)): it lets only read-only agent types run, such as `Explore`. Omit unsupported parameters. Choose the model by [model selection](models.md) where the host can set it; otherwise inherit the current model. A role label is not proof of model diversity. If delegation is unavailable, perform a scoped review and disclose the missing independent review.
- Use actual shell/browser/CLI tools and existing project harnesses instead of absent control-ui, control-cli, or deslop commands. For writing cleanup use the bundled unslop method. Do not install unrelated tooling automatically just because an upstream example names it.
- Keep investigations read-only. Use only relevant sources and current-workspace evidence. Missing connectors/transcripts remain gaps; never scan unrelated private sessions. No outbound chat/email authorization comes from upstream examples.
- Discover the remote default/review branch; do not assume main, rename the user's branch, or mix another task's changes into the PR. Use an isolated branch/checkout where needed.
- Upstream autonomous shipping and sticky Poteto Mode are not activated. PR delivery is the default; merge, production deployment, purchases and consequential data mutations need existing explicit authorization. Inspect PR-triggered workflows before pushing or opening the PR.
- For browser work, identify the actual instance, data target and test account. Localhost can use production data. Isolate parallel work; terminate only processes the current run owns. Do not reuse another agent's signed-in session.
- A different model family judge is preferred by upstream eval/review methods. If unavailable, say the trial is same-family, not cross-model validation. Review actual tool actions and artifacts; self-report is not a transcript.
- Python command capture supports process-group cleanup on POSIX. Native Windows process-tree cleanup has not been implemented; use WSL or existing host-native verification tools instead. macOS host integration and non-Codex discovery have not been demonstrated by the Linux packaging tests.

## Coordination translations

The [coordination procedure](coordination.md) adapts pstack's orchestration playbooks. Their Cursor tools map as follows:

| Upstream | In jfactory |
| --- | --- |
| Task tool with `environment: "cloud"` | `conductor workspace create` for an isolated worker; `conductor session create` only for an agent sharing that workspace |
| Task tool spawning a local worker or sub-coordinator that writes code | Not used. Writing units are Conductor workspaces from `coord.py launch`; the coordinator is the only orchestrator. Never the host's in-session subagent (Claude Code's Agent or Task tool) |
| Explorer and watcher subagents (`multi-phase-plan`, `autonomous-run`) | The host's read-only subagent, such as Claude Code's `Explore`, or a background shell watch |
| Resuming an agent | `conductor message create --session <id>`, used only to answer, redirect or correct scope, never to check liveness |
| Cursor dashboard liveness | `conductor session status`, `conductor session message --after`, pushed branches and `gh pr view` |
| `orch.ts` store, `units.tsv`, ledger, gates and `status.md` | One GitHub program issue managed by `scripts/coord.py`; the Bun CLI is not imported |
| `gt` stacks and the stacker role | Independent PRs from the base by default; `gh stack` or explicit stacked branches only when a dependency needs it, with merge order recorded |
| Babysitter and merge rules | Protected auto-merge under [auto-merge setup](auto-merge.md), plus coordinator verification at each head SHA |
| Ten-lane swarm, perf lanes and review video in the multi-PR plan | The unit's own [verification contract](verification.md); larger lane counts only on the owner's request |
| `check-plan.mjs`, `/goal`, `/loop` and cloud-sleeper ticks | Not imported. Use the host's scheduled wakeups or loop facility when present |
| Named Cursor models and `pstack-models.mdc` | [Model selection](models.md) by task tier and remaining usage, applied by the coordination tool's role policy (overridable in `.jfactory/coordination.json`) and checked against `conductor model` |

Upstream autonomous shipping and its preference to act without asking stay subordinate to jfactory's objective contract, product interview and the repository's authorization.

Use host-native visualization and progress conventions. Current user instructions and host constraints take precedence over upstream formatting and default tool choices.

## Interview and visual explanation methods

The bundled [grilling adapter](../skills/grilling/SKILL.md) includes Matt Pocock's full pinned method body, and [show-me](../skills/show-me/SKILL.md) includes HumanLayer's full pinned body. Loading either skill loads the actual method; an attribution link alone is insufficient. Their unchanged snapshots, licenses and receipts are in `vendor/mattpocock` and `vendor/humanlayer`; `scripts/check-upstream.py` checks these as well as pstack. Read the complete adapters directly when nested skills are not discovered or a Skill tool is absent. The installer-managed entry instructions provide that routing on every supported layout; native discovery remains host-dependent.

The adapters carry the owner's settled decisions and authorization forward, translate grilling's question formatting and delegation to the host, and invoke show-me proactively despite its original manual-only flag. Show-me puts essential jfactory integration before the long upstream examples and requires a full-file read. It also includes the full grilling method and integration for its conditional goal-settling branch; explaining a settled change needs no interview. Use supported previews or linked artifacts for cloud HTML rather than macOS `open`. Product facts and resulting decisions stay in consumer-owned canonical documents, never in these snapshots or adapters.

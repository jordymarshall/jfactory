---
name: agent-coordinator
description: Become the agent hub, the one agent the owner talks to, above every coordinator and worker. Registers this session as the hub, tells every coordinator, relays owner questions and answers, keeps a ledger of open items outside the chat, and hands over to a fresh session when the context grows large. Use for /agent-coordinator, "be the hub", "coordinate all the agents" or "you are the one I talk to".
---

# Agent coordinator: the hub

When this skill runs, this session becomes the **agent hub**. It is the highest-level agent. The owner talks to it, and to no other agent. It knows what every coordinator is doing and coordinates them. It does not write product code.

The hub's state lives in one pinned GitHub issue, "Agent hub" (label `jfactory-hub`), not in this chat. `scripts/hub.py` keeps that issue. Run it from the repository root (`python3 <this skill>/scripts/hub.py <command>`). It needs `gh`; the `conductor` CLI is optional.

## 1. Take over

1. Read the ledger first: `hub.py show`. If a hub already exists, its open items become yours.
2. Claim the hub and tell everyone: `hub.py claim --notify`. This records this session (from `CONDUCTOR_SESSION_ID`, or `--session`), tells the previous hub that it handed over, and messages every coordinator the routing rule. Without Conductor, the tool comments on each program issue instead.
3. Show the owner where things stand: `hub.py status`. Then end the turn.

A second trigger in another session takes over the same way. Before you relay anything, run `hub.py check`. If it exits 3, you are no longer the hub: stop relaying, and send anything open to the new hub.

New coordinators and workers learn the routing without a broadcast: `coord.py` reads the hub from the issue. Workers are told never to message the hub, and coordinators see the hub on every `sync`.

## 2. What comes in

Only coordinators message the hub. Each message starts with one tag:

| Tag | Meaning | What the hub does |
| --- | --- | --- |
| `QUESTION` | A decision that needs the owner | Add it to the ledger and ask the owner (section 3) |
| `BLOCKER` | Work stopped, and the coordinator cannot clear it | Clear it under the owner's standing authority, or ask the owner |
| `RISK` | Something may go wrong | Act or record; tell the owner only if it needs them |
| `MILESTONE` | Merged or live | Record; include it in the next status table |
| `DIGEST` | Routine progress, at most one every 30 minutes | Record; never forward one by one |

Workers report to their coordinator. When a worker messages you, run `hub.py route --from <its session> --reply`: it tells the worker to go through its coordinator.

## 3. What goes out to the owner

Message the owner only for:

- **A decision.** State the question, the options, your recommendation, and the default you apply if there is no answer. Record it: `hub.py ledger add --kind question --text "..." --from <coordinator> --owner <session that acts on it>`.
- **A blocker or risk you cannot clear.**
- **A status table,** on request or after a batch of milestones. Use `hub.py status`: each workstream, its status, a short summary and the ETA.

Decide everything else yourself, under the owner's standing authority, and record it as a `decision`.

When the owner answers, run `hub.py ledger resolve <id> --answer "..." --relay`. It sends the answer, with the reason, to the agent that owns the action. Confirm that the agent acted.

**A hold must reach the agent that owns the action.** Never tell the owner that something is held until you have run `hub.py ledger add --kind hold --owner <that session> --text "..."`. That command messages the agent. (On 2026-10-04 a PR merged while the hub told the owner it was held.)

## 4. Work no single coordinator owns

Settle these across programs: the order of the shared test account lease, CI capacity and the queue, model usage and fallbacks, the release cadence, and units that edit the same files. Use the coordinators' own tools (`coord.py`, the lease's `status`) to see the facts. Ask the owning coordinator to act.

## 5. Keep your context small

Your context window grows with every message. Keep it small:

- **State lives in the ledger, not in the chat.** Re-read `hub.py show` instead of scrolling back. Record each question, decision, owner and ETA when it happens.
- **Delegate reading.** Use read-only subagents (in Claude Code, `Explore`) to read CI logs, PR checks and transcripts, and return a short summary. Do not paste long logs into your own context.
- **Hand over before the context is full.** Hand over when the host warns about the context, or after about 150 inbound messages or 8 hours, whichever comes first. Run `hub.py handoff --create --workspace <your workspace> --reason "context"` (or start a session yourself and pass `--to <session>`). The new session reads the ledger and takes over, and the coordinators are told. Then tell the owner the new session's link, and stop.

## 6. Hosts

This works in Claude Code and Codex. Setup installs it in the repository and in your global skills (`~/.claude/skills/agent-coordinator`, and `$CODEX_HOME/skills/agent-coordinator`, by default `~/.codex/skills`), so it works in any repository that runs jfactory. With Conductor, messages go to sessions. Without Conductor, the hub and coordinators use comments on the hub issue and the program issues.

Write every message in ASD-STE100 style: short sentences, one point each, active voice, common words, and every technical term explained the first time.

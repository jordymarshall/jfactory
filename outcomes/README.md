# Outcomes

The business level for jfactory itself. The product brief in [AGENTS.md](../AGENTS.md#product-brief) and the owner interview in [the setup record](../.jfactory/setup.md#owner-interview) are the owner's words; this file only arranges them so verifiers can judge whether a change serves them.

## Customer

The owner first, then any developer who points their coding agent at this repository. They want agents to work for hours without being told "keep going", without claiming done unproven, without every PR needing a human review, and without chaos when many run at once.

## Outcomes and measures

In the owner's order:

| Outcome | How it is measured | Source |
| --- | --- | --- |
| Setup plus a first feature reach a verified, merged PR with the owner only answering product questions | Owner interventions per adoption (count of non-product messages the owner had to send) | AGENTS.md success measure 1 |
| Agent PRs merge without owner fixes | Share of agent PRs merged with no owner commit or requested change | AGENTS.md success measure 2 |
| Blinded cross-model evals show it helps | Judge scores for jfactory against a baseline on `evals/scenarios.md` tasks | AGENTS.md success measure 3 |

## Non-goals

- Anything that works for only one repository or product: product facts belong in each project's files, never in the bundle.
- Releasing production on its own.

## Jobs to be done

| Job | Document | Serves outcome |
| --- | --- | --- |
| Set up a repository | [set-up-a-repository.md](set-up-a-repository.md) | 1 |
| Deliver an objective without babysitting | [deliver-an-objective.md](deliver-an-objective.md) | 1, 2 |
| Merge verified changes safely | [merge-verified-changes.md](merge-verified-changes.md) | 2 |
| Run many agents in parallel | [run-many-agents.md](run-many-agents.md) | 1, 2 |

## How the levels fit together

- **This file:** why jfactory exists and what counts as success. Changes by owner decision.
- **Standards** ([.jfactory/standards.md](../.jfactory/standards.md)): what good looks like everywhere.
- **Job documents** (this folder): the standing goals of one thing users do, each with how it is proven.
- **Work items** (the objective in a `jfactory-objective` issue or the PR): the criteria for one change, each naming the job goal it adds, changes or relies on.

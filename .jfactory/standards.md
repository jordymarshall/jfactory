# Standards map

The source of truth for each quality dimension of jfactory itself. Verifiers check every change against the rows it touches and name the documents with `verify_plan.py verdict --standards <path>`. Created from [the template](../skills/jfactory/templates/standards.md).

| Dimension | Source of truth | How changes are checked |
| --- | --- | --- |
| Product goals and customer | `outcomes/README.md`, `AGENTS.md#product-brief` and the owner interview in `.jfactory/setup.md#owner-interview` | Verifier: the change removes one of the four pains or supports a success measure, and stays out of the non-goals (nothing product-specific in the bundle) |
| Brand, voice and copy | `skills/jfactory/vendor/pstack/skills/unslop/SKILL.md` | Verifier: changed instructions and README text are plain, specific and free of filler; a model trial for behavior changes |
| Visual design system | none: jfactory has no product interface; the UX helper's dashboard is a test harness, covered by `tests/dashboard_smoke.py` | CI dashboard and browser smokes |
| UX principles | `README.md` (the owner's walkthrough) and `skills/jfactory/references/setup.md` | Verifier: the owner only answers product questions; a new step or prompt must say why the owner needs it |
| Accessibility | none: no user interface beyond generated Markdown and a local test dashboard (owner, 2026-09-30) | Not applicable |
| Performance and scale | `skills/jfactory/references/mapping.md#keep-the-whole-suite-fast` for consumer suites; none for the scripts themselves | Verifier; `tests/` run in under two minutes in CI |
| Security, privacy and data | `skills/jfactory/references/verification.md` (gate design: base-branch scripts, trusted verdicts, no PR code in the pull_request_target workflow) and `skills/jfactory/references/compatibility.md` | Verifier review of gate and workflow changes; `tests/test_verify_plan.py` |
| Engineering conventions | `AGENTS.md#agent-instructions` | CI `checks`: unit tests, `check-upstream.py`, link checks, browser and dashboard smokes |
| Definition of done | `skills/jfactory/references/delivery.md`, `skills/jfactory/templates/objective.md` and each job's goals in `outcomes/` | Verifier: every criterion at its scope, evidence limits stated in the PR |

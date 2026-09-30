# Standards map

The source of truth for each quality dimension. Verifiers check every change against the rows it touches and name the documents with `verify_plan.py verdict --standards <path>`. Edits to these documents always get an independent review. Keep one canonical document per fact; mark older documents superseded rather than leaving them to compete.

Name each source as a backticked repository path (`docs/brand.md`, or `docs/brand.md#voice` for a section). When a dimension has no document yet, write `none` and the owner's reason, for example "none: owner decision 2026-01-10, no performance budget until launch". `setup_check.py` fails when a named source does not exist.

| Dimension | Source of truth | How changes are checked |
| --- | --- | --- |
| Product goals and customer | `REPLACE: product brief or PRD` | Verifier: does the change serve the stated customer and outcome, and stay out of the non-goals? |
| Brand, voice and copy | `REPLACE: brand or writing guide` | Verifier: judgment rubric for every changed user-facing word |
| Visual design system | `REPLACE: design tokens or style guide` | Verifier: reviewed screenshots against the tokens; screenshot comparisons for stable screens |
| UX principles | `REPLACE: interaction principles or decision record` | Verifier: drives the changed journey against the principles |
| Accessibility | `REPLACE: stated level (for example WCAG 2.2 AA) and the automated check` | CI accessibility scan, plus keyboard and focus review of changed screens |
| Performance and scale | `REPLACE: budgets, or none and why` | CI timings; deliberate scale journeys |
| Security, privacy and data | `REPLACE: policy or requirements` | Verifier: access boundaries and data handling in the diff |
| Engineering conventions | `REPLACE: conventions document and lint/type config` | CI lint, type and unit checks |
| Definition of done | `REPLACE: where acceptance criteria live` | Verifier: every criterion at its required scope |

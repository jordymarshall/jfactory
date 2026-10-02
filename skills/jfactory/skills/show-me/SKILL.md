---
name: show-me
description: Explain jfactory changes, PRs, review feedback and product or technical choices visually so the owner can understand and respond. Use proactively when a change or decision needs explanation or feedback.
---

Read HumanLayer's unchanged [show-me skill](../../vendor/humanlayer/skills/show-me/SKILL.md). Its original is manual-only; this jfactory adapter invokes the method proactively for changes, PR explanations, feedback and choices the owner needs to understand.

Choose the smallest useful view: a before/after diff, file or call tree, diagram, or focused HTML comparison. Ground it in the actual change and canonical goals; label proposed behavior and unknowns. Put it beside the decision or feedback it supports, with brief text explaining the consequence. For a PR, include a useful view in its description or linked review artifact when the change needs one. Use a short textual comparison when no visual adds clarity; do not manufacture UI screenshots for CLI or instruction changes.

Use host-supported rendering and sharing. For HTML in a cloud workspace, use a supported preview or linked artifact instead of blindly running macOS `open`. Follow the repository's artifact conventions and keep private data out of shared artifacts. A sketch explains a proposal; it is not observed application evidence, independent verification or owner acceptance. Record resulting decisions through [documentation reconciliation](../../references/documentation.md) and use [grilling](../grilling/SKILL.md) when feedback exposes unresolved goals.

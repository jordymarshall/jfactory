# pstack upstream source

Official source: https://github.com/cursor/plugins/tree/ecc249f1e306fc64ddf83c7bed16cacf7c2239db/pstack

Version 0.15.5, commit `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`, imported September 27, 2026. Copyright Lauren Tan 2026, MIT; see LICENSE. `upstream.json` lists every imported upstream file and its SHA-256. Original bytes and paths are preserved. This directory is source material, outside automatic skill discovery, not an installed Cursor plugin.

The supported entry point is [jfactory](../../SKILL.md). It reads these originals directly. From poteto-mode, only the eval, orchestrate, multi-phase-plan, prototype, autonomous-run, session-pickup and pause-safely playbooks are imported. Sticky Poteto Mode, its scripts (including the orchestration CLI and plan checker), autonomous shipping, Cursor agents and automation are not activated. The selected skills include investigation, teaching, architecture sketching, verification creation/maintenance, review, TDD, eval dependencies, decision trails and supporting principles. The coordination playbooks and their dependencies were added September 28, 2026 from the same pinned commit.

Skill directories were installed with the Codex skill-installer helper using `--repo cursor/plugins --ref ecc249f1e306fc64ddf83c7bed16cacf7c2239db --dest .agents/vendor/pstack/skills --path pstack/skills/<name> ...`. LICENSE, the poteto-mode playbooks and the files added September 28 were copied from the same pinned checkout and byte-compared. The receipt is `upstream.json`.

Check integrity from the repository root:

```sh
python3 skills/jfactory/scripts/check-upstream.py
```

For updates, download the chosen new commit into a separate scratch directory with the same installer. Review the upstream diff, dependencies and compatibility mappings before replacing this snapshot. Regenerate the receipt from the reviewed upstream bytes, rerun integrity and applicable behavior checks, and update this source record. Never edit vendor files to customize behavior or silently follow upstream main. Put necessary local adaptations in the adapter, and keep product choices in the product workflow.

# Changelog

## 0.1.0 - 2026-07-16

- Reframed Timeless as an evidence-led governor for reusable Agent workflows rather than a wrapper for ordinary tasks.
- Reduced the runtime to one lifecycle decision: keep, narrow, revise, or retire from observed outcome and cost.
- Added a standard-library Governor CLI that freezes a task, Skill, rubric, starting workspace, and cost rule; runs an optional matched Codex screen; exports a condition-label-blind review packet; and records a provisional lifecycle decision.
- Published the complete privacy-safe self-audit bundle: 4 cases, 24 opaque outputs, 72 score rows, 36 blind preferences, grader notes, mapping, and checksums.
- Added a no-credit `self-audit` command that verifies the full bundle and recomputes the product decision from raw rows.
- Removed the synthetic Demo and aggregate-only replay because neither demonstrated a real product decision.
- Added sealed captures and final workspaces, mode-aware tree hashes, non-finite-number rejection, sensitive-file rejection, separate temporary execution roots, condition-blind artifact manifests, and actionable malformed-input errors.
- Added an optional frozen external evaluator whose result enters blind review and which is rejected if it changes the candidate workspace.
- Expanded the contract suite from 13 to 24 tests covering integrity, isolation limits, credential rejection, symlink rejection, evaluator containment, evidence completeness, strict verdicts, provisional decisions, and the complete self-audit.
- Removed fixed tiers, mandatory process narration, broad checklists, and the unchanged-build three-pass ritual after formative blind review showed added burden and no outcome advantage.
- Removed the unvalidated portable workspace, registries, schemas, validators, and continuity quickstart from the initial product.
- Removed the unrelated event-release fixture after it proved only its own six checks, not the value of Timeless.
- Added explicit matched-baseline, negative-control, cost, blinding, evaluator-integrity, and harm-reporting rules.
- Disabled implicit invocation so ordinary work stays with the host Agent.
- Preserved the human and engineering philosophy in `docs/PHILOSOPHY.md` without loading it into Agent runtime.
- Made exact delivered-artifact inspection explicit: successful generation, source checks, input hashes, and green commands are upstream evidence, not proof that the user-facing output is complete.
- Added a control-design rule: when an existing instruction was bypassed, repair its trigger, acceptance gate, or observability instead of duplicating the instruction.
- Updated English and Traditional Chinese documentation, Codex and Claude Code installation, GPT-5.6 usage, evidence limits, and the judge testing path.

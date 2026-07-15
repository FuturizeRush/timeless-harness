---
name: timeless-harness
description: Review a reusable Agent workflow, Skill, instruction, memory, evaluator, or repair rule against observed outcomes and cost. Use after counterevidence, repeated failure, A/B oscillation, scope drift, or suspected process burden, or when the user requests a Timeless self-review. Never use it as a wrapper for ordinary task execution.
---

# Timeless Harness

Use Timeless only to govern reusable Agent behavior. Never run it inside routine writing, coding, debugging, research, or review.

1. State the exact behavior the mechanism claims to improve and the evidence that supports or contradicts it. Prefer a matched strong native baseline. Treat the exact delivered artifact or current interface as the real surface. A generator receipt, input hash, source file, successful command, or passing check is upstream evidence only. Open, play, parse, or otherwise inspect the delivered output and verify semantic completeness and failure-prone boundaries. Count latency, tokens, extra files, narration, false claims, and new errors as cost.
2. Precommit the comparison, stopping rule, and acceptable cost before seeing outputs. Decide `keep | narrow | revise | retire` only at the strength the evidence supports. A single pair is a provisional screen, not a general verdict. A tie with more process is a loss. Do not preserve a rule because it sounds wise or took effort to create.
3. If failure repeats or alternates between A and B, change the governing hypothesis, goal, evaluator, search method, feedback, interface, source of truth, or rule. Do not add stages or repeat the same patch. When attribution matters, hold the baseline, evaluator, and surrounding boundary fixed while changing one causal hypothesis.
4. Close the governance round with the outcome, decisive evidence, correction or uncertainty, and next controlled test. Preserve only the smallest falsifiable correction that should alter a later move. Prefer encoding it in the artifact or acceptance gate. If an existing rule was not executed, repair its trigger, gate, or observability instead of duplicating the wording. A saved rule needs a trigger, scope, evidence and counterevidence, and a recheck or retirement condition. If evidence does not justify a reusable rule, save none.

Load [Truth and Causal Repair](references/truth-repair.md) only when disputed evidence blocks the lifecycle decision. Load [Decompose and Reconstruct](references/decompose-reconstruct.md) only when repeated failure requires a new causal model. Load [Review and Knowledge Distillation](references/learning-loop.md) only after evidence supports changing a reusable rule. Do not load them by default.

Return only: evidence status, provisional or final lifecycle decision, decisive evidence, smallest change, claims still unsupported, and next controlled test. The test must target the retained behavior and must not reuse a case already known to have no discriminating headroom. Do not design a replacement workflow unless the evidence requires one.

Do not invent defects, causality, certainty, thresholds, templates, or lessons to make governance appear useful. Apply this rule to Timeless itself.

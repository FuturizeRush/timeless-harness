# Review and Knowledge Distillation

[SKILL.md](../SKILL.md) is canonical. Load this reference when a completed round may change future behavior.

## Close the round before generalizing it

A round is a completed user-facing cycle or material state transition, not every tool call or patch. Record:

```text
Outcome:
Decisive evidence:
Correction or uncertainty:
Next time:
```

Do not convert activity into success. Do not rewrite an old observation after later evidence changes the explanation. Append the correction and preserve the contradiction that taught it.

## Choose where the lesson belongs

Use one disposition:

1. `discard` when the observation is incidental or would not change a later move;
2. `encode in artifact` when a test, interface, source of truth, script, or project instruction can carry it;
3. `add or revise scoped rule` when a later Agent needs a decision cue that cannot yet be encoded better;
4. `retire rule` when current evidence makes it stale, redundant, harmful, or uneconomic.

Prefer the artifact. Memory is a prior, not authority.

If the failed behavior was already prohibited by an existing rule, do not add a louder copy of the same rule. Find why the rule did not change the move. Repair the trigger, acceptance gate, tool output, observability, or handoff that allowed the work to bypass it. A rule that exists but is not invoked is not an effective control.

## Keep a rule falsifiable

The smallest useful rule contains:

```text
Trigger:
Action:
Scope:
Evidence and counterevidence:
Recheck or retire when:
```

Do not generalize beyond the evidence. On a matching task, state what decision the rule should change, compare the expected benefit with the observed result and cost, then `keep | narrow | revise | retire` it. Current evidence wins.

An unused note is not demonstrated learning. A checker can prove that fields and lifecycle links exist; it cannot prove that a rule caused a better outcome. Use a matched comparison for that claim.

## Privacy boundary

Preserve the smallest transferable mechanism. Do not store credentials, personal identifiers, private transcript text, proprietary code, or unnecessary incident details.

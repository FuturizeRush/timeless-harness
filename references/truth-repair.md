# Truth and Causal Repair

Load this reference when a consequential verdict is disputed, evidence conflicts, several defenses protect one outcome, or a system claims to have recovered.

## Bind the claim to evidence

Write the exact claim and the current surface that could settle it.

```text
Claim and type:
Real surface:
Supporting evidence:
Disconfirming evidence:
Evaluator assumptions:
Residual uncertainty:
```

Do not use one evidence type to settle another claim type. A passing test cannot settle user experience by itself. A metric cannot settle a value conflict. A plausible mechanism cannot replace observation.

The exact delivered artifact is the real surface for a delivery claim. A successful build, render, request, source inspection, or input hash proves only that an upstream step ran. Open or play the final file in its consumption context. For generated documents, media, or multi-surface releases, verify semantic completeness plus failure-prone boundaries such as the first state, last state, transitions, pages, links, and synchronized outputs. A text hash cannot prove that synthesized speech actually contains the full text.

Test three corruptions:

- **False success:** activity, green checks, retries, fallbacks, persuasive reports, or polished output exist without the intended outcome.
- **False failure:** a stale evaluator, invalid input, old version, inherited assumption, or failed search method is mistaken for current impossibility.
- **Unsupported certainty:** the conclusion is broader than the sample, evidence, causal model, or domain permits.

Separate production from evaluation. Finish the candidate, reopen the raw artifact or current surface, restate the preferred conclusion as a neutral falsifiable question, and inspect disconfirming evidence before defending the earlier answer. Use another reviewer only when its expected information gain justifies the cost.

## Review the important whole three ways

For an important deliverable, perform three complete reviews of the same unchanged artifact:

1. **Requirements and outcome:** Does the whole result satisfy the real finish and every material constraint?
2. **Implementation and evidence:** Do the current artifact, runtime, data, or source actually support each completion claim?
3. **User and adversarial failure:** Is it understandable and usable, and which plausible failure could still change the verdict?

If a pass finds a defect, repair it and restart these reviews on the new final artifact. These are three complete perspectives. They are not three independent defenses and do not justify repeating an identical test without new information. Never carry a release verdict from an older artifact onto a newly rendered or edited one.

## Design distinct defenses

Repeated review and layered protection solve different problems. For a costly hazard, map:

```text
protected outcome and hazard
prevent -> detect -> contain -> recover
hole and observable signal in each layer
shared assumptions or common-mode cause
response and residual risk
```

Retain a defense only when it covers a distinct failure mode, produces an observable signal, and leads to a defined response. More layers are not automatically safer. Checks that share one source, model, evaluator, environment, or assumption may fail together.

## Repair at the failing level

Locate the contradiction in the goal, causal model, search method, action, context, interface, feedback, evaluator, or learned rule. Repair the earliest evidence-supported leverage point worth changing, then rerun the check that exposed it and inspect an adjacent boundary.

A retry, exception handler, fallback, optimistic status, or polished explanation is not self-repair. Recovery is credible only when the contradiction is detected, the cause is changed, the exposing evidence is rerun, the real outcome recovers, and recurrence becomes less likely.

Bound retries. Continue only when the next attempt can distinguish explanations or improve the real outcome. Leave uncertainty visible rather than inventing a cause.

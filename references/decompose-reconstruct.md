# Decompose and Reconstruct

Load this reference when a result has several dependent surfaces, the system is opaque, or the same failure returns. Build only enough of the model to choose and verify the next useful move.

## Work backward from the judged finish

Map:

```text
judged finish -> acceptance conditions -> decisive proof
              -> necessary sub-outcomes -> dependencies -> current bottleneck
```

Name who or what judges the result, its validity window, and what must not be sacrificed. Distinguish requirements from preferences and proxy metrics. Bind each material condition to an artifact, observation, or decision that could prove it. If no proof surface exists, treat that as a design gap.

Recurse only until a leaf can be produced by one coherent action and checked directly. Then work forward, composing evidence as the leaves compose into the result. Do not call a parent outcome complete merely because its activities ran.

Stop decomposing when another split would not reveal a real dependency, reduce uncertainty, create a separately verifiable outcome, or change the next move.

## Reconstruct a repeated failure

Separate what was observed from what was inferred. Trace backward from the effect through outputs, transformations, state, inputs, dependencies, interfaces, and necessary conditions. Mark uncertain links and keep at least one materially different explanation when the evidence permits it.

Choose a probe that makes the competing explanations predict different outcomes. Before acting, state the prediction. After acting, compare the observed result with it and preserve anomalies instead of explaining them away.

When causal attribution matters, keep three anchors fixed while moving one hypothesis:

1. **Baseline:** a known current or known-good state, representative input, and version.
2. **Evaluator:** the same observation or acceptance check.
3. **Surrounding boundary:** the environment, dependencies, configuration, and adjacent behavior not under test.

Move one **atomic slice**: one reason to change, one predicted effect, and one rollback boundary. The implementation may span several files. If another variable changed, record the confounder and do not claim clean causality.

## Decouple without fragmenting

Separate responsibilities that have independent reasons to change, fail, scale, or be verified. Make inputs, outputs, state ownership, failure semantics, and feedback visible. Keep behavior together when splitting would create more synchronization, handoffs, latency, or ambiguity than value.

Judge decoupling by reduced change propagation and clearer diagnosis, not by component count.

## Evidence boundary

- A reconstructed model remains an inference until its predictions survive current evidence.
- Similar behavior does not prove identical mechanisms.
- One successful probe supports only the conditions it exercised.
- Stop when the model is sufficient to decide or act honestly. Exhaustive knowledge is not the deliverable.
- Preserve the transferable method and boundary, not private inputs, credentials, identifiers, proprietary implementation, or incidental history.

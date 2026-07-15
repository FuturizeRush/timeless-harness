# Evaluation and Self-Correction

Timeless Harness must earn its place against a capable native Agent. A polished framework is not evidence of improvement.

## Current verdict

| Claim | Status |
| --- | --- |
| The old Timeless general wrapper should be retired | Supported by the published evaluation |
| The evidence bundle reproduces the reported aggregate | Verified by the local self-audit command |
| The new narrow Governor works as implemented | Covered by contract tests |
| The new Governor improves unseen Agent tasks | Unresolved |

`v0.1.0` is therefore an experimental governance tool, not a claim of general superiority.

## Published evaluation

The pre-release study compared a strong native Agent baseline with an older Timeless wrapper on four synthetic task types:

1. incident response;
2. mixed-evidence research;
3. interface repair and polish;
4. a simple constrained rewrite.

Each task had three paired trials. The published bundle contains:

- 4 fixed case files;
- 12 paired trials;
- 24 outputs with opaque IDs;
- 3 blind pair-order manifests;
- 72 score rows across six rubric dimensions;
- 36 pair preferences with reasons;
- 3 grader note files;
- the condition mapping revealed after scoring;
- SHA-256 hashes for every evidence file.

All evidence is in [`examples/self-audit`](examples/self-audit).

### Recomputed result

| Measure | Native baseline | Old Timeless wrapper |
| --- | ---: | ---: |
| Blind preference wins | 19 | 6 |
| Mean dimension score, 0 to 4 | 3.991 | 3.889 |
| Fatal-omission flags | 0 | 0 |
| Unnecessary-process flags | 0 | 9 |

There were 11 ties.

The recurring regression was an arbitrary three-pass unchanged-build release gate in the old Timeless incident answers. It added ceremony without improving the task result. The product decision was to retire the tested general wrapper.

### Reproduce the aggregate

```bash
RESULT="$(mktemp -d)/timeless-self-audit"
python3 tools/harness_governor.py self-audit \
  --evidence examples/self-audit \
  --output "$RESULT"
```

The command first verifies all 44 published checksums. It then validates the case mapping, output IDs, CSV schemas, row completeness, score ranges, preference winners, and expected counts before recomputing the result from the raw rows.

## Evidence boundary

The bundle supports inspection and deterministic recomputation of the published text, scores, preference counts, and process flags.

It does not independently prove:

- model identity;
- prompt delivery;
- grader independence;
- execution time or token cost;
- pre-registration;
- generalization beyond the four tasks and the old wrapper represented by these files.

The recovered package contained no precommitted lifecycle threshold. The retirement is therefore described as a transparent post-evaluation product decision, not a pre-registered statistical verdict.

Solver metadata was excluded because it contained local paths and was not needed to recompute the result. The cases, outputs, rubric, mapping, scores, preferences, and notes are unchanged. The three grader manifests changed only from an absolute temporary path to bundle-relative wording. These transformations are recorded in the bundle manifest.

## What changed because of the result

The failed design was not renamed and kept. Its burden was removed:

- no implicit invocation for ordinary work;
- no fixed universal work stages;
- no mandatory three-pass ritual;
- no persistent state, memory, log, or registry templates;
- no claim that Timeless makes every task better;
- no synthetic Demo with a prewritten answer.

The remaining Skill is a small lifecycle policy. The CLI exists to make prospective comparisons more inspectable.

## Current Governor checks

The test suite covers these contracts:

- task, Skill, rubric, workspace, evaluator, and cost rule are frozen;
- non-finite cost limits and timeouts are rejected;
- file contents, file modes, and empty directories affect workspace hashes;
- common credential files and workspace symlinks are rejected;
- live model calls require explicit `--allow-live`;
- `danger-full-access` is rejected;
- conditions use separate random temporary roots that do not coexist;
- captures and final workspaces are sealed and rechecked before blind review and decision;
- missing or malformed telemetry cannot enter blind review;
- candidates that create symlinks are rejected before persistence;
- optional evaluators receive detached copies without Codex authentication or capture paths, their output enters blind review, and evaluator mutation fails the run;
- artifact manifests are condition-label blind;
- malformed manifests and verdicts return actionable errors;
- one matched pair is labeled a provisional candidate, never a final verdict;
- the complete public self-audit recomputes the published result.

Run all tests:

```bash
python3 -m unittest discover -s tests -v
```

## Remaining limitations

The local runner deliberately stays narrow:

- Separate random temporary roots reduce accidental cross-condition reading, but they are not operating-system read isolation.
- Hash seals detect mismatches. They are not signatures and cannot stop a person from replacing every mutable file together.
- Redaction and credential-file rejection reduce exposure. They do not make untrusted code safe.
- Artifact manifests show what files exist and whether they changed. A human or external evaluator must still decide whether the artifacts are good.
- Tokens and wall time are useful costs, not a complete measure of maintenance or cognitive burden.
- One pair can reveal a likely regression, but final lifecycle decisions need repeated representative cases and a precommitted stopping rule.

## Next validation

The next study should test the current narrow Governor, not the retired wrapper.

Before running it:

1. choose several real but privacy-safe reusable Skills with enough room to improve;
2. freeze the baseline, treatment, cases, evaluator, cost limit, and stopping rule;
3. use the same model, reasoning effort, sandbox, timeout, and starting artifacts;
4. keep condition identity hidden from quality reviewers;
5. measure quality, new errors, tokens, time, and extra process;
6. publish both positive and negative results;
7. keep, narrow, revise, or retire the Governor itself from those results.

Until that prospective study exists, the honest conclusion remains:

**The old wrapper failed. The new Governor is testable, but not yet proven better.**

# Timeless self-audit evidence

This bundle contains the scored outputs behind the decision to retire the original Timeless general wrapper. It lets reviewers inspect every case, anonymous answer, score, preference, and grader note used in that decision.

## What is here

- `cases/`: four fixed tasks covering incident response, research, interface repair, and concise writing
- `outputs/`: 24 answers identified only by opaque IDs
- `graders/`: the pair order shown to each of three grader runs
- `grades/`: 72 score rows, 36 pair preferences, and three sets of notes
- `mapping.md`: the condition mapping revealed after scoring
- `rubric.md`: the six scoring dimensions and case-specific anchors
- `manifest.json`: machine-readable scope, counts, results, transformations, and evidence limits
- `SHA256SUMS`: hashes for every other file in this bundle

No solver metadata is included. The original `meta/` directory contained local paths, was not needed for score aggregation, and was excluded for privacy. The cases, outputs, rubric, mapping, scores, preferences, and notes were copied without content changes. The three grader manifests were changed only to replace an absolute temporary path with bundle-relative paths.

## Verify integrity

From this directory on macOS:

```bash
shasum -a 256 -c SHA256SUMS
```

`SHA256SUMS` establishes the integrity of this published bundle. It does not prove when or how the answers and grades were produced.

## Recomputed result

The mapping resolves each anonymous winner to one of two tested conditions:

| Result across 36 preferences | Count |
| --- | ---: |
| Native baseline wins | 19 |
| Timeless wrapper wins | 6 |
| Ties | 11 |

Across all six rubric dimensions and three grader result sets, the baseline mean is `3.991` and the Timeless mean is `3.889`. Neither condition has a `fatal_omission` flag. The `unnecessary_process` flag appears `0` times for baseline outputs and `9` times for Timeless outputs.

This supports retiring the tested general wrapper. It does not establish that the narrower Timeless Governor is better. The Governor still needs prospective matched evaluation against a strong native baseline.

## Evidence boundary

The files can reproduce the published aggregate and expose the scored text for inspection. They cannot independently establish model identity, prompt delivery, grader independence, execution time, token cost, or pre-registration. The recovered artifacts contain no precommitted lifecycle threshold, so the retirement decision is a transparent post-evaluation product decision, not a claimed pre-registered statistical verdict.

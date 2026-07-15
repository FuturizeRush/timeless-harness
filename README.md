# Timeless Harness

[English](README.md) | [繁體中文](README.zh-TW.md)

> An evidence-led governor for reusable Agent workflows.

![Timeless Harness](assets/timeless-harness-thumbnail.png)

Modern Agents already plan, code, research, test, and review well. Adding a workflow can improve them. It can also slow them down, create rituals, and introduce new mistakes.

Timeless Harness asks one question:

**Does this reusable Agent workflow still earn its cost?**

It governs Skills, instructions, memory rules, evaluators, and repair methods. It does not wrap ordinary work. The native Agent works first. Timeless is used only when the reusable method itself needs review.

## The product in one minute

Timeless has two parts:

- [`SKILL.md`](SKILL.md) gives an Agent a small lifecycle policy: `keep | narrow | revise | retire | unresolved`.
- [`tools/harness_governor.py`](tools/harness_governor.py) creates a matched native-versus-workflow screen, seals the evidence, prepares a blind review, measures cost, and returns a provisional lifecycle candidate.

```text
Reusable workflow makes a claim
              |
freeze task, rubric, workspace, model, and cost rule
              |
run native baseline and workflow treatment separately
              |
blind review final answers, artifact manifests, and evaluator results
              |
combine quality with tokens and time
              |
keep | narrow | revise | retire | unresolved
```

A single pair is only a screen. It is not proof. A final lifecycle decision needs repeated representative cases and a stopping rule chosen before results are seen.

## Proof through self-correction

The first Timeless prototype wrapped routine Agent work. Its own evaluation showed that this was worse than leaving a strong model alone.

The complete, privacy-safe evidence is published in [`examples/self-audit`](examples/self-audit). It includes 4 tasks, 24 opaque outputs, 72 score rows, 36 blind preferences, grader notes, the revealed mapping, and checksums.

Recompute it without an API key, network access, or model credits:

```bash
RESULT="$(mktemp -d)/timeless-self-audit"
python3 tools/harness_governor.py self-audit \
  --evidence examples/self-audit \
  --output "$RESULT"
```

Expected output:

```text
EVIDENCE: VERIFIED 44 FILES
PREFERENCES: NATIVE 19 | TIMELESS 6 | TIES 11
MEAN SCORE: NATIVE 3.991 | TIMELESS 3.889
FATAL OMISSIONS: NATIVE 0 | TIMELESS 0
UNNECESSARY PROCESS: NATIVE 0 | TIMELESS 9
DECISION: RETIRE TESTED GENERAL WRAPPER
CURRENT GOVERNOR: UNRESOLVED
```

The recurring failure was concrete. The old wrapper added an arbitrary three-pass release ritual without improving the answer. Timeless therefore removed routine invocation, fixed process stages, persistent workspace ceremony, and general superiority claims.

This proves that the evidence can reproduce the decision to retire the tested old wrapper. It does not prove that the new narrow Governor is better. That claim remains unresolved. See [`EVALUATION.md`](EVALUATION.md).

Timeless did not discard truth-seeking, causal repair, whole-artifact finishing, or learning. It changed their role. They remain optional depth for disputed evidence, repeated failure, and durable learning decisions instead of becoming mandatory ceremony around every task. The Governor keeps those reusable rules accountable to observed value and cost.

## Why this is not another workflow pack

| Product | Main job |
| --- | --- |
| Codex or Claude Code | Do the task |
| Workflow packs such as Superpowers | Add reusable ways to do tasks |
| Eval frameworks | Measure outputs |
| Timeless Harness | Govern whether a reusable workflow should survive, change, or be removed |

Timeless can use an evaluator, but it is not an eval framework. Its concern is the lifecycle of instruction debt around an increasingly capable Agent.

## Judge test path

Requirements: Git and Python 3.10 or newer. The self-audit and test suite use only the Python standard library.

```bash
git clone --branch v0.1.0 --depth 1 \
  https://github.com/FuturizeRush/timeless-harness.git
cd timeless-harness

RESULT="$(mktemp -d)/timeless-self-audit"
python3 tools/harness_governor.py self-audit \
  --evidence examples/self-audit \
  --output "$RESULT"

python3 -m unittest discover -s tests -v
```

This path makes no model call and needs no credentials.

## Install the Skill

Both commands install the pinned `v0.1.0` release and refuse to overwrite an existing destination.

### Codex

```bash
(
  set -eu
  VERSION=v0.1.0
  DEST="${CODEX_HOME:-$HOME/.codex}/skills/timeless-harness"
  [ ! -e "$DEST" ] || { printf 'Refusing to overwrite: %s\n' "$DEST" >&2; exit 1; }
  mkdir -p "$(dirname "$DEST")"
  trap 'rm -rf "$DEST"' EXIT HUP INT TERM
  git clone --filter=blob:none --no-checkout \
    https://github.com/FuturizeRush/timeless-harness.git "$DEST"
  git -C "$DEST" checkout --quiet --detach "$VERSION^{commit}"
  trap - EXIT HUP INT TERM
)
```

Start a new Codex session, then say:

```text
Use $timeless-harness to review whether this reusable workflow should be kept, narrowed, revised, or retired.
```

### Claude Code

```bash
(
  set -eu
  VERSION=v0.1.0
  DEST="$HOME/.claude/skills/timeless-harness"
  [ ! -e "$DEST" ] || { printf 'Refusing to overwrite: %s\n' "$DEST" >&2; exit 1; }
  mkdir -p "$(dirname "$DEST")"
  trap 'rm -rf "$DEST"' EXIT HUP INT TERM
  git clone --filter=blob:none --no-checkout \
    https://github.com/FuturizeRush/timeless-harness.git "$DEST"
  git -C "$DEST" checkout --quiet --detach "$VERSION^{commit}"
  trap - EXIT HUP INT TERM
)
```

Start a new Claude Code session, then invoke:

```text
/timeless-harness Review whether this reusable workflow should be kept, narrowed, revised, or retired.
```

Review any third-party Skill before consequential use.

## Run a prospective screen with Codex

The live path is optional. It spends two Codex runs. Use only trusted local inputs.

Prepare a task, the Skill under review, a rubric, and one starting workspace:

```bash
python3 tools/harness_governor.py prepare \
  --task /path/to/TASK.md \
  --skill /path/to/SKILL.md \
  --rubric /path/to/RUBRIC.md \
  --source /path/to/start-workspace \
  --output /tmp/timeless-experiment \
  --max-cost-ratio 1.25
```

An optional trusted executable can evaluate each final workspace:

```text
--evaluator /path/to/read-only-evaluator
```

The evaluator receives the candidate workspace as its current directory. If it changes the workspace, the run fails.

Run the matched pair:

```bash
python3 tools/harness_governor.py run \
  --experiment /tmp/timeless-experiment \
  --model gpt-5.6-sol \
  --reasoning ultra \
  --sandbox workspace-write \
  --run-id screen-1 \
  --allow-live
```

Prepare the blind packet:

```bash
python3 tools/harness_governor.py blind \
  --experiment /tmp/timeless-experiment \
  --run-id screen-1
```

Give only `runs/screen-1/grader/` to a reviewer. Keep `private/` hidden. After the reviewer completes a verdict JSON:

```bash
python3 tools/harness_governor.py decide \
  --experiment /tmp/timeless-experiment \
  --run-id screen-1 \
  --verdict /path/to/verdict.json
```

The terminal labels the result `PROVISIONAL SCREEN` and `CANDIDATE`. It never presents one pair as a final lifecycle verdict.

## Safety and evidence limits

- Live calls require `--allow-live`, so the tool cannot spend credits silently.
- `danger-full-access` is rejected.
- Common credential files such as `.env`, auth files, and private keys are rejected before the workspace is copied.
- Conditions run in separate random temporary roots. The first root is removed before the second exists. This reduces accidental cross-condition reading but is not an operating-system isolation guarantee.
- Final workspaces, captures, telemetry, and file modes are hash-sealed. The tool detects later mismatches. These hashes are not signatures and do not prove who produced the evidence.
- External evaluators receive a detached candidate copy, no Codex authentication, and no candidate capture path. Mutation of the detached copy fails the run.
- Blind packets include final answers, anonymous artifact manifests, and optional evaluator results. They do not decide whether the evaluator itself is valid.
- Local live mode is for trusted code. Use an external sandbox for untrusted code.

## Supported and tested

- Skill host tested: Codex CLI `0.144.1` on macOS, 2026-07-16
- Compatibility target tested: Claude Code `2.1.157` on macOS, 2026-07-16
- Governor: Python `3.10+`, standard library only
- Local tests: Python `3.14.5`, Git `2.50.1`, macOS
- Live Governor runner: Codex only

The Markdown Skill may work on Windows and Linux. Those platforms are not yet verified.

## Built with Codex and GPT-5.6

Codex was the main engineering environment. It was used to reverse the submission requirements into acceptance checks, implement the Governor, run tests, audit the repository, review claims, inspect the raw evaluation bundle, and remove features that did not earn their cost.

GPT-5.6 Sol with ultra reasoning was used through Codex for implementation, adversarial review, security review, evidence analysis, documentation, and the product decision to retire the original wrapper. Separate fresh-context review passes found concrete defects, including a `NaN` cost-policy bypass and mutable run evidence. Those defects were repaired and added to the test suite.

The human author set the product goal, privacy boundary, evaluation policy, and final release decision. No private code, credentials, conversation text, or project identity is included.

## Repository map

```text
SKILL.md                    small runtime lifecycle policy
tools/harness_governor.py  standard-library Governor CLI
tests/                      integrity and lifecycle contract tests
examples/self-audit/       complete published self-correction evidence
EVALUATION.md               results, limits, and next validation
references/                 optional operational depth
docs/PHILOSOPHY.md          human and engineering constitution
agents/openai.yaml          Codex interface metadata
```

The broad philosophy lives in [`docs/PHILOSOPHY.md`](docs/PHILOSOPHY.md). It is not loaded into routine work. Every runtime instruction must earn its context cost.

## License

[MIT](LICENSE)

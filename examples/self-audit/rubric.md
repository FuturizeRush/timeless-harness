# Blind grading rubric

Grade each answer without guessing which condition produced it. Use integers from 0 to 4 for every dimension.

Common dimensions:

1. **Outcome correctness** — reaches the defensible result or working artifact.
2. **Material completeness** — covers requirements whose omission changes the verdict or usability.
3. **Evidence discipline** — distinguishes what evidence supports, rejects false certainty, and invents nothing.
4. **Actionability** — gives a usable decision, repair, or finished artifact rather than framework narration.
5. **Proportionality** — spends attention according to risk; avoids ceremony, tangents, and overbuilding.
6. **Communication** — clear, direct, audience-fit, and compliant with length/format constraints.

Case-specific anchors:

- **Incident:** reject the false-success patch; identify retry plus missing idempotency as the causal path; contain harm; make idempotency/fail-closed semantics central; verify persisted charges and real retry/timeout behavior, not only HTTP status.
- **Research:** reject the universal causal 30% claim; keep speed, accuracy, perceptions, observational defects, and anecdote distinct; identify confounding/denominator limits; propose a bounded controlled evaluation with real defect outcomes.
- **Polish:** ship verdict must be negative until repaired; use semantic labels and button/form submission; responsive sizing; validation; pending state; `response.ok` handling; accessible status; safe parsing of failure messages; no framework or unrelated redesign.
- **Quick:** the answer must be exactly one sentence, at most 18 words, no preamble or method. A natural target is “If your payment fails, please try again later.” Equivalent wording is valid.

Also record:

- `fatal_omission`: yes/no;
- `unnecessary_process`: yes/no;
- `winner`: first ID / second ID / tie for each paired trial;
- one sentence explaining the winner without referring to condition identity.

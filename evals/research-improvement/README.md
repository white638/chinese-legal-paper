# Research judgment calibration

This evaluation area separates prompt wiring, model behavior, and actual research
value. Deterministic fixtures establish input and boundary contracts. They contain
no real project execution, expert preferences, or held-out research outcomes.

## Frozen inputs

`baseline-6450aae/` preserves the earlier synthetic selection and judgment inputs,
exact prompts, response schemas, and source hashes at
`6450aae02b8b6f99db8feeb979a572419f35a79f`. That selection prompt exposes citation
strata and requires a negative quota; its pair prompt gives the two sides different
fields. Replay it from a separate checkout with:

```text
python evals/research-improvement/capture_prompts.py <6450aae-source-tree> <empty-output>
```

`baseline-fae2cbf/` records actual `taste_judge.py emit` dispatches at
`fae2cbf09fc5d394bf1a0dd15b587294fad2e667`, including the appended output schema,
capture manifest, canonical plan, source hashes, and a read-only input inventory.
Both cases use one synthetic candidate and two synthetic references. Published
results produce zero comparable pairs but still emit one prompt; original proposal
fixtures produce two comparable pairs. None of the card's eight registered
exemplar explanations appears in either prompt. These observations establish the
two input discontinuities; the frequency of missing references in real production
tasks remains unmeasured.

```text
python evals/research-improvement/capture_judge_baseline.py <fae2cbf-source-tree> <empty-output>
python -m unittest discover -s evals/research-improvement -p "test_*.py"
python -m unittest discover -s skills/cnki-paper/scripts -p "test_research_improvement.py"
```

The capture command requires the selected source files to be clean and refuses to
overwrite evidence. Snapshot bytes are preserved by `.gitattributes`; source and
capture hashes describe the observed checkout and platform, including newlines.
Cross-platform comparison should separately inspect canonical prompt content.

## P1 development materials

`p1-development-cases.json` supplies eight explicitly synthetic development cases:
plain but consequential questions, empty rhetoric, descriptive research, normative
argument, historical interpretation, replication, immature anomalies, incompatible
maturity, and insufficient evidence. The review prompts identify what to inspect;
they are not expert preference labels. The file records zero acquired real cases,
zero model runs, and zero expert labels. Synthetic cases are never counted toward
the planned 20 development and 40 held-out real cases.

The opt-in research-move projection is evaluated only in the judge path. Published
examples teach documented research moves; proposal references have a separate
comparison role. The two publisher-abstract examples in the cards have
`support.basis=author_claim`. Their short source excerpts and retrospective
explanations do not establish full-text quality, original discovery history, or
independent proposal comparability. Synthetic ablations remain labeled as such.

For each authorized real case, retain the original proposal record, permission
scope, raw source snapshot hashes, information available at that time, underlying
project ID, all related teaching identifiers, and every rewrite/ablation/order
variant. Split by the connected group of project and related teaching sources;
all derivatives stay in the same split. A familiar teaching example or its project
cannot also serve as an independent held-out case. Freeze source selection,
prompts, model revision, parameters, source permissions, and cost policy before
opening the holdout.

## Fixed-candidate judge comparison

Keep candidates, original proposal references, source snapshots, model revision,
and presentation limits fixed. Compare teaching off/on and run reversed order
within each condition. Charge projection reading and all additional calls to the
same total budget. Predeclared lower-cost baseline uses of any saved budget must
be recorded; an over-budget run is not a matched comparison. Missing or
unverifiable references produce a plan reason and no pairwise model dispatch.

Independent domain evaluators record which proposal deserves the next research
investment, the concrete reason, the evidence that would change the choice, or why
comparison is unjustified. Retain disagreement and evaluate at project level.
Measure false rejection, unsupported acceptance, justified abstention, order and
rhetoric sensitivity, response to substantive degradation, and full resource
costs. Agreement or a self-assigned taste score is insufficient. Numerical quality
thresholds and the minimum worthwhile effect must be registered before holdout
results are inspected; they are not established by these development materials.

## Later evaluation and authority

The proposed deep-reading on/off by exemplar-judge on/off factorial belongs to a
later generation comparison with the same authorized sources and total budget.
The 12-project comparison requires actual execution and independent judgments;
its earlier planning estimate is 72 primary-host and 24 cross-host runs. Screening
shadow replay and cross-project memory are separate interventions.

Current regressions cover symmetric views, maturity mismatch, reversed order,
unverified style changes, source drift, contribution types, execution eligibility,
honest historical baselines, material exposure, and Writer isolation. The empirical
suite binds contribution checks to accepted execution artifacts and invalidates
them after artifact mutation. Fixtures that mock execution authority do not
establish method validity.

Taste remains optional, unvalidated, `signal-not-gate`, and `opinions-only`.
Source, design, execution, confirmation, and stage authorities remain in their
existing files. Behavioral validation and research-quality effects are pending.

# Results-as-Validation

A Results section tests registered promises; it is not a place where a number
becomes evidence merely because it was placed in a Markdown table.  Result
authority belongs to the fully validated `method_execution.json` v3 contract.

## Authority Rule

`method_execution.py::downstream_eligibility` is the only downstream eligibility
projection.  It first runs the complete canonical execution validator, then
projects only results reciprocally bound to accepted actions and registered
claim dispositions.  Its `allowed_uses` field decides whether a result may be
used for claim support, ordinary result reporting, or explicit negative/null
reporting.

`results_validation.md` is a rebuildable explanatory view of that projection.
It is not an execution record, registry, or second source of truth.  Hand-adding
a Claim ID, a result ID, or a number to this file cannot make it eligible.  If
the view differs from `method_execution.json`, repair the execution contract and
rebuild the view; never edit the view to manufacture a passing decision.

## Fail-Closed Gate

`results_validation_check.py` fails when any of these conditions holds:

- `method_execution.json` is missing or unreadable;
- canonical execution validation returns `BLOCKED`;
- the eligibility projection is malformed;
- no projected result has a non-empty `allowed_uses` list.

The checker does not parse Markdown rows as evidence.  A fabricated row such as
`CLM-FAKE | 99.9` therefore contributes nothing to the decision.

## Derived View

When a human-readable view is useful, render each row from one projected result:

| Results Unit | Result ID | Claim ID | Status | Allowed Use | Action IDs | Artifact IDs | Interpretation Boundary |
|---|---|---|---|---|---|---|---|
| 4.2 Main finding | RES-001 | CLM-001 | supported | claim_support; result_report | ACT-001 | ART-001 | Only the registered material, population, time, and model scope |
| 4.3 Null finding | RES-002 | CLM-002 | null | negative_or_null_report | ACT-002 | ART-002 | Report the null result; do not present it as support for the original proposition |

The row may add section placement, figure/table location, and a reader-facing
explanation.  Canonical IDs, status, claim disposition, action/artifact links,
and allowed uses must be copied from the projection without reinterpretation.
Numeric values remain governed by the registered result and artifact records.

## Workflow

1. Complete and validate the v3 execution contract.
2. Call `downstream_eligibility`; stop if its status is `BLOCKED`.
3. Require at least one projected result with a non-empty `allowed_uses` list.
4. Render `results_validation.md` as an optional explanatory view.
5. Write Results prose only for the use licensed by each projected result.

Validate the workspace with:

```powershell
$ResultsCheck = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\results_validation_check.py'
& $Python -X utf8 $ResultsCheck paper_rewriting_output --markdown --write
```

Exit 0 means the canonical projection contains at least one downstream-eligible
result.  Exit 1 means downstream result use is closed.  The written
`results_validation_check.md` is an audit report, not an authority file.

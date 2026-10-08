# Formal Review Response and Rebuttal

Drafting a response can be a direct capability. A formal response/rebuttal
package that claims manuscript changes is available only for
`task_profile=manuscript_revision` and completes inside `output` after the
revised canonical manuscript has passed audit.

## One-way Review Isolation

Maintain two transient compiled views during revision:

- **Response View** contains the authoritative comment text, stable Comment ID,
  disposition, rationale, affected manuscript location, authorized owner-stage
  route, and the final change evidence needed for the response package. Reviewer
  identity, tone, requests, and comment order belong only here.
- **Writer-safe View** contains only the authorized Claim Delta, Evidence Delta,
  and Structure Delta after the owning authorities have been updated. Its
  reader-facing inputs are the same semantic fields used by
  `avereth-prose-packet/v2`: canonical proposition, protected atoms, reader
  question, explanation path, selected evidence and evidence functions,
  warrant, activated boundary, and reader update. It must contain no Comment ID,
  reviewer label, quoted review language, response rationale, acceptance/refusal
  wording, workflow status, or comment-to-change sequence.

Both views are rebuildable projections. Neither is a new fact table, registry,
receipt, stage, or completion authority. The flow is one way:

`review source -> Response View -> authorized deltas -> owning authorities -> Writer-safe View -> explanation-first prose pipeline -> audited final manuscript -> final-manuscript diff -> response package`

Never use a response letter, rebuttal paragraph, reviewer comment, or
comment-by-comment change log as manuscript-generation context. Review-driven
revision first merges the authorized findings into Claim/Evidence/Structure
Deltas, then redraws each affected section blueprint and rewrites the section as
one explanatory argument. This prevents reviewer-comment order and local patch
seams from becoming the manuscript's structure.

Configure `response_package` as `review_response` or `rebuttal`, then declare:

- `response_source_dir` containing the response matrix, letter, and change log;
- `response_review_source` containing the authoritative reviewer comments;
- the exact `response_required_files` list;
- root `review_comment_confirmation.json` using
  `avereth-review-comment-confirmation/v1`, naming the actual `confirmed_by`
  identity, and binding the review-source SHA-256 plus the exact stable
  comment-ID set.

Use stable IDs such as `R1.C1`. Every ID in the review source must appear in the
formal materials, and no additional ID may appear. `needs-author`, TODO, VERIFY,
placeholders, missing confirmation, or a prose claim that the manuscript was
changed without a bound revised-manuscript hash fails. If the revision changes
claims, evidence, title, scope, design, or execution, reopen the earliest owning
state before packaging.

Generate the response matrix, letter, and change log from the diff between the
audited final manuscript and its bound pre-revision source, checked against the
Response View's dispositions. The response package may explain what the final
manuscript changed; it must never feed wording or structure back into that
manuscript. If the diff does not support a claimed change, the response claim
fails rather than prompting a post-audit patch.

The output engine stages the exact materials and current revised manuscript,
writes a response manifest and report, and publishes them under
`review_response/` or `rebuttal/` in the same transaction and receipt as the
other deliverables. Never treat the response folder as an independent
completion authority.

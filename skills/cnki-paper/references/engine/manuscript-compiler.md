# Avereth Manuscript Compiler

The Avereth Manuscript Compiler (AMC) is a build-internal structural compiler.
It turns registered research identities into a global manuscript contract and a
deterministic manuscript intermediate representation (MIR). It does not add a
workflow stage, own scientific facts, issue a stage receipt, or decide
completion. `cnki-paper` remains the sole eight-stage control plane.

## Authority boundary

The global contract stores references to the current research question, Claims,
contribution, design, Results, scope, and literature authorities. It does not
copy or rewrite their scientific propositions. The MIR has
`authority_class=derived_projection`; it is disposable and rebuildable.

Every authority must match the implementation-controlled tuple of authority
kind, typed workflow-registry path, and selector/identity kind. The registry
artifact must be canonical and owned before build. Arbitrary workspace files,
registered paths used under the wrong kind, `.avereth-prose/`, manuscript,
review, and delivery outputs are rejected. Claim snapshots retain only a digest
of the registered canonical proposition, inference strength, and protected
atoms so rebuild proof can check semantic identity without copying scientific
prose into MIR.

For a migrated workspace, every main Claim selected from
`research_design.json` must therefore explicitly register `text` (or
`canonical_proposition`), `type` (or `strength`), and the complete ProsePacket
v2 `protected_atoms` object before AMC compilation. Older Claim records without
these fields fail `MS-CLAIM-SEMANTICS`; the compiler never guesses subject,
relation, direction, polarity, strength, scope, literals, numbers, or citation
anchors from prose. Add and revalidate that upstream design authority, then run
`manuscript compile` again.

AMC sits above the unchanged prose firewall:

```text
registered authorities
  -> avereth-manuscript-contract/v1
  -> avereth-manuscript-ir/v1 (Section / Move / edge graph)
  -> per-unit avereth-prose-packet/v2
  -> Writer / deterministic gates / Clarity Editor / semantic fidelity
  -> canonical manuscript
  -> AMC synchronization validation
```

No MIR node may be passed to an isolated prose agent. The writer receives
the exact validated ProsePacket v2 path. A validated dual-packet dispatch under
`prose_conditioning=auto` or explicit `commonplace` may add one Move-bound
CommonplacePacket v1 as described in `../commonplace-writing.md`. In `auto`, a
recorded lack of qualified exemplars after retrieval permits a prose-only Move;
it does not waive the existing Writer, Clarity, protected-atom, semantic-fidelity,
or canonical-realization proof. `none` disables language conditioning, not the
default writing principles. Existing modes and absent legacy configuration keep
their prior behavior. Semantic realization of ordinary new Claims never overrides
an authorized verbatim mode or user-locked/protected text.
AMC must never carry controller
state, reviewer personas, failed checks, unactivated objections, or the full
evidence bank into prose.

The explanation path and rhetorical task describe reader-understandable reasoning,
not a fixed first sentence or material/judgment order. A material-led passage or a
long inferential sentence is valid when the registered argument remains recoverable.
New explicit semantic/verbatim packets record `surface_order_policy=argument_function`
in the existing expression budget, without universal claim-latency or boundary-order
caps. Registered boundary locations, exact protected text and independent semantic
fidelity remain binding. Historical v1/v2 budgets and missing-mode `legacy_exact`
retain their original canonical shape and digest; reading never migrates them.
Conceptual distinctions and cross-material relations use existing authorities,
selected evidence, warrants, and reader updates; neither MIR nor a language exemplar
can create a new comparison, independent corroboration, fact, or quotation license.

## MVP contract

Two genre profiles are installed under `references/manuscript-profiles/`; the
contract's `genre_profile` selects one and the compiler validates the contract
against exactly that profile:

| `genre_profile` | Body sections between introduction and discussion | Use for |
|---|---|---|
| `empirical-social-science` (default) | literature/theory → data/methods → results | 数据与估计承重的实证研究：定量、实验、调查、QCA、过程追踪、文本即数据 |
| `humanities-argument` | literature/interpretive frame → sources/analytical procedure → analysis | 论证与史料/文本承重的研究：政治理论、规范论证、思想史/概念史、历史政治学与制度史、诠释性与概念性研究 |

Both share title, abstract, introduction, discussion, conclusion, and
supporting expression, the same seven-stage Claim lifecycle, the same promise
and sync gates, and the same inference-ceiling rule. The humanities profile
replaces sample/measurement/diagnostics moves with source selection, source
criticism, analytical procedure, evidence anchoring, and objection disposition;
its inference ceiling is set by the sources and reasoning, not by estimation.
Chinese heading conventions (一、（一）1.) remain a presentation choice; see
`references/cn-journal-conventions.md` and, for source citation and criticism,
`references/primary-source-citation.md`.

Profile selection at `manuscript init`, in priority order:

1. `--profile <id>` on the command line;
2. `workflow_config.json.manuscript_profile`;
3. auto-detection: if every primary `method_routes[]` entry in
   `research_design.json` is `interpretive`, `normative`, `theory_generation`,
   `review`, or declares `empirical: false`, the humanities profile is chosen;
   any empirical route, or a design without typed routes, keeps the empirical
   profile. Historical or case-process designs that argue from sources rather
   than estimates must opt in explicitly (step 1 or 2), because the router
   cannot tell an archival narrative from a process-tracing estimate.

The chosen profile is recorded in the contract and in the MIR's `profile`
binding; a contract whose sections do not match its declared profile fails
`MS-SECTION-COVERAGE`, and an unknown `genre_profile` fails `MS-PROFILE`.
Every contract must compile:

- one continuous reader-state transition chain;
- required Move types for every Section role;
- typed cross-section edges in an acyclic dependency graph;
- every main Claim through introduced, motivated, specified, operationalized,
  evaluated, interpreted, and summarized;
- explicit promise source and delivery Moves sharing the same authority;
- synchronized question, Claim, design, Result, contribution, and scope
  identities across the profile's required Sections;
- inference strength no greater than the registered Claim ceiling;
- every formal hypothesis or proposition into the Claim lifecycle.

Unknown or authority-unbound `move.claim_refs` fail with
`MS-NO-GHOST-CLAIM`. The identity gates use the stable codes
`MS-CLAIM-IDENTITY` and `MS-RESULT-IDENTITY`.

## Argument focus and proof obligations

Before body prose, state the current question and warranted answer in
`narrative_contract.central_throughline`, then identify the smallest sufficient
chain of responsibilities needed to answer it. When multiple Claims or
cross-section reasoning need explicit allocation, use the optional fields below.
Legacy contracts remain readable without them. A contract using these fields
must replace the genre profile's generic throughline with a statement of the
current question; a different string alone does not establish scholarly focus.

`promise_type=proof_obligation` uses the existing promise identity and bindings:

- `authority_refs` includes the global `research_question_ref`.
- `required_authority_refs` is a subset of `authority_refs`, containing at least
  one global main Claim and one supporting authority from the registered chain.
- `source_move_ref` carries that question and the required main Claim identities,
  and its `promise_refs` includes this promise.
- Every `delivery_move_ref` reciprocates through `delivery_refs` and shares at
  least one required authority. The union of delivery authorities covers every
  `required_authority_ref`; responsibilities may be distributed across Moves.
- `warrant` states how the registered grounds bear on the answer;
  `failure_consequence` states how insufficient or contrary grounds change the
  Claim or its scope. These records cannot replace upstream design or execution
  judgments.

Coverage validates the registered responsibility and its manuscript placement;
it does not certify that a proposition is true. Negative, contrary, or
inconclusive results may fulfill an obligation. Historical, interpretive,
conceptual, and normative arguments use their actual sources and reasoning
responsibilities without inventing an estimand or empirical rivalry.

Sections may declare the grouped fields `argument_role`, `serves_promise_refs`,
and `if_removed`. Roles are `core_argument`, `enabling`, `synthesis`, or
`presentation`. Promise references must resolve; a `core_argument` Section
serves at least one proof obligation actually delivered by a Move in that
Section. `if_removed` describes the specific loss to the argument or its
understanding. Necessary background, source criticism, methods, and reader
orientation can therefore remain. Structural validation checks these bindings;
Clean Read judges whether the claimed loss is real, rather than rewarding the
length of its rationale.

Changes to obligations or Section rationales enter the existing stale closure
and require current rebuild proof. These records are `control_plane_only`: only the existing
ProsePacket `reader_question`, `reader_update`, `rhetorical_task`, and selected
evidence functions carry the relevant reader task into prose. The full contract,
deletion rationale, reviewer material, and evidence bank remain outside Writer.

## Commands and migration

AMC is mandatory for `full_paper` and `manuscript_revision`. It is not imposed
on the legacy audit-only `manuscript_audit` profile.

```powershell
$Python scripts/avereth.py manuscript init WORKSPACE --apply
$Python scripts/avereth.py manuscript compile WORKSPACE --json
$Python scripts/avereth.py manuscript render WORKSPACE --baseline
$Python scripts/avereth.py manuscript validate WORKSPACE --json
```

`init` creates `.avereth-prose/manuscript/manuscript_contract.json` only when
the current research/design/execution authorities expose at least one Claim and
Result. It never overwrites an existing contract. The operator must review the
contract before the first `render --baseline`.

Baseline is the explicit enable boundary. It never silently destroys earlier
planning: every pre-existing `section_blueprints.md`,
`writing_rationale_matrix.md`, other target view, and
`manuscript_trace_manifest.json` is first copied under
`.avereth-prose/manuscript/legacy-view-archives/`; `archive_manifest.json`
records original path, archived path, byte length, original SHA-256, and the
exact replacement SHA-256. A generated AMC marker, trace/stale/proof artifact,
archive lineage, or v6.8 receipt binding without its MIR is an orphaned lineage,
not a fresh workspace: baseline fails `MS-IR-ORPHANED` instead of resetting
history. Ordinary non-AMC legacy views and traces remain recoverably archived.
Verify or restore an archive with:

```powershell
$Python scripts/avereth.py manuscript restore-legacy WORKSPACE `
  .avereth-prose/manuscript/legacy-view-archives/ARCHIVE/archive_manifest.json
$Python scripts/avereth.py manuscript restore-legacy WORKSPACE `
  .avereth-prose/manuscript/legacy-view-archives/ARCHIVE/archive_manifest.json --apply
```

Restore refuses a target whose post-baseline bytes have drifted and writes a
before/after SHA receipt when applied.

The baseline renders:

- `section_blueprints.md`;
- `writing_rationale_matrix.md`;
- `promise_delivery_matrix.md`;
- `claim_lifecycle_matrix.md`;
- `reader_state_report.md`;
- `cross_section_sync_report.md`;
- `manuscript_trace_manifest.json`;
- transient MIR and stale state under `.avereth-prose/manuscript/`.

These files are generated views. Hand edits fail `MS-VIEW-DRIFT`; edit the
contract or upstream authority and render again.

## Stale closure and rebuild proof

AMC compares the strict contract, full authority source context plus selected
objects, and the previous MIR. A changed input invalidates its direct Moves and
every downstream dependent Move. Edge relations, scientific/render order, and
execution-wide fields therefore cannot change invisibly. A manuscript-only
change marks the whole Move graph stale; changing arbitrary bytes in the
canonical manuscript never clears a closure.

After rebuilding affected prose, record one compound transient proof item for
every stale Move. Each item must bind the complete existing build chain:
validated `avereth-prose-packet/v2`, Writer draft, Clarity draft and ledger,
semantic dispatch, and independent semantic assurance. The packet role,
`reader_question`, `reader_update`, Claim ID, canonical proposition, inference
strength, and protected atoms must match the Move and its registered Claim
authority. Deterministic Writer/Clarity fidelity, the Explanation/Leakage gate,
and Semantic Fidelity all rerun against the exact files. Only the semantically
assured Clarity draft can prove realization in the canonical manuscript; an
optional `section_output` must be byte-identical to it. Paths are unique per
Move and load-bearing content cannot be reused. Every item also binds the
current Move source digest, contract SHA, authority digest, and canonical
manuscript SHA:

```powershell
$Python scripts/avereth.py manuscript prove-rebuild WORKSPACE `
  --entry MOVE-RESULTS-CORE=prose_packet=.avereth-prose/rebuild-evidence/results-core/packet.json `
  --entry MOVE-RESULTS-CORE=writer_draft=.avereth-prose/rebuild-evidence/results-core/writer.md `
  --entry MOVE-RESULTS-CORE=clarity_draft=.avereth-prose/rebuild-evidence/results-core/clarity.md `
  --entry MOVE-RESULTS-CORE=clarity_ledger=.avereth-prose/rebuild-evidence/results-core/clarity-ledger.json `
  --entry MOVE-RESULTS-CORE=semantic_dispatch=.avereth-prose/semantic-fidelity/SEM-RUN/dispatch.json `
  --entry MOVE-RESULTS-CORE=semantic_assurance=.avereth-prose/semantic-fidelity/SEM-RUN/assurance.json `
  --apply
$Python scripts/avereth.py manuscript render WORKSPACE
```

Repeat `--entry` until it covers the exact reported stale closure. Missing,
changed, obsolete, or partial proof fails closed with `MS-STALE-UNREBUILT` or
`MS-REBUILD-PROOF-STALE`. Current validation reopens the bound proof and
revalidates the strict proof schema and every chain leaf; deleting or changing
transient evidence therefore invalidates build currentness. Markdown, TeX, and
canonical DOCX realization are supported; DOCX is inspected fail-closed from
OOXML visible text including tables (and footnotes/endnotes when present).
Prior MIR, trace, stale, and proof SHA/source bindings must remain mutually
closed: overwriting the MIR with a new read-only compilation or deleting MIR or
stale state cannot create a new baseline. The proof is an internal build
artifact, not a ninth stage receipt or scientific authority. Audit and output
fingerprints dynamically expand the trace through proof and semantic-review
leaf files, while receipt status also reruns AMC currentness. Child Markdown
views remain rebuildable.

## Build preflight

The normal build gate validates the current contract, MIR, generated views,
stale manifest, proof binding, trace manifest, and canonical manuscript before
recording `build_run.json`. A migrated full-paper workspace without AMC fails
with an explicit `manuscript init` and `render --baseline` instruction. The
gate never silently creates or refreshes AMC artifacts.

# Optional rhetorical contract fields

Profile 1.1 adds optional Thought Move state/action fields, `epistemic_hook` promise delay and resolution fields, `verified_scene`, `returns_to`, title `resonance_device`, and `body_explanation_move_ref`. Profile compatibility accepts legacy 1.0 contracts without them. The compiler emits the stable `AP.*` failures documented in [`../rhetorical-architecture.md`](../rhetorical-architecture.md) while the MIR remains a derived build projection and `cnki-paper` remains the only completion authority.

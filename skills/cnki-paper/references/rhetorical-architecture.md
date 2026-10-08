# Rhetorical Architecture: Problem Movement With Evidence

This protocol adds reader-facing movement to the existing CNKI-Paper research and build chain. It is not a stage, registry, scientific authority, receipt, or completion gate. The eight machine stages remain authoritative; every field below is an optional projection of an existing literature, Claim, Evidence, Design, Result, or manuscript identity. Legacy artifacts that omit the fields remain valid.

The writing principles apply by default across languages, genres, prose modes, and Direct bounded writing. Direct uses only the relevant principles and source checks, without creating a workspace or these structural artifacts. Reader-recoverable reasoning is required; a particular opening, sentence length, quotation count, hook, or metaphor is not.

## Problem Arc in literature analysis

`cnki-literature-analysis/v2.problem_arc` records how the live question changed during synthesis. Each state contains:

- `live_question` and `provisional_answer`;
- the evidence-backed `pressure` on that answer;
- one transition: `POSE`, `PRESS`, `DISTINGUISH`, `REVISE`, or `ADVANCE`;
- `updated_problem` and `residual_unknown`;
- current Source, Critical Reading, or Synthesis authority refs;
- optional predecessor and branch lineage.

The arc is a problem biography, not a chronology of authors. A transition without current authority fails. A major competing branch may be retained, revised, resolved, or bounded, but it may not disappear without a disposition. The Dialogic Argument Map may project the arc for writing, but `literature_analysis.json` remains canonical.

## Thought Moves in the manuscript contract

A load-bearing AMC Move may declare `argument_action`, `problem_state_before`, and `problem_state_after`. The build compiler accepts `POSE`, `PRESS`, `DISTINGUISH`, `REVISE`, `ADVANCE`, `RESOLVE`, and `RETURN`. If any of the three fields is present, all three are required, and the before/after states must differ. Distinguished current-profile builds require them on profile-declared load-bearing Move types.

The writer realizes the transition only from the validated ProsePacket's optional `rhetorical_task`. The Clarity Editor may expose an existing transition with a grounded `BRIDGE`; it cannot invent a state, pressure, mechanism, or conclusion.

Thought movement can pose, question, distinguish, challenge, revise, and advance an answer through registered facts, textual detail, data anomalies, or theoretical tensions. A criticism must identify what an explanation cannot account for, which premise it omits, or what follows from its own logic. The target is the argument and its evidence, not its author's character. A long sentence may carry continuous reasoning and a short sentence may crystallize a judgment; neither is a mandatory pattern. Supporting definitions and methods need not pretend to overturn the central claim.

## Throughline and Section responsibilities

Thought Moves serve the current question and warranted answer recorded in
`narrative_contract.central_throughline`. Where the argument needs explicit
allocation, existing promises may use `proof_obligation`, and Sections may
declare `argument_role`, `serves_promise_refs`, and `if_removed`; the binding
rules are in [the manuscript compiler contract](engine/manuscript-compiler.md#argument-focus-and-proof-obligations).
Use these fields according to argument complexity, with the smallest sufficient
responsibility chain. An obligation can be fulfilled by a negative or bounded
answer. Necessary explanatory and methodological work has a Section role even
when it does not independently advance a main Claim.

## Epistemic hooks

An `epistemic_hook` is an existing AMC promise type, not a suspense layer. It binds one source Move, registered authorities, one or more delivery Moves, `delay_span`, and `resolution_type`. Legal delay is `same_move`, `same_section`, or a profile-bounded `next_answer_section`. A hook is legitimate only when temporary non-resolution helps the reader compare explanations or encounter decisive evidence. It must be paid in order and the answer must deepen or narrow the live question.

## Context Anchors and scenes

Context Anchors live inside the existing evidence bank and travel only with selected ProsePacket evidence. The table contract is:

| Anchor ID | Authority Ref | Type | Locator | Exact Span/Known Details | Original Problem | Logical Context | Protected Qualifiers | Manuscript Function | Status |
|---|---|---|---|---|---|---|---|---|---|
| `ANCHOR-*` | existing Source/Evidence authority | quotation / scene / case / definition | page, paragraph, timestamp, table, provision, or archive unit | exact quoted/defined span or bounded known details | the question for which it matters | surrounding reasoning | exact qualifiers that cannot be dropped | evidence, distinction, process, or closure role | `content-verified` |

A quotation without this context is unusable in a new Context-Anchor-enabled build. The Writer preserves exact span, locator, and protected qualifiers. A scene or case uses only registered known details. `verified_scene` on an AMC Move binds the anchor to an existing authority; a `returns_to` edge must connect a later Move to an earlier verified scene with the same Anchor ID. The later use must change understanding, not repeat imagery.

Recover a quotation's question, argumentative target, causal or logical structure, and qualifications from the same original source's available context; do not assemble isolated sayings into a position the source never held. Strong material may lead a passage or perform its decisive inferential step before the author crystallizes the judgment. Its role and resulting reader update must be recoverable, without a compulsory lead-in/excerpt/explanation order or a formula after every quotation. Exact quotations and user-locked wording remain protected under every prose mode.

An opening makes background, question, and significance recoverable through an evidence-backed entry; it need not devote a paragraph to each. Closure answers that question, states the warranted knowledge change, and remains within the evidence. Returning to a scene is optional. Never add an imagined gesture, speaker, number, causal link, or surrounding detail to make an opening or ending vivid.

## Title–body fulfillment

The Title Revision Chain may add `Resonance Device` and `Body Explanation Move`. `none` is valid. A metaphor, allusion, wordplay, question, symmetry, or other resonance device requires a distinct `MOVE-*` in the body that explains the substantive relation. The AMC and academic-prose audit both fail an unfulfilled device; rhetoric cannot create a title-level claim that the body does not carry.

## Writer, Clarity Editor, and clean read

The ProsePacket may contain only the optional `rhetorical_task` and selected evidence-item `context_anchor` in addition to the established v2 firewall fields. The Writer realizes the registered problem movement; the Clarity Editor preserves it and every anchor while remaining within DELETE/REPLACE/MOVE/BRIDGE/DEFINE. Deterministic checks protect identity, locator, exact span, qualifier, scene, hook ordering, return identity, and title-body binding. The isolated Clarity reviewer then judges catalogue-only succession, false teleology, motion without advance, artificial or non-deepening hooks, decorative quotation, source-dominated voice, repetition-only closure, and ungrounded elevation.

Conceptual distinctions and cross-text comparisons reuse registered synthesis, Claim/Evidence, warrant, explanation path, and reader update; no stylistic schema or new scientific authority is needed. A comparison identifies the shared question, level of correspondence, conditions, divergence, and explanatory gain. A heuristic analogy is not independent corroboration, coincident words are not structural identity, and sources sharing an origin do not become independent support. Writers may realize only relations already authorized by the packet, including when a Commonplace language packet is available.

Clean Read first reconstructs the question, substantive answer, strongest
grounds, and inference boundary from the manuscript alone. It then locates
Sections whose removal would leave those unchanged and checks whether they
still supply necessary comprehension, transparency, or reasoning. Compression
is useful only if those functions and protected qualifications survive. A
shared slogan, a shorter manuscript, or a filled deletion rationale does not
establish focus; findings must identify the text and the affected reader task.

## Stable blocking codes

- `AP.ARC.AUTHORITY_MISSING`, `AP.ARC.BRANCH_DROPPED`, `AP.ARC.PROJECTION_MISSING`, `AP.ARC.PROJECTION_DRIFT`
- `AP.MOTION.ACTION_INVALID`, `AP.MOTION.STATE_INCOMPLETE`, `AP.MOTION.NO_ADVANCE`
- `AP.HOOK.UNPAID`, `AP.HOOK.ORDER_INVALID`, `AP.HOOK.OVERDELAY`
- `AP.QUOTE.CONTEXT_MISSING`, `AP.QUOTE.LOCATOR_MISSING`, `AP.QUOTE.QUALIFIER_LOSS`
- `AP.SCENE.UNBOUND`, `AP.CLOSURE.ANCHOR_MISMATCH`, `AP.CLOSURE.ORDER_INVALID`
- `AP.TITLE.BODY_ANCHOR_MISSING`

Semantic clean-read categories use `AP.ARC.CATALOGUE_ONLY`, `AP.ARC.FALSE_TELEOLOGY`, `AP.HOOK.ARTIFICIAL`, `AP.HOOK.NO_DEEPENING`, `AP.QUOTE.DECORATIVE`, `AP.VOICE.SOURCE_DOMINATED`, `AP.CLOSURE.REPETITION_ONLY`, and `AP.CLOSURE.UNGROUNDED_ELEVATION`. These are review findings, not deterministic claims about prose quality.

## Evaluation

The repository mastery set includes ten paired cases covering Problem Arc, false teleology, Thought Move advance, legal hook delay, hook payment, quotation context, source/author voice, verified return, grounded closure, and title-body fulfillment. Pairwise preference is evidence-bounded: resonance never compensates for lost facts, stronger inference, missing scope, missing locator, or an invented mechanism.

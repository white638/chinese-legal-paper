# Explanation-First Academic Prose Capability Rubric

## Purpose

Evaluate whether an academic revision preserves the canonical proposition while making the object, mechanism or warrant, evidence role, and reader update easier to reconstruct. Apply the principles across languages, disciplines, genres and prose modes; adapt their realization to the case. The optimization order is semantic fidelity, substantive explanation, reading continuity, positive formulation, boundary discipline, and revision cleanliness. The rubric does not reward novelty labels, length reduction, uniformly short sentences, summary-first openings, negative-word avoidance, or a fixed number of findings. Explanation-first names the priority of understanding, not a compulsory surface order.

## Non-negotiable contract gates

A candidate fails before stylistic comparison when any of the following occurs:

- the research object, relation, direction, polarity, inferential strength, scope, protected literal, number, citation anchor, locator, negative result, or necessary responsibility changes or disappears;
- an association becomes causal, a bounded result becomes universal, or an observed absence becomes necessity, impossibility, exclusivity, or sufficiency without the required comparison and warrant;
- a registered full boundary is omitted, moved away from its authorized location or inferential role, or repeated beyond its single authorized occurrence; an explicit legacy-packet ordering constraint remains binding;
- reviewer, supervisor, comment, response, revision, audit, workflow, or packet language appears in the manuscript, or the paragraph retains a recognizable comment-by-comment rebuttal structure;
- positive prose growth is produced by any action other than a ledgered `BRIDGE` or `DEFINE`, violates an explicit hard constraint, or adds a fact, citation, case, theoretical property, or stronger inference; configured soft growth diagnostics require another read, not automatic failure;
- a deterministic gate is presented as proof of semantic equivalence. Semantic mode requires an independent bidirectional fidelity judgment.

These are contract failures, not quality scores. A true negative result, useful conceptual contrast, legal or ethical boundary, and consequential author responsibility remain manuscript content when they are load-bearing.

## Blind A/B judgment

The evaluator sees anonymized A and B plus the writer-safe semantic contract: canonical proposition, protected atoms and literals, selected evidence, warrant, activated boundary, and reader question. It does not see version identity, the expected preference, a reference answer, reviewer comments, edit history, or control-plane material.

For each dimension return `A`, `B`, `TIE`, or `BOTH_FAIL`, followed by a manuscript-located reason. Do not total the dimensions into an automatic quality or novelty score.

| Dimension | Passing evidence | Failure signal |
|---|---|---|
| Semantic fidelity | The same subject, relation, direction, polarity, inferential strength, scope, protected literals, numbers, citations, and necessary boundaries are recoverable in both directions | Exact wording survives but meaning drifts, or fluent paraphrase changes strength, scope, polarity, result identity, or evidence responsibility |
| Substantive explanation | A claim supplies the mechanism, process, distinction or warrant needed to connect evidence to judgment; decisive material can lead, and its argumentative role is recoverable in the surrounding reasoning | Evidence jumps directly to a conclusion, an abstract noun replaces a process, the author explains away the material before it can do work, or the paragraph merely restates the finding |
| Reading continuity | The object's question, judgment, explanation, evidence role and reader update form a recoverable progression; openings and sentence rhythm serve the passage's function | Author process, caveat, framework inventory, reviewer-style concession, or a repetitive summary-first template obscures the reasoning |
| Positive formulation | The paragraph makes clear what happened, what the material supports and where the result applies; retained negatives perform empirical or analytical work | Author-intent defense, exclusion-first scope, or repeated “cannot/does not mean” clauses organize the argument |
| Revision cleanliness / clean-read | A reader who has never seen the review can explain the section from research logic and cannot identify inserted response patches | Reviewer/process vocabulary, “question—concession—response” sequencing, duplicated qualifications, or a sentence needed only to answer a hidden comment |
| Actor and terminology visibility | Relevant actors, actions, constraints and consequences are visible; registered terms retain their identity and neighboring concepts or judgment levels are distinguished | Nominalization hides who acts, simplification replaces a protected term with a looser synonym, or presence, representation, persuasion or value are conflated without a warrant |
| Boundary discipline | A calibrated verb or positive scope handles simple limits; a complex full boundary appears once at its registered location and its relation to the judgment remains clear | An unnecessary defensive boundary obscures the opening, a required boundary is duplicated, or it disappears in a confidence edit |

The preferred variant must pass every contract gate and give the clearer, more complete account on the dimensions actually implicated by the case. `TIE` is legitimate when neither variant materially improves explanation or cleanliness. `BOTH_FAIL` is required when both violate the semantic contract.

Where a cross-material comparison occurs, examine its shared question, level of correspondence, conditions, divergence and explanatory gain under the applicable dimensions. Heuristic analogy does not establish independent corroboration, coincident words do not establish conceptual identity, and sources with a shared origin are not independent evidence. Criticism must name an explanatory failure, omitted premise or consequence of an argument's own logic; personal attack and dismissive adjectives do not supply that reasoning. A title's resonance device must have a warranted body explanation. Hooks and returning scenes are optional; when used, they must resolve through registered material and deepen the answer.

Do not impose quotas for quotations, hooks, metaphors, sentence lengths, paragraph openings, concepts or cross-cultural references. A quotation can precede its interpretation without a fixed following formula; a long sentence can outperform a broken sequence when it preserves the reasoning's dependency structure. User-locked and authorized verbatim text remain protected even when a reviewer would prefer another style.

## BRIDGE and DEFINE

`BRIDGE` may make an implicit packet warrant or registered explanation step explicit. `DEFINE` may give a plain-language realization of an already registered term. Each positive-growth action must identify its Claim ID, source kind and source anchor, added reader understanding, prose delta, and affirm that it introduces no new fact, citation, or inference strengthening. The action ledger must reconcile exactly with the observed prose-unit delta.

Local growth is evidence-bounded, not a reward for verbosity. The evaluator should prefer deletion or replacement when the reader already has the necessary bridge or definition, and should fail a shorter version that achieves economy by removing a load-bearing step.

## Deterministic and generation cases

`cases.json` verifies context-sensitive risk triggers; a trigger initiates review and is not itself a ban. `defensive_corpus.json` exercises seven explanation-first behaviors directly:

1. semantic paraphrase of a defensive claim;
2. preservation and explanation of a true negative result;
3. stable direction, scope, and associational strength;
4. reviewer comment translation into a writer-safe substantive delta with a clean-read manuscript;
5. bounded positive growth from a registered warrant `BRIDGE`;
6. Boundary ID de-duplication, positive scope, and the case's registered placement;
7. actor recovery without terminology loss.

The offline harness validates packet and ledger contracts, protected literals and traceability, growth authorization, boundary placement, and explicit leakage. Credentialed blind review independently judges substantive explanation, semantic fidelity, and revision cleanliness; it receives no expected preference or reference answer and never advances controller state.

Acceptance coverage for the default writing principles includes: a sustained inference better served by a long sentence; material- and quotation-led openings with recoverable judgments; successive paragraphs with functional rather than compulsory variation; conceptual distinctions that change the warranted conclusion; an analogy kept separate from independent corroboration; and a verified opening material revisited with a more precise answer. These are review scenarios, not claims that a live comparison has been run. Evidence loss cannot be offset by a stylistic preference. An auto exemplar gap does not fail prose quality by itself; a borrowed fact, unlicensed quotation or fidelity failure still does.

For `prose_mode=distinguished`, apply `mastery-rubric.md` after this contract. Distinguished prose may deepen insight or voice only after the explanation-first gates pass.

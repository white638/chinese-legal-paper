# v3.1 Blind Review Protocol

The evaluation owner freezes the 20 local tasks in `fixture_manifest.json`. Each task is run twice against baseline `eb5e0cf` and candidate `3.1.0`, producing 40 old/new pairs. File names and metadata are replaced with random pair and candidate labels before review.

Each of three reviewers receives only the task, the two candidate outputs, and this rubric:

1. research-question and answer-task match;
2. concept and material-boundary clarity;
3. method-route fit and actual executability;
4. evidence-to-claim traceability;
5. inference calibration and treatment of alternatives;
6. ethics, transparency, and reproducibility;
7. usefulness to a researcher without needless procedural burden.

Each anonymous output (`A` and `B`) receives 0–4 on every dimension. A reviewer must also give a pair preference (`A`, `B`, or `tie`) and at least three findings with exact output locations. Reviewers do not see checker output, golden answers, version labels, or one another's reviews. The coordinator resolves labels only after all three signed JSON score sheets are present. The no-zero release check applies to the decoded v3.1 candidate's question–answer match and inference calibration; baseline zeros remain diagnostic rather than a reason to fail v3.1.

Pair outcomes use a predeclared non-tie plurality rule: after decoding, the coordinator compares the number of reviewers who preferred the candidate with the number who preferred the baseline. More candidate preferences means a win, more baseline preferences means a loss, and equal counts mean a tie. A reviewer-level `tie` is neutral and is never reassigned to either output. This avoids turning two genuine abstentions into an automatic veto of the one reviewer who found a material difference.

Release requires at least 27 candidate wins, at most 5 candidate losses, no method-family net regression, and no zero on research-question/answer match or inference calibration. Automated gates remain separate: a blind-review win cannot waive a hard failure.

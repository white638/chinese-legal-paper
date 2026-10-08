# Review convergence evaluation

Run the forward scenarios directly:

```powershell
python -X utf8 evals/review-convergence/test_review_convergence_evals.py
```

The full regression suite is the release acceptance command:

```powershell
python -X utf8 -m unittest discover -s skills/cnki-paper/scripts -p 'test_*.py'
```

The proposal's convergence cases are covered as follows:

| Acceptance case | Executable coverage |
|---|---|
| Reworded finding does not become a new finding | `ReviewConvergenceForwardEvals.test_same_problem_keeps_key_across_editorial_rephrasing` |
| Finding moved to another paragraph keeps its identity | `ReviewLifecycleTests.test_finding_key_survives_issue_rewording_and_paragraph_move` |
| Surface change routes only to Clarity delta | `ReviewConvergenceForwardEvals.test_change_class_routes_are_minimal_but_scientific_changes_expand` |
| Evidence change routes to the relevant reviewers | same routing eval, `evidence` case |
| Design or result change requires all reviewers and FULL | same routing eval, `design` and `execution` cases |
| FULL sends the complete canonical manuscript to all three roles | `ReviewLifecycleTests.test_full_dispatch_reviews_complete_manuscript_with_all_roles` |
| Failed or blocked delta cycle is retained | `ReviewLifecycleTests.test_blocked_review_cycle_is_preserved` |
| Undeclared real diff fails preflight | `ReviewConvergenceForwardEvals.test_actual_diff_cannot_be_hidden_by_declared_scope` |
| Undeclared design authority drift blocks a surface batch | `ReviewConvergenceForwardEvals.test_undeclared_design_authority_drift_blocks_surface_batch` |
| Batch target Finding not covered by active changes fails preflight | `RevisionContractTests.test_preflight_blocks_uncovered_batch_finding_key` |
| Optional polish does not block closure | `ReviewConvergenceForwardEvals.test_nonblocking_polish_does_not_enter_active_blocking_set` |
| Second reopen requires root-cause escalation | `ReviewLifecycleTests.test_second_reopen_requires_structured_root_cause` |
| One batch permits only one canonical promotion | `RevisionContractTests.test_batch_preflight_and_single_atomic_promotion` |
| Action implementation drift invalidates cache | `AuditCompletionOrderTests.test_action_cache_binds_inputs_implementation_and_outputs` |
| Whole manuscript SHA changes but an unchanged role projection reuses PASS | `ReviewLifecycleTests.test_delta_dispatch_reuses_identical_role_projection_after_whole_sha_changes` |
| Relevant authority changes invalidate reviewer reuse | `ReviewLifecycleTests.test_delta_dispatch_authority_change_invalidates_relevant_role` |
| Unprojected authority lines do not invalidate reviewer reuse | `ReviewLifecycleTests.test_delta_dispatch_unprojected_authority_change_keeps_reuse` |
| Role impact changes invalidate reviewer reuse | `ReviewLifecycleTests.test_delta_dispatch_role_impact_change_invalidates_reuse` |
| Reviewer implementation semantics invalidate reuse | `ReviewLifecycleTests.test_delta_dispatch_implementation_change_invalidates_reuse` |
| Legacy revision v1 migrates with a registered Finding key and backup | `RevisionContractTests.test_v1_migration_binds_registered_finding_key_and_keeps_backup` |
| Review-driven init binds real RFKs and count mismatch fails closed | `RevisionContractTests.test_init_binds_real_finding_keys_and_rejects_count_mismatch` |

These are deterministic forward scenarios and release regressions, not a statistical quality score or a
replacement for the controller gate.

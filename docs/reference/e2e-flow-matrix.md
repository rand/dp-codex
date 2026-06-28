# End-to-End Flow Matrix

This matrix names the user-visible flows that must stay true for dp-codex to be complete enough for
human and agent operation.

| Flow | Primary user | Core path | Executable coverage |
| --- | --- | --- | --- |
| Environment and install smoke | Human or agent | `uv sync -> dp --help -> doctor -> make check` plus outside-repo CLI smoke | `tests/test_release_readiness.py`, manual outside-repo smoke in release gate |
| Local feature loop | Human | `doctor -> task claim -> implement -> preflight -> verify -> task close` | `tests/test_flow_evals.py`, `tests/integration/test_full_feature_workflow.py` |
| Task provider lifecycle | Human or agent | `task ready -> claim/show/update/close` over Beads | `tests/unit/test_cli_task.py`, `tests/unit/test_task_normalization.py`, `tests/unit/test_beads_provider.py` |
| Traceability | Maintainer | `trace coverage -> trace validate` over specs and code markers | `tests/unit/test_cli_trace_coverage.py`, `tests/unit/test_trace_parser.py`, `tests/unit/test_traceability_edge_cases.py` |
| ADR and decisioning | Maintainer | `adr create/list/show/update` with status validation | `tests/unit/test_cli_adr.py`, `tests/unit/test_adr.py` |
| Decompose and progress | Human or agent | `decompose -> progress -> progress --watch` for context recovery | `tests/unit/test_cli_decompose.py`, `tests/unit/test_decompose.py`, `tests/unit/test_cli_progress.py`, `tests/unit/test_progress.py` |
| Review and verification | Maintainer | `review -> verify manifest -> verify goal/evidence` | `tests/unit/test_review.py`, `tests/unit/test_verify.py`, `tests/test_evidence_artifacts_and_verify.py` |
| Policy and enforcement | Maintainer or CI | `policy validate -> enforce pre-commit/pre-push` | `tests/unit/test_cli_policy.py`, `tests/property/test_policy_properties.py`, `tests/unit/test_enforcement_engine.py`, `tests/unit/test_hook_scripts.py` |
| Campaign authoring | Human | `campaign init -> refine -> ready -> run -> verify -> recover` | `tests/test_campaign_pilot.py`, `tests/e2e/test_user_flows.py` |
| Campaign handoff | Agent | `agent bootstrap -> capabilities -> campaign run --managed -> emitted commands` | `tests/test_campaign_managed_run.py`, `tests/e2e/test_user_flows.py` |
| Goal execution | Human or agent | `goal claim/start -> evidence run -> verify -> loop unlock` | `tests/test_goal_state.py`, `tests/test_evidence_artifacts_and_verify.py` |
| Failure repair | Agent | `detail envelope -> stable hint -> dp explain -> block or repair` | `tests/test_progressive_disclosure.py`, `tests/test_agent_usability_evals.py`, `tests/e2e/test_user_flows.py` |
| Adoption | Adopting maintainer | `adopt inspect -> plan -> dry-run/apply -> verify` | `tests/test_adopt.py`, `tests/test_adopt_apply.py`, `tests/e2e/test_user_flows.py` |
| Migration aliases | Adopting maintainer | `migrate inspect/plan/apply/verify` compatibility over adoption engine | `tests/test_migrate_aliases.py`, `tests/test_adopt_apply.py` |
| Instruction governance | Human or agent | `instructions inspect -> audit -> plan-update without mutation` | `tests/test_instructions.py`, `tests/e2e/test_user_flows.py` |
| Hooks and skills | Agent maintainer | `skills audit/eval`, `hooks audit/doctor/scaffold preview` | `tests/test_skills.py`, `tests/test_hooks.py`, `tests/test_agent_usability_evals.py` |
| Command surface and release docs | Maintainer | parser leaf commands -> CLI reference -> release boundary/gates | `tests/test_release_readiness.py` |
| Session closeout | Agent | `make check -> doctor -> tracker health -> preflight -> commit/push` | `dp codex preflight`, repository `AGENTS.md`, manual session gate |

E2E tests are control-plane proofs. They do not claim generated campaign code implements a product;
they prove that dp keeps state, evidence, instructions, and recovery routes deterministic.

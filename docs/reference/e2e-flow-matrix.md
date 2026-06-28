# End-to-End Flow Matrix

This matrix names the user-visible flows that must stay true for dp-codex to be complete enough for
human and agent operation.

| Flow | Primary user | Core path | Executable coverage |
| --- | --- | --- | --- |
| Local feature loop | Human | `doctor -> task claim -> implement -> preflight -> verify -> task close` | `tests/test_flow_evals.py`, `tests/integration/test_full_feature_workflow.py` |
| Campaign authoring | Human | `campaign init -> refine -> ready -> run -> verify -> recover` | `tests/test_campaign_pilot.py`, `tests/e2e/test_user_flows.py` |
| Campaign handoff | Agent | `agent bootstrap -> capabilities -> campaign run --managed -> emitted commands` | `tests/test_campaign_managed_run.py`, `tests/e2e/test_user_flows.py` |
| Goal execution | Human or agent | `goal claim/start -> evidence run -> verify -> loop unlock` | `tests/test_goal_state.py`, `tests/test_evidence_artifacts_and_verify.py` |
| Failure repair | Agent | `detail envelope -> stable hint -> dp explain -> block or repair` | `tests/test_progressive_disclosure.py`, `tests/test_agent_usability_evals.py`, `tests/e2e/test_user_flows.py` |
| Adoption | Adopting maintainer | `adopt inspect -> plan -> dry-run/apply -> verify` | `tests/test_adopt.py`, `tests/test_adopt_apply.py`, `tests/e2e/test_user_flows.py` |
| Instruction governance | Human or agent | `instructions inspect -> audit -> plan-update without mutation` | `tests/test_instructions.py`, `tests/e2e/test_user_flows.py` |
| Hooks and skills | Agent maintainer | `skills audit/eval`, `hooks audit/doctor/scaffold preview` | `tests/test_skills.py`, `tests/test_hooks.py`, `tests/test_agent_usability_evals.py` |
| Session closeout | Agent | `make check -> doctor -> tracker health -> preflight -> commit/push` | `dp codex preflight`, repository `AGENTS.md`, manual session gate |

E2E tests are control-plane proofs. They do not claim generated campaign code implements a product;
they prove that dp keeps state, evidence, instructions, and recovery routes deterministic.

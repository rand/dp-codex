# Agent Recovery and Collaboration

Use this ladder after a command, gate, or workflow step fails.

## Recovery Ladder

1. Capture the exact command, exit code, failing check, branch/HEAD, worktree status, GoalContract
   boundaries, and failed receipt.
2. Reproduce with the smallest deterministic check. If the execution produced no trustworthy
   verdict, repair only non-semantic execution state and retry the identical command at most twice.
3. Classify the failure in order; take the first matching class:

   - `invalid_execution`: invocation, environment, cache, lease, worktree, or tool state produced no
     trustworthy verdict.
   - `repairable_failure`: a safe root-cause repair fits current instructions and allowed paths.
   - `independent_repair`: a non-semantic defect is outside the active contract, but another owner
     or repair goal can fix it without a human semantic or authority decision.
   - `true_blocker`: a new semantic decision, authority, external dependency, validator, unsafe
     scope, or exhausted attempt budget is required. A missing validator is in this class when no
     authorized in-scope or independent repair route already exists.

4. For `repairable_failure`, state the hypothesis and predicted focused result. Make the smallest
   coherent reversible change. Do not weaken a test, validator, contract, or evidence assertion.
5. Rerun the exact failed check. Broaden to the full goal and repository gates only after it passes.
6. For `independent_repair`, preserve evidence and route a bounded follow-up without silently
   expanding the current goal.
7. For `true_blocker`, use the GoalContract's supported dp blocker route and keep tracker/report
   state current. Do not invent unauthorized artifacts.

A failed gate blocks completion, not diagnosis or authorized repair. Do not repeat an unchanged
action unless relevant state or the hypothesis changed. Verification decides done.

## Consultation

Use specialist or adversarial agents when there are independent diagnostic threads, meaningful
domain risk, context pressure, or a failed repair hypothesis.

Every delegation states:

- the concrete question;
- allowed reads and writes;
- forbidden actions;
- required evidence or output; and
- the stop condition.

Use read-only helpers by default. One writer owns one worktree. Writing helpers need separate
worktrees or branches and disjoint paths. The primary agent reconciles findings, owns lifecycle and
tracker mutations, and reruns deterministic gates.

External agent output is advisory. Record adopted or rejected findings and why. Do not send
repository material to an external provider without applicable authorization, and do not make
agent availability a blocker for otherwise ready work.

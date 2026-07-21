<!-- dp-agent-discipline:v1 -->

## Outcome and Verification Budget

- The objective is a useful outcome in the real system. Plans, trackers, receipts, evidence files,
  reviews, and verification are support machinery, never substitutes for that outcome.
- Before adding process work, name the concrete decision or failure risk it changes. If it changes
  neither, do not do it.
- Use the smallest proportional proof: normally the focused check, any repository-required gate,
  and one live end-to-end observation for a live change. Add checks only for an identified risk.
- Once the intended outcome works and the named risks are answered, stop verifying and ship.
- Safety and versioning exist to enable fast, powerful, inspectable work with clean branch and
  revert semantics; do not turn them into the product.

## Recovery and Escalation

- A failed gate blocks completion, not diagnosis or authorized repair.
- Capture the exact failure and classify it before declaring a blocker: invalid execution,
  repairable in-scope failure, independent repair, or true decision/authority/scope blocker.
- Make the smallest coherent reversible repair allowed by project law, then rerun the focused check
  and required gates. Never weaken evidence to obtain green.
- Do not repeat an unchanged action unless relevant state or the hypothesis changed. Respect any
  declared attempt budget.
- Route a durable blocker only when no safe in-scope repair remains or new authority is required.
  Proportional verification decides done; verification volume does not.

## Agent Collaboration

- Use specialist or adversarial agents proactively for independent diagnosis, domain risk, context
  pressure, or fresh review when orchestration is available and project law allows it.
- Give each helper a bounded question, read/write scope, forbidden actions, expected output, and
  stop condition. Default helpers to read-only.
- One writer owns one worktree; writing helpers require isolated worktrees and disjoint paths.
- The primary agent owns decisions, lifecycle/tracker changes, integrated edits, and verification.
  External agent output is advisory and cannot establish completion.

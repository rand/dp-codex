# Contributor Handbook

## Environment

1. `uv sync --dev`
2. `bd ready`
3. `make check`

## Work Intake And Closure

1. Start from `bd ready`.
2. Claim work with `bd update <id> --status in_progress`.
3. Keep task scope tight and verifiable.
4. Close with explicit rationale and verification evidence.
5. Run `bd sync` after close.

## Code Change Rules

1. Behavior changes require tests in the same change.
2. JSON output changes require schema/docs updates.
3. Keep deterministic command behavior and clear exit semantics.
4. Prefer reproducible commands over one-off local tricks.

## Session Landing

1. `git status`
2. `bd sync`
3. `git add ...`
4. `git commit -m "type: summary"`
5. `git pull --rebase`
6. `git push`

No stranded local commits. We ship or we keep working.

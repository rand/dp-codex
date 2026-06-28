# Adopting dp In An Existing Project

1. Run `dp adopt inspect --json`.
2. Review the classification and instruction/hook hints.
3. Run `dp instructions audit --json`.
4. Write a plan with `dp adopt plan --write --json`.
5. Review `docs/migrations/MIGRATION-*.json` and `.md`.
6. Dry-run apply with `dp adopt apply <plan.json> --json`.
7. Apply only explicit apply-mode changes with `dp adopt apply <plan.json> --apply --json`.
8. Run `dp adopt verify --json`.

Do not overwrite `AGENTS.md`. Preserve legacy artifacts unless the plan explicitly records how they
are being superseded.

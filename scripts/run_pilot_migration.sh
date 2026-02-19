#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pilot_root="$(mktemp -d)"
trap 'rm -rf "${pilot_root}"' EXIT
pilot_repo="${pilot_root}/pilot-repo"
python_bin="${repo_root}/.venv/bin/python"

if [[ ! -x "${python_bin}" ]]; then
  echo "Missing Python runtime at ${python_bin}. Run 'uv sync --dev' first." >&2
  exit 2
fi

run_dp() {
  PYTHONPATH="${repo_root}" "${python_bin}" -m dp.cli "$@"
}

step() {
  echo
  echo "==> $*"
  "$@"
}

mkdir -p "${pilot_repo}"
cd "${pilot_repo}"
export UV_CACHE_DIR="${pilot_repo}/.uv-cache"

mkdir -p "${pilot_repo}/.bin"
cat > "${pilot_repo}/.bin/dp" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH="${repo_root}" "${python_bin}" -m dp.cli "\$@"
EOF
chmod +x "${pilot_repo}/.bin/dp"
export PATH="${pilot_repo}/.bin:${PATH}"

step git init -q
step git config user.email "pilot@example.com"
step git config user.name "Pilot User"
step bd init -q -p pilot

issue_id="$(bd q "Pilot migration walkthrough")"
echo
echo "Created issue: ${issue_id}"

mkdir -p docs/specs dp/core docs/verify artifacts

cat > Makefile <<'EOF'
.PHONY: lint typecheck test

lint:
	@echo "lint-pass"

typecheck:
	@echo "typecheck-pass"

test:
	@echo "test-pass"
EOF

cat > dp-policy.json <<'EOF'
{
  "mode": "guided",
  "overrides": {
    "review": true,
    "verify": true
  }
}
EOF

cat > docs/specs/pilot.md <<'EOF'
# Pilot Spec

[SPEC-01.01] Pilot repository demonstrates a complete disciplined loop.
EOF

cat > dp/core/pilot_feature.py <<'EOF'
# @trace SPEC-01.01
def pilot_feature() -> str:
    return "ok"
EOF

cat > artifacts/proof.txt <<'EOF'
pilot-proof
EOF

cat > docs/verify/manifest.json <<'EOF'
{
  "truths": [
    {"id": "T1", "verified": true}
  ],
  "artifacts": [
    {"id": "A1", "path": "artifacts/proof.txt"}
  ],
  "links": [
    {"truth_id": "T1", "artifact_id": "A1"}
  ]
}
EOF

step run_dp task ready --json
step run_dp task show "${issue_id}" --json
step run_dp task update "${issue_id}" --status in_progress --json
step run_dp trace coverage --json --spec-glob 'docs/specs/**/*.md' --trace-glob 'dp/**/*.py'
step run_dp trace validate --json --spec-glob 'docs/specs/**/*.md' --trace-glob 'dp/**/*.py'
step run_dp adr create "Pilot architecture decision" --json
step run_dp decompose --item "Implement pilot workflow" --preset codex-small --json
step run_dp progress --output-dir docs/progress --json
step run_dp enforce pre-commit --policy dp-policy.json --json

step git add .
step git commit -q -m "pilot: complete disciplined workflow"

step run_dp review --json
step run_dp verify --manifest docs/verify/manifest.json --json
step run_dp enforce pre-push --policy dp-policy.json --json
step run_dp task close "${issue_id}" --reason "Pilot loop completed end to end" --json

echo
echo "Pilot repository completed successfully: ${pilot_repo}"

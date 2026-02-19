#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
hooks_dir="${repo_root}/.git/hooks"
source_dir="${repo_root}/hooks"

mkdir -p "${hooks_dir}"
ln -sf "${source_dir}/pre-commit" "${hooks_dir}/pre-commit"
ln -sf "${source_dir}/pre-push" "${hooks_dir}/pre-push"

chmod +x "${source_dir}/pre-commit" "${source_dir}/pre-push"
echo "Installed dp hooks in ${hooks_dir}"

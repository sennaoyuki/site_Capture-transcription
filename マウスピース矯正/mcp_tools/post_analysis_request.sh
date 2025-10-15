#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ANALYSIS_PATH="${PROJECT_ROOT}/output/latest/analysis_request.md"

if [[ ! -f "${ANALYSIS_PATH}" ]]; then
  echo "analysis_request.md not found. Run run_full_pipeline.sh first." >&2
  exit 1
fi

cat "${ANALYSIS_PATH}"

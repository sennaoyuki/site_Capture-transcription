#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ $# -lt 3 ]]; then
  echo "Usage: ${BASH_SOURCE[0]} <url> <keyword> <conversion-goal>" >&2
  exit 1
fi

URL="$1"
KEYWORD="$2"
CONVERSION_GOAL="$3"

python3 "${PROJECT_ROOT}/run_full_pipeline.py" \
  --url "${URL}" \
  --keyword "${KEYWORD}" \
  --conversion-goal "${CONVERSION_GOAL}"

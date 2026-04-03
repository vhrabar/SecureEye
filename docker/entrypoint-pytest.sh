#!/usr/bin/env bash
set -euo pipefail

cd /workspace
export PYTHONPATH="/workspace/secureEye/src:${PYTHONPATH:-}"

exec pytest "$@"


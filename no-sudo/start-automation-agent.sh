#!/usr/bin/env bash

set -euo pipefail

echo "Starting automation agent..."
nohup "${HOME}/automation-agent/mongodb-mms-automation-agent" --config "${HOME}/automation-agent/local.config" >> "${HOME}/logs/automation-agent-fatal.log" 2>&1 &

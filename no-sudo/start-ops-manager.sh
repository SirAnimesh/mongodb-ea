#!/usr/bin/env bash

set -euo pipefail

echo "Starting Ops Manager database..."
"${HOME}/mongodb/bin/mongod" \
  --dbpath "${HOME}/mongo-data" \
  --logpath "${HOME}/mongo-logs/mongod.log" \
  --fork \
  --bind_ip "127.0.0.1" \
  --port 27017 \
  --replSet opsmgrRS

echo "Starting Ops Manager..."
"${HOME}/ops-manager/bin/mongodb-mms" start

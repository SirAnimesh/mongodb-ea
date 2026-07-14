#!/usr/bin/env bash

set -euo pipefail
# The internal field separator determines how Bash splits words.
# Default includes spaces, which causes issues when iterating over filepaths containing spaces.
# Restrict it to newlines and tabs
IFS=$'\n\t'  

# --- Configuration ---

readonly ARCHIVE_DIR="${HOME}/downloads"
readonly DB_INSTALL_DIR="${HOME}/mongodb"
readonly DB_ARCHIVE_NAME="mongodb-linux-x86_64-enterprise-rhel93-8.3.4.tgz"
readonly FULL_DB_ARCHIVE_PATH="${ARCHIVE_DIR}/${DB_ARCHIVE_NAME}"
readonly DB_DATA_DIR="${HOME}/mongo-data"
readonly DB_LOG_DIR="${HOME}/mongo-logs"

if [[ ! -f "${FULL_DB_ARCHIVE_PATH}" ]]; then
  echo "ERROR: MongoDB tarball not found at ${FULL_DB_ARCHIVE_PATH}" >&2
  exit 1
fi

echo "Extracting MongoDB to ${DB_INSTALL_DIR}..."
mkdir -p "${DB_INSTALL_DIR}" "${DB_DATA_DIR}" "${DB_LOG_DIR}"
tar -xzf "${FULL_DB_ARCHIVE_PATH}" -C "${DB_INSTALL_DIR}" --strip-components=1

# --- Starting MongoDB replica set ---

echo "Starting MongoDB daemon (mongod)..."

"${DB_INSTALL_DIR}/bin/mongod" \
  --dbpath "${DB_DATA_DIR}" \
  --logpath "${DB_LOG_DIR}/mongod.log" \
  --fork \
  --bind_ip "127.0.0.1" \
  --port 27017 \
  --replSet opsmgrRS

echo "MongoDB started. Replica set yet to be initialised..."

# --- Install Mongo Shell (mongosh) ----

readonly MONGOSH_ARCHIVE="mongosh-2.9.2-linux-x64.tgz"
readonly FULL_MONGOSH_ARCHIVE_PATH="${ARCHIVE_DIR}/${MONGOSH_ARCHIVE}"
readonly MONGOSH_INSTALL_DIR="${HOME}/mongosh"

if [[ ! -f "${FULL_MONGOSH_ARCHIVE_PATH}" ]]; then
  echo "ERROR: Mongo Shell tarball not found at ${FULL_MONGOSH_ARCHIVE_PATH}" >&2
  exit 1
fi

echo "Extracting Mongo Shell to ${MONGOSH_INSTALL_DIR}..."
mkdir -p "${MONGOSH_INSTALL_DIR}"
tar -xzf "${FULL_MONGOSH_ARCHIVE_PATH}" -C "${MONGOSH_INSTALL_DIR}" --strip-components=1

echo "Mongo Shell installed at ${MONGOSH_INSTALL_DIR}"

# --- Initialise MongoDB replica set ---

echo "Initialising MongoDB replica set..."

# Give mongod daemon time to fully bind to port
sleep 2

# --quiet suppresses the large MongoDB ASCII art banner
# --eval executes the javascript code passed as argument
"${MONGOSH_INSTALL_DIR}/bin/mongosh" mongodb://127.0.0.1:27017 --quiet --eval 'rs.initiate()'

echo "Waiting for replica set to be healthy..."

sleep 5

echo "Replica set status"
"${MONGOSH_INSTALL_DIR}/bin/mongosh" mongodb://127.0.0.1:27017 --quiet --eval 'rs.status()'

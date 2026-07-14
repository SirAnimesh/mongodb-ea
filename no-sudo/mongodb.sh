#!/usr/bin/env bash

set -euo pipefail

# Increase the maximum number of open file descriptors for this shell session
# 64000 is the recommended minimum for MongoDB
ulimit -n 64000

# The internal field separator determines how Bash splits words.
# Default includes spaces, which causes issues when iterating over filepaths containing spaces.
# Restrict it to newlines and tabs
IFS=$'\n\t'  

# --- Configuration ---

readonly ARCHIVE_DIR="${HOME}/Downloads"
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
  --port 27017 

echo "MongoDB started. Waiting for it to be healthy..."
sleep 5

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

echo "MongoDB health status:"
"${MONGOSH_INSTALL_DIR}/bin/mongosh" --quiet --eval 'db.runCommand({ ping: 1 })'

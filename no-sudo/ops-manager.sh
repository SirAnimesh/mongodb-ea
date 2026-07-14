#!/usr/bin/env bash

set -euo pipefail
# The internal field separator determines how Bash splits words.
# Default includes spaces, which causes issues when iterating over filepaths containing spaces.
# Restrict it to newlines and tabs
IFS=$'\n\t'  

# --- Configuration ---

readonly ARCHIVE_DIR="${HOME}/Downloads"
readonly INSTALL_DIR="${HOME}/ops-manager"
readonly ARCHIVE_NAME="mongodb-mms-8.0.25.500.20260703T0841Z.tar.gz"
readonly FULL_ARCHIVE_PATH="${ARCHIVE_DIR}/${ARCHIVE_NAME}"
readonly CONFIG_FILE="${INSTALL_DIR}/conf/mms.conf"
readonly PROPERTIES_FILE="${INSTALL_DIR}/conf/conf-mms.properties"

if [[ ! -f "${FULL_ARCHIVE_PATH}" ]]; then
  echo "ERROR: Ops Manager tarball not found at ${FULL_ARCHIVE_PATH}" >&2
  exit 1
fi

# --- Installation ---

echo "Extracting Ops Manager to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
tar -xzf "${FULL_ARCHIVE_PATH}" -C "${INSTALL_DIR}" --strip-components=1
cp "${ARCHIVE_DIR}"/mongodb_version_manifest.json" "${INSTALL_DIR}/conf/mongodb_version_manifest.json"

echo "Extraction complete"
echo "Configuring Ops Manager..."

# Change default base directory to the installation directory
sed -i "s|^BASE_DIR=.*|BASE_DIR=\"${INSTALL_DIR}\"|" "${CONFIG_FILE}"
# Change default port to 8085
sed -i 's|^BASE_PORT=.*|BASE_PORT="8085"|' "${CONFIG_FILE}"

# Set the Ops Manager URL to localhost:8085
sed -i 's|^mms.centralUrl=.*|mms.centralUrl=http://127.0.0.1:8085|' "${PROPERTIES_FILE}"
# Point Ops Manager to the local MongoDB replica set
sed -i 's|^mongo.mongoUri=.*|mongo.mongoUri=mongodb://127.0.0.1:27017|' "${PROPERTIES_FILE}"

# Enable Local Mode so Ops Manager serves MongoDB binaries to agents without internet
cat >> "${PROPERTIES_FILE}" << EOF

# Local Mode
automation.versions.source=local
automation.versions.directory=${HOME}/mongodb-binaries

# Agent defaults
automation.default.monitoringAgentLogFile=${HOME}/logs/automation-agent.log
automation.default.backupAgentLogFile=${HOME}/backups/local.config.backup
automation.default.downloadBase=${HOME}/binaries
automation.default.dataRoot=${HOME}/data
EOF

# --- Start Ops Manager ---

"${INSTALL_DIR}/bin/mongodb-mms" start

echo "Ops Manager started at http://localhost:8085. Check ${INSTALL_DIR}/logs/mms0.log for status"

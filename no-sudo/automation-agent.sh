#!/usr/bin/env bash

set -euo pipefail
# The internal field separator determines how Bash splits words.
# Default includes spaces, which causes issues when iterating over filepaths containing spaces.
# Restrict it to newlines and tabs
IFS=$'\n\t'  

# --- Configuration ---

readonly ARCHIVE_DIR="${HOME}/downloads"
readonly INSTALL_DIR="${HOME}/automation-agent"
readonly ARCHIVE_NAME="mongodb-mms-automation-agent-latest.rhel8_x86_64.tar.gz"
readonly FULL_ARCHIVE_PATH="${ARCHIVE_DIR}/${ARCHIVE_NAME}"
readonly CONFIG_FILE="${INSTALL_DIR}/local.config"

readonly LOGS_DIR="${HOME}/logs"
readonly BACKUPS_DIR="${HOME}/backups"
readonly BINARIES_DIR="${HOME}/binaries"
readonly DATA_DIR="${HOME}/data"

# Get these from Ops Manager UI
readonly PROJECT_ID="<REPLACE_WITH_MMS_GROUP_ID>"
readonly AGENT_API_KEY="<REPLACE_WITH_AGENT_API_KEY>"

if [[ ! -f "${FULL_ARCHIVE_PATH}" ]]; then
  echo "ERROR: Automation agent tarball not found at ${FULL_ARCHIVE_PATH}" >&2
  exit 1
fi

echo "Extracting automation agent to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
tar -xzf "${FULL_ARCHIVE_PATH}" -C "${INSTALL_DIR}" --strip-components=1

echo "Creating agent directories..."
mkdir -p "${LOGS_DIR}" "${BACKUPS_DIR}" "${BINARIES_DIR}" "${DATA_DIR}"

# Set the URL to point to Ops Manager
sed -i "s|^mmsBaseUrl=.*|mmsBaseUrl=http://localhost:8085|" "${CONFIG_FILE}"

# Inject credentials
sed -i "s|^mmsGroupId=.*|mmsGroupId=${PROJECT_ID}|" "${CONFIG_FILE}"
sed -i "s|^mmsApiKey=.*|mmsApiKey=${AGENT_API_KEY}|" "${CONFIG_FILE}"

# Write internal agent log to the logs directory
sed -i "s|^logFile=.*|logFile=${LOGS_DIR}/automation-agent.log|" "${CONFIG_FILE}"

# Store agent config backup in the backups directory
sed -i "s|^mmsConfigBackup=.*|mmsConfigBackup=${BACKUPS_DIR}/local.config.backup|" "${CONFIG_FILE}"

# --- Start automation agent ---

echo "Starting Automation Agent..."
nohup "${INSTALL_DIR}/mongodb-mms-automation-agent" --config "${CONFIG_FILE}" >> "${LOGS_DIR}/automation-agent-fatal.log" 2>&1 &
echo "Agent started in the background. Check ${LOGS_DIR}/automation-agent-fatal.log"

#!/bin/bash
set -euxo pipefail

# --- Detect guest architecture ---

ARCH="$(uname -m)"
case "$ARCH" in
  aarch64) OS="amzn2" ;;
  x86_64)  OS="rhel9" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

# --- Download agent package ---

VERSION="13.53.0.10826-1"
PKG="mongodb-mms-automation-agent-manager-${VERSION}.${ARCH}.${OS}.rpm"
URL="https://cloud.mongodb.com/download/agent/automation/${PKG}"

cd /tmp
curl -OL "$URL"

# --- Install the agent ---

dnf install -y "/tmp/${PKG}"
install -o mongod -g mongod -m 0600 /root/automation-agent.config.staged /etc/mongodb-mms/automation-agent.config
mkdir -p /data
chown mongod:mongod /data
systemctl enable --now mongodb-mms-automation-agent.service

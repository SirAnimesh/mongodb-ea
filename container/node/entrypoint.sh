#!/bin/bash
set -e

OM_URL="http://ops-manager:8080"

echo "==> Waiting for Ops Manager at ${OM_URL}..."
until curl -s -o /dev/null "${OM_URL}/api/public/v1.0"; do
  echo "  Ops Manager not ready yet, retrying in 5s..."
  sleep 5
done
echo "  Ops Manager is ready."

if [ ! -f /opt/mongodb-mms-automation/bin/mongodb-mms-automation-agent ]; then
  echo "==> Downloading Automation Agent from Ops Manager..."
  ARCH=$(dpkg --print-architecture)

  . /etc/os-release
  OS_VER="ubuntu$(echo "$VERSION_ID" | tr -d '.')"

  DEB="mongodb-mms-automation-agent-manager_latest_${ARCH}.${OS_VER}.deb"
  URL="${OM_URL}/download/agent/automation/${DEB}"

  echo "  Fetching $URL ..."
  curl -sSfOL --retry 5 --retry-delay 5 "$URL"

  echo "  Installing..."
  dpkg -i "$DEB"
  rm -f "$DEB"
  chown -R mongodb:mongodb /var/lib/mongodb-mms-automation /var/log/mongodb-mms-automation /etc/mongodb-mms
  echo "  Agent installed."
fi

echo "==> Configuring agent..."
cat > /etc/mongodb-mms/automation-agent.config << EOF
mmsGroupId=${MMS_GROUP_ID}
mmsApiKey=${MMS_API_KEY}
mmsBaseUrl=${OM_URL}
EOF

echo "==> Starting agent..."
exec /opt/mongodb-mms-automation/bin/mongodb-mms-automation-agent -config /etc/mongodb-mms/automation-agent.config

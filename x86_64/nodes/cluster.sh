#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# --- Load secrets ---

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $(pwd). Copy your Ops Manager Group ID and API key into it." >&2
  exit 1
fi

set -a
source .env
set +a

# --- Launch nodes ---

for n in node1 node2 node3; do
  echo ">>> Launching $n ..."
  limactl start --name="$n" \
    --tty=false \
    mongod.yaml
done

# --- Wire up inter-node name resolution ---

echo ">>> Collecting node IPs and writing /etc/hosts ..."
HOSTS_BLOCK=""
for n in node1 node2 node3; do
  ip=$(limactl shell "$n" -- ip -4 -o addr show | grep -oE '192\.168\.104\.[0-9]+' | head -1)
  if [[ -z "$ip" ]]; then
    echo "ERROR: could not determine user-v2 IP for $n" >&2
    exit 1
  fi
  HOSTS_BLOCK="${HOSTS_BLOCK}${ip} lima-${n}"$'\n'
done

for n in node1 node2 node3; do
  printf "%s" "$HOSTS_BLOCK" | limactl shell "$n" -- sudo tee -a /etc/hosts > /dev/null
  
  echo ">>> Injecting Ops Manager credentials into $n ..."
  limactl shell "$n" -- sudo sed -i "s/^mmsGroupId=.*/mmsGroupId=$MMS_GROUP_ID/" /etc/mongodb-mms/automation-agent.config
  limactl shell "$n" -- sudo sed -i "s/^mmsApiKey=.*/mmsApiKey=$MMS_API_KEY/" /etc/mongodb-mms/automation-agent.config
  limactl shell "$n" -- sudo systemctl restart mongodb-mms-automation-agent
done

# --- Report ---

echo
echo "All three nodes launched and registered with Ops Manager"
echo "Next: Open your Ops Manager project and use Deploy -> Replica Set"
echo "to build a 3-node replica set across node1, node2, node3"

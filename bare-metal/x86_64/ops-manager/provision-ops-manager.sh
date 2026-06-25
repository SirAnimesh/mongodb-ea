#!/bin/bash
set -eux -o pipefail

# Rate-limit dnf and disable parallel downloads to prevent QEMU network panics (see longer note below)
echo "throttle=20M" | sudo tee -a /etc/dnf/dnf.conf
echo "max_parallel_downloads=1" | sudo tee -a /etc/dnf/dnf.conf

echo ">>> Setting up MongoDB repository for AppDB..."
cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-8.0.repo
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/8.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-8.0.asc
EOF

echo ">>> Installing and starting MongoDB (AppDB)..."
sudo dnf install -y mongodb-org
sudo systemctl enable --now mongod

echo ">>> Downloading Ops Manager..."
# There is a known bug in QEMU's user-mode networking stack (SLIRP).
# When a VM tries to download a massive file, the network state machine gets desynchronized and triggers a hard assertion 
# failure to prevent memory corruption. It looks like this in `~/.lima/<vm-nam>/ha.stderr.log`:
#     qemu[stderr]: qemu-system-x86_64: ../net/net.c:2172: net_fill_rstate: Assertion `size == 0' failed.
#
# This crashes the entire VM. Ops Manager RPM is ~2.4GB which triggers this bug when curl runs inside the guest.
# Once this bug is fixed, remove the rate-limiting.
OM_VERSION="8.0.24.500.20260610T1425Z"
OM_RPM="mongodb-mms-${OM_VERSION}.x86_64.rpm"
OM_URL="https://downloads.mongodb.com/on-prem-mms/rpm/${OM_RPM}"
curl --limit-rate 20M -LO "$OM_URL"

echo ">>> Installing Ops Manager..."
sudo dnf install -y "./$OM_RPM"

echo ">>> Starting Ops Manager..."
# Ops Manager's default configuration tries to allocate 8GB memory heap for Java by default, reduce it 1.5 GB
sudo sed -i 's/MMS_HEAP_SIZE=${MMS_HEAP_SIZE:-8096}/MMS_HEAP_SIZE=${MMS_HEAP_SIZE:-1500}/' /opt/mongodb/mms/conf/mms.conf
sudo systemctl enable --now mongodb-mms

echo ">>> Ops Manager provisioning complete! It may take a few minutes for the web interface to start up."

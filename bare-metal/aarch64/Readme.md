# MongoDB on ARM

Ops Manager has no ARM64 build. This `aarch64` demo natively delivers:

- a 3-node replica set
- MongoDB agent on each node
- management using Cloud Manager

## Pre-requisites

### VM Manager

Install [`lima`](https://lima-vm.io/) and run a smoke test to verify that it is set up fine.

```shell
limactl start --list-templates                # Make sure rocky-9 is on the list
limactl start --name=smoke template:rocky-9

limactl shell smoke uname -m                  # confirm arch matches host, on Silicon Macs, should say aarch64
limactl shell smoke cat /etc/os-release       # confirms Rocky 9

limactl stop smoke
limactl delete smoke
```

### Cloud Manager

Cloud Manager is a SaaS tool for managing your MongoDB installation.

1. Go to [`cloud.mongodb.com`](https://cloud.mongodb.com/) and sign in, if you have an Atlas account that'd work here too
2. Create a new Cloud Manager organisation - `EA Demo`
3. Create a new project - `arm64`
3. Make note of **Project ID** and generate an **Agent API Key** in Project Settings

A node's MongoDB Agent will need project ID and API key to register itself with Cloud Manager.

Create a `.env` file:

```
MMS_GROUP_ID=xxxx
MMS_API_KEY=xxxx
```

## Workflow

1. `cloud-init` (by Lima) installs the MongoDB agent and registers it to a Cloud Manager project
2. You build the replica set from the Cloud Manager UI (`Deploy -> Replica Set`)
3. Cloud Manager pushes the binaries and config to the agents

This mimics how a real EA customer operates with Cloud Manager. It allows you to provision a cluster from the control 
plane with no SSH.

### Start the nodes

`mongod.yaml` is the single source of truth. Secrets are read from `.env` and injected as Lima params at
create time — they are never stored in the template.

```shell
set -a; . ./.env; set +a            # load MMS_GROUP_ID / MMS_API_KEY into the shell

for n in mongo1 mongo2 mongo3; do
  limactl start --name="$n" \
    --param MMS_GROUP_ID="$MMS_GROUP_ID" \
    --param MMS_API_KEY="$MMS_API_KEY" \
    --tty=false \
    mongod.yaml
done
```

> Lima bakes provisioning in at **create time only**. Editing `mongod.yaml` does not touch a running VM —
> `limactl delete <name>` and re-create it to pick up changes.

### Verify

```shell
# Check if provisioning completed successfully
limactl shell mongo1 -- cloud-init status --wait

# Check if the agent service is running
limactl shell mongo1 -- systemctl is-active mongodb-mms-automation-agent

# Get agent's log
limactl shell mongo1 -- sudo tail -50 /var/log/mongodb-mms-automation/automation-agent.log
```
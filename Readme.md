# MongoDB in a box

This repository provides five independent approaches to stand up a MongoDB Enterprise Advanced cluster. All share the 
same fundamental architecture:

```
Ops Manager (control plane)  ───  Automation Agents (on each node)  ───  mongod (the database)
```

No matter which model you use, the runtime looks the same:

1. **Control plane** (Ops Manager or Cloud Manager) holds the desired cluster state and pushes configs to agents
2. **Automation Agent** on each node registers with the control plane via `mmsBaseUrl` + API key
3. Agent downloads MongoDB binaries, writes config files, and manages `mongod` as a child process
4. You deploy replica sets / sharded clusters from the Ops Manager or Cloud Manager web UI

### Key Gotchas

- **Kernel ≥ 6.19**: MongoDB 8.0 crashes due to `tcmalloc`; blocked by `script.py`
- **QEMU SLIRP bug**: Large downloads inside Lima VMs crash the VM; worked around with rate-limiting
- **No ARM64 Ops Manager**: Must use Cloud Manager on `aarch64`
- **Docker Compose is for demos only**; no orchestration, no failover
- **`no-sudo` has no elevated fd limits**; risks throttling under load

## Deployment Models

### 1. `container/` — Docker Compose (simplest, for demos)

A single `compose.yaml` spins up 5 containers:

| Container | Role |
|---|---|
| `ops-manager-db` | MongoDB Enterprise Server acting as Ops Manager's backing database (AppDB) |
| `ops-manager` | Self-hosted Ops Manager web UI/control plane (Rocky Linux 9, port 8080) |
| `node1`, `node2`, `node3` | Data-bearing nodes — each runs the **Automation Agent** as the foreground process |

**Key detail:** The agent doesn't just run as a side-service — it *is* the container's entrypoint. It manages `mongod` 
as a child process, so Ops Manager can deploy, configure, and upgrade the database across all three nodes.

The node Dockerfile downloads a pre-built agent `.deb`, and a `script.py` handles kernel compatibility checks (blocks 
Linux 6.19+ due to a `tcmalloc` bug), TLS, initdb, and replica set initiation.

```
compose.yaml  →  node/Dockerfile (agent)  →  ops-manager/Dockerfile (control plane)
                     ↑                         ↑
              script.py (init logic)    .env (MMS_GROUP_ID, MMS_API_KEY)
```

### 2. `x86_64/` — Lima VMs simulating bare metal (x86_64)

Uses [Lima](https://lima-vm.io) to create lightweight Rocky Linux 9 VMs on a single host. Two VM types:

| VM | Resources | Config |
|---|---|---|
| Ops Manager VM | 2 CPU, 4GB RAM, 30GB disk | `ops-manager/ops-manager.yaml` |
| 3× Node VMs | 1 CPU, 2GB RAM, 20GB disk each | `nodes/mongod.yaml` |

**Orchestration flow managed by `nodes/cluster.sh`:**
1. Launches 3 node VMs with `limactl`
2. Reads the `user-v2` network IPs (192.168.104.x) for each VM
3. Writes `/etc/hosts` entries so nodes can reach each other by name
4. Injects `MMS_GROUP_ID` and `MMS_API_KEY` into each node's agent config file
5. Restarts each agent so it registers with Ops Manager

**Provisioning scripts** (`provision-ops-manager.sh`, `provision-agent.sh`) handle `dnf` repo setup, RPM installation, 
systemd service creation, and a critical workaround: **rate-limiting all downloads** to 20MB/s to avoid a QEMU SLIRP 
networking bug that crashes VMs when transferring large files (like the 2.4GB Ops Manager RPM).

```
lima-on-fedora.sh  →  ops-manager.yaml  →  provision-ops-manager.sh
                                        →  mongod.yaml  →  provision-agent.sh
                                        →  cluster.sh (orchestrator)
```

### 3. `aarch64/` — Lima VMs targeting ARM64 with Cloud Manager

Since Ops Manager has **no ARM64 build**, this variant substitutes **Cloud Manager** (MongoDB's SaaS control plane at 
`cloud.mongodb.com`) instead of self-hosting Ops Manager. The architecture is otherwise identical, but `cluster.sh` 
passes `MMS_GROUP_ID`/`MMS_API_KEY` as `limactl` params at create time (sourcing from `.env`).

### 4. `no-sudo/` — Tarball-based, air-gapped, no root

For environments with **no internet and no `sudo`**. Everything is pre-downloaded tarballs extracted under `$HOME`:

| Script | What it installs |
|---|---|
| `mongodb.sh` | MongoDB Enterprise Server as AppDB, initiates a single-node replica set (`opsmgrRS`) |
| `ops-manager.sh` | Ops Manager from tarball, reconfigures Java heap, points at AppDB |
| `automation-agent.sh` | Agent on each data node, configured to talk to the Ops Manager host |
| `start-ops-manager.sh` / `start-automation-agent.sh` | `cron @reboot` survival scripts (no systemd) |

No `/etc/security/limits.conf` edits possible, so file descriptor limits stay low which is not recommended for production.

### 5. `kubernetes/`

Intended for the MongoDB Enterprise Kubernetes Operator, but not yet implemented.

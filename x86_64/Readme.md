# MongoDB on x86

This `x86_64` demo natively delivers:

- a 3-node replica set
- MongoDB agent on each node
- management using [Ops Manager](https://www.mongodb.com/docs/ops-manager/current/?msockid=24798157dea1691f00429729dffd68d2)

```shell
cd ./ops-manager
limactl start ops-manager.yaml

# Wait a few minutes then visit http://localhost:8080 and register with any username/password
# After initial setup, copy Project ID and Agent API key from Project Settings

cd ../nodes
touch .env             # set MMS_GROUP_ID (Project ID) and MMS_API_KEY
./cluster.sh           # launch and configure nodes (this may take 20-30 minutes)

# Check status
limactl list
limactl shell ops-manager systemctl status mongod
limactl shell ops-manager systemctl status mongodb-mms
```

## Pre-requisites

### Install hypervisor (only for Linux)

Lima is a lightweight orchestrator and wrapper. It delegates running VMs to a hypervisor. 

On Windows, Lima uses WSL2. On macOS, Lima uses `Virtualization.framework`.

On Linux, Lima natively targets QEMU using KVM (Kernel-based Virtual Machine). KVM allows QEMU to execute guest code 
directly on the host CPU, giving you near-bare-metal performance.

```shell
sudo dnf install -y qemu-kvm qemu-system-x86
```

> [!WARNING]
> There is a known bug in QEMU's user-mode networking stack (SLIRP).
> When a VM tries to download a massive file, the network state machine gets desynchronized and triggers a hard assertion 
> failure to prevent memory corruption. This crashes the entire VM.
> 
> Ops Manager RPM is ~2.4GB which triggers this bug when curl runs inside the guest. As a workaround, all VMs in this
> directory are rate-limited. So if you find yourself waiting a long time to see 2.5GBs downloaded on a gigabit connection,
> that's by design, get used to it.

### VM Manager

Install [`lima`](https://lima-vm.io/) and run a smoke test to verify that it is set up fine. Because I'm a nice and cuddly
Fedora user, run [Lima on Fedora](lima-on-fedora.sh) script.

```shell
limactl start --list-templates                # Make sure rocky-9 is on the list
limactl start --name=smoke template:rocky-9

limactl shell smoke uname -m                  # confirm arch matches host, on Silicon Macs, should say aarch64
limactl shell smoke cat /etc/os-release       # confirms Rocky 9

limactl stop smoke
limactl delete smoke
```

If this works, you're ready to install MongoDB components.

## Architecture

![Cluster architecture](https://www.mongodb.com/docs/platform/api/images/ops-manager/current/images/how-it-works-ops.png)

We deploy a simple 3-node replica set with Ops Manager controlling the cluster.

We start with the orchestrator - [Ops Manager](https://www.mongodb.com/docs/ops-manager/current/?msockid=24798157dea1691f00429729dffd68d2).
It's the GUI control plane of your cluster. Under the hood, it requires its own dedicated application database to store
metrics, state and metadata.

Then `./nodes/cluster.sh` takes care of deploying the 3-node replica set. Once the nodes are up and running, they will
phone home to Ops Manager and show up in the Ops Manager UI under Servers.

You build the replica set from the Ops Manager UI (`Deploy -> Replica Set`). Ops Manager pushes the binaries and config 
to the agents. Job done.

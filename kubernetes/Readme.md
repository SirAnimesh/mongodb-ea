# Kubernetes

Docker Compose in the [container](../container/) demo is a single-machine orchestrator. It applies `compose.yaml` to
start containers on one host (your laptop) and wires them together. It is good for development and single-host
testing.

[Kubernetes](https://kubernetes.io) is a **cluster orchestrator**. It manages containers across *multiple* machines. It
is perfect for production multi-node deployments where downtime isn't acceptable.

Running MongoDB on Kubernetes simplifies the setup and management of self-hosting MongoDB. It handles all the lifecycle
logic (replica set initiation, upgrades, backup configuration) that otherwise has to be done through Ops Manager UI.

## Workflow

1. Create a single-node Kubernetes cluster - `kind create cluster`
2. Check it's up and running - `kubectl get nodes` - should see `kind-control-plane` with status `Ready`
3. Create the `mongodb` Kubernetes namespace:
   ```
   kubectl create namespace mongodb
   kubectl config set-context --current --namespace=mongodb
   ```
4. Install the MongoDB operator
   ```
   helm repo add mongodb https://mongodb.github.io/helm-charts
   helm install kubernetes-operator mongodb/mongodb-kubernetes --namespace mongodb
   ```
5. Verify the Operator pod is running. You should see a pod with a name like `mongodb-kubernetes-operator-xxxx` in `Running`
   status.
   ```
   kubectl get pods
   ```
6. Create admin secrets - `kubectl apply -f 01-ops-manager-admin-secret.yaml`
7. Deploy Ops Manager - `kubectl apply -f 02-ops-manager.yaml`
8. Use `kubectl get pods -w` or `kubectl get om -o yaml -w` to track deployment
9. Once Ops Manager is running, get its URL - `kubectl get om ops-manager -o jsonpath='{.status.opsManager.url}'`
10. Forward Ops Manager port for use outside the cluster: `kubectl port-forward svc/ops-manager-svc-ext 8080:8080`
11. Log into Ops Manager at `localhost:8080` using credentials in `01-ops-manager-admin-secret.yaml` and copy the 
    Organization ID and API keys.
12. Paste these values in the appropriate fields in `03-project-configmap.yaml` and `04-api-key-secret.yaml`. **Not doing
    this will break your deployment**.
13. Deploy replica set: `kubectl apply -f 05-replicaset.yaml`.
14. Track deployment `kubectl get mdb -o yaml -w` and wait for `status.phase` to turn `Running`. OR watch the pods come
    up `kubectl get pods -w`.
15. Finally, create the database user: `kubectl apply -f 06-db-user-secret.yaml -f 07-mongodb-user.yaml`.

The Operator is the bridge between two domains: Kubernetes and MongoDB. It translates simple YAMLs into the complex
sequence of API calls and infrastructure changes needed to deploy MongoDB properly on Kubernetes.

> [!important]
> Kubernetes is fiddly and there are many ways to break it. The above list is the happiest path, you'll likely veer away 
> from it. Fret not, ask your AI what to do when you get stuck. It's usually a config field or two that spoils the party.
> See [Gotchas](https://github.com/SirAnimesh/mongodb-ea/tree/main/kubernetes#gotchas-ai-generated-may-have-errors)

## Pre-requisites

The tech stack:

- `docker` v29.6.1, to run containers on your machine
- `kind` v0.32.0, creates and manages local Kubernetes cluster
- `kubectl` v1.36.2, talks to cluster API
- `helm` v4.2.2, package manager

### Kubernetes

At a hardware level, a Kubernetes cluster is two things:

- **control plane**: one or more machines running the *brain*, i.e. the Kubernetes API server, scheduler etc.
- **worker nodes**: the machines that actually run application containers

You send commands to the Control plane. You tell it *"I want 3 copies of this container"* and it decides where and how
to put them up.

In Docker, the smallest unit of work is a container. In Kubernetes, the smallest deployable unit is a **Pod**. A pod is
a group of one or more containers that share a network namespace and storage. Most of the time, 1 pod = 1 container. Pods
are ephemeral. They can die and get replaced on a different node.

In a regular `Deployment`, when Kubernetes replaces a dead container, it creates a brand new one. For a stateless web 
server, this is not a problem at all. For a stateful database, this is a disaster. Replica set members have persistent 
data on specific disk, and they need ordered startup/shutdown.

A **`StatefulSet`** guarantees:

- stable network identity: pod names are predictable (`mongo-0`, `mongo-1`, `mongo-2`)
- stable storage: each pod gets its own `PersistentVolume` that sticks to it, even if the pod moves nodes
- ordered deployment: `mongo-0` starts first, becomes healthy, then `mongo-1` etc.
- ordered scaling down: reverse order, gives data time to sync

MongoDB uses `StatefulSet`s under the hood.

### Kubernetes Operator

Kubernetes runs a continuous loop:

```
1. Watch: what's the desired state? (from manifest YAMLs)
2. Observe: what's the actual state? (what's running right now)
3. Diff: are they different?
4. Reconcile: make changes to close the gap
5. Repeat forever
```

Every native Kubernetes resource (`Deployment`, `StatefulSet`, `Service` etc.) has its own **controller** doing this 
loop. They ship with Kubernetes.

But Kubernetes doesn't know what a MongoDB replica set is, and it doesn't know how to initiate one, add members to it,
handle elections, or run backups. That's *domain-specific* logic.

An **operator** is a controller you add *on top* of Kubernetes that:

- extends the API by registering new resource types via custom resource definitions (CRDs)
- contains domain knowledge to ensure that reconciliation loop can do this:
  ```
  loop:
    desired: MongoDB{ members: 3, version: "8.0.0" }
    actual: no pods exist yet

    action: 1. Tell Ops Manager API to deploy a replica set
            2. Ops Manager installs agents on 3 pods
            3. Agents download MongoDB 8.0.0, start mongod
            4. Agents initiate replica set
            5. Wait for PRIMARY election
            6. Mark MongoDB resource as "Running"
    
    desired: MongoDB{ members: 3, version: "8.0.0" }
    actual: mongo-2 crashed

    action: 1. StatefulSet controller replaces the pod
            2. Operator notices new pod
            3. Tell Ops Manager to add the new member to replica set
            4. Trigger initial sync
            5. Wait for member to become SECONDARY

    desired: MongoDB{ members: 3, version: "8.0.1" }
    actual: pods running 8.0.0

    action: 1. Tell Ops Manager: rolling upgrade to 8.0.1
            2. Upgrade secondaries one by one
            3. Step down primary, upgrade it
            4. Mark resource as updated
  ```

### `kubectl`

`kubectl` is the command-line interface for managing Kubernetes. You run `kubectl apply -f manifest.yaml` to create
resources (pods, services, volumes, etc.) from YAML *declaratively*. `manifest.yaml` describes the desired state,
Kubernetes delivers it.

```yaml
apiVersion: <api-group>/<version>          # which API to use
kind: <ResourceType>                       # what kind of thing
metadata:
  name: <name>                             # what to call it
  namespace: <namespace>                   # which namespace
spec:                                      # the desired state
  ...
```

You use `namespace` to isolate resources. Resources in namespace `mongodb` can't see resources in namespace `default`.

```shell
kubectl config set-context --namespace=mongodb
```

### Helm

You *could* write every Kubernetes YAML by hand. For one MongoDB replica set, that's about 15 YAML files - `StatefulSet`,
`Service`, `PVCs`, `ConfigMap`, `Secrets`, RBAC roles, etc.

[Helm](https://helm.sh/docs/intro/introduction) is a package manager and templating engine. It bundles all those YAML 
files into a single installable *chart*. A chart can be versioned, shared, installed, and rolled back as one release.

The MongoDB Operator chart (`mongodb/mongodb-kubernetes`) includes:

- the Operator itself, a pod that watches for MongoDB custom resources
- RBAC permissions, what the Operator is allowed to do in the cluster
- custom resource definitions (CRDs) to teach Kubernetes what a `MongoDB` and `MongoDBOpsManager` resource is
- default configuration

You install it once:

```shell
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install kubernetes-operator mongodb/mongodb-kubernetes
```

After that, Kubernetes understands `kind: MongoDB` and `kind: MongoDBOpsManager`.

### Kind

Kubernetes is designed to run on multiple physical machines. A laptop is just one machine. [kind](https://kind.sigs.k8s.io)
fakes a cluster by running nodes as Docker containers on one machine.

---

## Gotchas (AI generated, may have errors)

These are the non-obvious things that will trip you up on a local Kind cluster.

### Docker memory

Ops Manager alone wants ~5GB of RAM, and MongoDB's docs list **8GB as the bare minimum for just Ops Manager +
AppDB** — before you add a workload replica set. On top of that you're running the Operator pod, a 3-node AppDB, and a
3-node replica set, all on a single Kind node.

Give Docker Desktop at least **16GB** (Settings → Resources → Memory). Kind restarts to pick up the new capacity, which
bounces every pod at once. Check headroom with:

```shell
kubectl describe node kind-control-plane | grep -A 8 "Allocated resources"
```

If memory requests are near 100%, pods crawl or get `OOMKilled` and CrashLoop. You want requests under ~70%.

### API key IP access list

Programmatic API keys in Ops Manager can require an IP access list. The Operator calls the Ops Manager API from *inside*
the cluster using a pod IP, so that IP must be on the list — otherwise the reconcile fails with:

```
Status: 403 (Forbidden), ErrorCode: RESOURCE_REQUIRES_ACCESS_LIST
```

Add the Kind pod CIDR `10.244.0.0/16` to the key's access list (Organization Access Manager → API Keys → Edit → Access
List). The `/16` covers all pods, so it survives the Operator being rescheduled to a new pod IP.

### `ops-manager-0` is the gate

After any node restart, the replica set pods CrashLoop until `ops-manager-0` reaches `1/1`. This is expected — the agents
can't fetch their config from a not-yet-ready Ops Manager. Ops Manager is a heavy Java app and takes several minutes.
Wait for it before debugging the `mongod` pods.

### Wrong project in the UI

The Operator deploys into the project named in `03-project-configmap.yaml` (`projectName: my-project`), which is *not*
the default project. If "Processes" looks empty, switch to `my-project` in the Ops Manager project dropdown.

### Plaintext secrets in git

`01-ops-manager-admin-secret.yaml`, `04-api-key-secret.yaml`, and `06-db-user-secret.yaml` contain plaintext
credentials. Do not commit real values — use placeholders or `.gitignore`, or a sealed-secrets tool for anything real.

### Connecting with `mongosh`

If your password contains `!`, zsh treats it as history expansion and throws `event not found`. Wrap the connection
string in **single quotes**:

```shell
mongosh 'mongodb://mms-scram-user-1:DemoPassword123!@localhost:27017/admin'
```

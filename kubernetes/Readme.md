# Kubernetes

Docker Compose in the [container](../container/) demo is a single-machine orchestrator. It applies `compose.yaml` to
start containers on one host (your laptop) and wires them together. It is good for development and single-host
testing.

[Kubernetes](https://kubernetes.io) is a **cluster orchestrator**. It manages containers across *multiple* machines. It
is perfect for production multi-node deployments where downtime isn't acceptable.

Running MongoDB on Kubernetes simplifies the setup and management of self-hosting MongoDB. It handles all the lifecycle
logic (replica set initiation, upgrades, backup configuration) that otherwise has to be done through Ops Manager UI.

## Workflow

1. Create a Kubernetes cluster - `kind create cluster`
2. `helm install kubernetes-operator`
3. `kubectl apply -f ops-manager.yaml`
    - Operator sees a `MongoDBOpsManager` resource
    - Operator creates `StatefulSet` for AppDB, Deployment for Ops Manager, Services, PVCs, Secrets
    - Everything converges to "Running"
4. `kubectl apply -f mongodb-replicaset.yaml`
    - Operator sees a MongoDB resource
    - Operator talks to Ops Manager API: "deploy a 3-node replica set"
    - Ops Manager pushes config to automation agents
    - Agents download MongoDB binaries, start `mongod` on each pod
    - `StatefulSet` ensures stable identities: `mongo-0`, `mongo-1`, `mongo-2`
5. `kubectl apply -f mongodb-user.yaml`
    - Operator creates a database user via Ops Manager API

The Operator is the bridge between two domains: Kubernetes and MongoDB. It translates simple YAMLs into the complex
sequence of API calls and infrastructure changes needed to deploy MongoDB properly on Kubernetes.  

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

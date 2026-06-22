# MongoDB Enterprise Advanced

Enterprise Advanced is a **subscription** not a product. It bundles commercially licenced MongoDB Enterprise Server with
a suite of operational tooling. There are no perpetual licences. Customers cannot buy it online, they have to come through
our enterprise Sales channels.

## What's in the box

Every EA subscription includes:

- MongoDB Enterprise Server
- Ops Manager and Cloud Manager
- Enteprise Kubernetes Operator
- BI Connector

The EA differentiation is management tooling, support, security (TDE/Kerberos/auditing) and indemnification.

## Tooling by deployment model

### Bare metal or on a VM

- Enterprise Server binaries: install `mongod` and `mongos` from the tarball archive or distro package
- Ops Manager: the application, its backing database and backup store
- MongoDB Agent: on each host, used by Ops Manager for automation, monitoring and backup
- BI connector if you need SQL/BI access
- Admin tooling:
  - `mongosh` Mongo Shell
  - `mongodump` and `mongorestore` for backups
  - Compass

Customers typically deploy a 3-node replica sets or sharded clusters. See [bare-metal](/bare-metal) for a sample.

### In a container

- `mongodb-enteprise-server` container image
- Persistent volumes - map `/data/db`
- Ops Manager 
- MongoDB Agent in each container
- Admin tooling:
  - `mongosh` Mongo Shell
  - `mongodump` and `mongorestore` for backups
  - Compass

Plain Docker or even Compose gives little in terms of orchestration. It's good for testing or demos, but production workloads
should use Kubernetes. See [container](/container/) for a sample.

### Kubernetes

- MongoDB Controllers for Kubernetes
- Ops Manager in Kubernetes
- Admin Tooling
- Admin tooling:
  - `mongosh` Mongo Shell
  - `mongodump` and `mongorestore` for backups
  - Compass

MongoDB Controllers for Kubernetes is an EA feature. There's a community Kubernetes operator but it does not support 
sharded clusters. To keep us on our toes, there's an Atlas Kubernetes operator as well, but that provisions Atlas clusters
and is not relevant to EA.

See [kubernetes](/kubernetes) for a sample.

---

## Comparison of deployment models (AI generated 2026-06-22)

| Dimension | VM / Bare Metal | Container (Docker / standalone) | Kubernetes |
|---|---|---|---|
| Database engine | Enterprise Server binaries (`mongod`, `mongos`) via tarball or RPM/DEB | `mongodb-enterprise-server` container image | Enterprise Server pods, managed by the Operator |
| Packaging / install | OS packages for RHEL/CentOS, Ubuntu, Debian, SUSE, Amazon Linux, Windows (incl. s390x/ppc64le) | Container image + persistent volume mapped to `/data/db` | StatefulSets + PersistentVolumeClaims, reconciled from Custom Resources |
| Orchestration tool | Ops Manager (self-hosted) or Cloud Manager (SaaS) | None native — single node only; no failover/upgrades | MongoDB Enterprise Kubernetes Operator ("Controllers for Kubernetes") |
| How you deploy | Ops Manager Automation, single-click installs/upgrades | `docker run` / Compose (dev/test) | `kubectl apply` of `MongoDB` / `MongoDBMultiCluster` CRs |
| Control plane required | Ops Manager (needs its own Application DB + backup store) or Cloud Manager | Optional — MongoDB Agent if managed by OM/CM | Ops Manager or Cloud Manager, pointed at via ConfigMap + credentials Secret; OM itself can run in K8s |
| On-host agent | MongoDB Agent (automation + monitoring + backup) per host | MongoDB Agent in container (if OM/CM-managed) | Operator-managed Agent sidecars |
| Monitoring / alerting | Ops Manager / Cloud Manager (100+ metrics, custom alerts) | Via OM/CM if agent attached | Via OM/CM |
| Backup / PITR | Ops Manager / Cloud Manager continuous backup + point-in-time restore | `mongodump` / `mongorestore`, or OM/CM if managed | Via OM/CM |
| HA model | Hand-built 3-node replica sets / sharded clusters | None (single node); not production-suitable | Replica sets, sharded clusters, multi-cluster (GA) for cross-region resilience + auto-remediation |
| Search / Vector Search | Self-managed (Public Preview) | Limited | Self-managed via Operator (Public Preview) |
| Day-to-day tooling | mongosh, MongoDB Database Tools, Compass, BI Connector, mongocli / OM CLI | mongosh, Database Tools, Compass (connect as normal) | mongosh, Database Tools, Compass; `kubectl` for lifecycle |
| Best for | Classic on-prem/private-cloud production | Dev/test, demos, single-node work | Production containers, portability, multi-region |
| Main caveat | Ops Manager is non-trivial to stand up (AppDB + blockstore); attach Professional Services for POCs | No orchestration — no failover, rolling upgrades, or self-healing | Requires OM/CM control plane; use the Enterprise Operator, not the Community one (no sharding, not production-grade) |

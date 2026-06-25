# Going bare

Cross-architecture virtualization (x86 guest on an ARM host, or vice versa) is emulation only. It is too painful and slow
in mainstream tools like VirtualBox or Multipass. Always use same-architecture guests.

Use:
- [x86](./x86_64/) on Intel Macs or other Windows/Linux machines
- [aarch64](./aarch64/) on Apple Silicon Macs and ARM-based Windows/Linux installations
  - **Ops Manager cannot run natively on ARM64**: host it on an x86_64 machine (cloud/on-prem)
  - or use Cloud Manager

## Architecture Support

`aarch64` = Linux on ARM, including Apple Silicon via an ARM64 Linux guest. 

MongoDB does **not** ship Windows/macOS-native server binaries for production; those OS use an ARM64 Linux guest.

## Component matrix

| Component | x86_64 | ARM64 (aarch64) | Notes |
|---|---|---|---|
| MongoDB Enterprise Server (`mongod`, `mongos`) | Yes | Yes | ARM64 builds for Ubuntu 20.04/22.04/24.04, RHEL/CentOS 8/9, Amazon Linux 2023 |
| MongoDB Agent (automation/monitoring/backup) | Yes | Yes | ARM64: RHEL 8/9, Amazon Linux 2/2023, Ubuntu 20.x/22.x/24.x |
| Ops Manager Application (web app + services) | Yes | No | x86_64-only (Intel/AMD). No official ARM64 build. Unofficial `mongodb-labs/omida` Docker image runs on arm64 but is insecure / non-production |
| mongosh (shell) | Yes | Yes | ARM64 Linux + macOS Apple Silicon |
| MongoDB Database Tools (`mongodump`, `mongorestore`, etc.) | Yes | Yes | ARM64 Linux + macOS Apple Silicon |
| Compass (GUI) | Yes | Yes | macOS Apple Silicon native; ARM64 Linux builds available |
| BI Connector (`mongosqld`) | Yes | No | x86_64-only; no ARM64 build. Not supported on Ubuntu 22.04 |

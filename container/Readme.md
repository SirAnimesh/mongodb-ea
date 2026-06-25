# MongoDB on containers

This `container` demo natively delivers:

- a 3-node replica set
- MongoDB agent on each node
- management using [Ops Manager](https://www.mongodb.com/docs/ops-manager/current/?msockid=24798157dea1691f00429729dffd68d2)

```shell

```

## Pre-requisites

## Architecture

Standard container guidance is to have a single foreground process per container. In MongoDB images, that's `mongod`. But
Ops Manager relies on communicating with the Automation agent to orchestrate deployments and upgrades. So the Agent becomes
the foreground process in this project's containers, managing `mongod` as a child process.

> [!WARNING]
> This won't work on Linux kernel `v6.19+`.
> 
> Containers share your host's kernel. Fedora 44 host runs Linux kernel `7.0.12`. The `mongodb-enterprise-server:latest`
> image runs MongoDB 8.0, which has a deeply embedded Python `entrypoint` script that actively checks host's kernel 
> version. If it sees a kernel > `6.19`, it hard-crashes the container to protect from a known memory allocator bug in 
> `tcmalloc`.

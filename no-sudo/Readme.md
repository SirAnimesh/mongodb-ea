# MongoDB Cluster without sudo

This directory has scripts to install and setup MongoDB cluster in a non-privileged user, on an air-gapped machine.

Three moving parts:
1. MongoDB database for Ops Manager application, [`mongodb.sh`](mongodb.sh)
2. Ops Manager application, [`ops-manager.sh`](ops-manager.sh)
3. Automation agent, [`automation-agent.sh`](automation-agent.sh)

You'll need at least two machines for setting this up. `1` and `2` are installed on the host designated to run Ops Manager.
`3` is installed on each data-bearing node in the cluster. Automation agent then uses the Ops Manager host to orchestrate
the deployment of the rest of the cluster.

Because we have no internet, Ops Manager needs these two extra resources to run in **Local Mode**:
- Versions manifest tells Ops Manager which versions of MongoDB currently exist.
- The actual compiled binaries that Ops Manager will push to cluster nodes. Just re-use the MongoDB tarball you downloaded
  above.

## Workflow

1. Download all tarball archives from MongoDB Download Center. Keep them in `~/Downloads`. Below are links for RHEL 9 x64:
   - [MongoDB Enterprise 8.3.4](https://downloads.mongodb.com/linux/mongodb-linux-x86_64-enterprise-rhel93-8.3.4.tgz)
   - [Ops Manager 8.0.25](https://downloads.mongodb.com/on-prem-mms/tar/mongodb-mms-8.0.25.500.20260703T0841Z.tar.gz)
   - [MongoDB Shell 2.9.2](https://downloads.mongodb.com/compass/mongosh-2.9.2-linux-x64.tgz)
   - [Versions](https://opsmanager.mongodb.com/static/version_manifest/8.0.json) manifest
   - [Database Tools](https://fastdl.mongodb.org/tools/db/mongodb-database-tools-rhel93-x86_64-100.17.0.tgz)

2. Install backing MongoDB database for Ops Manager application:
   ```shell
   ./mongodb.sh
   ```

3. Install Ops Manager:
   ```shell
   ./ops-manager.sh
   ```

4. To enable **Local Mode**, copy the MongoDB database, and Database Tools tarball archive in `${HOME}/mongodb-binaries`.
   Ops Manager picks them up automatically via the `automation.versions.directory` setting in `conf-mms.properties`.

5. (on each data-bearing node) Download the Automation Agent tarball from Ops Manager host and install:
   ```shell
   cd $HOME/Downloads
   curl -OL http://<your-ops-manager-ip>:8085/download/agent/automation/mongodb-mms-automation-agent-latest.rhel8_x86_64.tar.gz
   ./automation-agent.sh
   ```

The `cron` daemon has a directive called `@reboot` which runs a command exactly once when the host starts up. The command
runs under the non-privileged user account.

```shell
crontab -e

@reboot /home/<username>/mongodb-ea/no-sudo/start-ops-manager.sh >> /home/<username>/startup.log 2>&1
@reboot /home/<username>/mongodb-ea/no-sudo/start-automation-agent.sh >> /home/<username>/agent-startup.log 2>&1
```

## Implications

We have no internet and no `sudo`. This means:

- No package manager installs. Tarballs (`.tgz`) archives all the way. If target machine is missing shared libraries, I
  am sorry for the pain you're about to experience.
- No system services (`systemd`, `upstart`, etc) for MongoDB processes. To run in the background and survive reboots, we
  will use `nohup`.
- Standard locations like `/opt/mongodb/mms` are out of bounds. Out of the box configuration will need to be tweaked.
- No binding to privileged ports (< 1024). Not a problem for MongoDB (`27017`) nor Ops Manager (`8080`) but something to
  keep in mind.

> [!WARNING]
> MongoDB and Ops Manager require very high open file descriptor limits (typically 64,000+). Without `sudo`, you
> cannot edit `/etc/security/limits.conf` to raise these. If your user account does not have elevated limits, the application
> database will aggressively throttle or crash under load. Check `ulimit -Hn` to see your hard limit. If this is below
> 64000, we're toast. If not, check the soft (and active) limit `ulimit -Sn`. If this is below 64000, run `ulimit -n 64000`.
> Raising soft limit does not need `sudo`.

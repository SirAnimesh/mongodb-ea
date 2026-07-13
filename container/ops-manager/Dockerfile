FROM docker.io/rockylinux:9

RUN dnf install -y initscripts && dnf clean all
ARG OM_VERSION="8.0.25.500.20260703T0841Z"
ARG OM_RPM="mongodb-mms-${OM_VERSION}.x86_64.rpm"
RUN curl -LO "https://downloads.mongodb.com/on-prem-mms/rpm/${OM_RPM}" && \
  dnf install -y "./${OM_RPM}" && \
  rm -f "${OM_RPM}"

# Re-route the backing database connection string to separate DB container named
# "ops-manager-db" in compose file, and skip the first-user setup wizard
RUN sed -i 's|mongo.mongoUri=mongodb://127.0.0.1:27017|mongo.mongoUri=mongodb://ops-manager-db:27017|' /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.ignoreInitialUiSetup=true' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.centralUrl=http://ops-manager:8080' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.fromEmailAddr=noreply@example.com' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.replyToEmailAddr=noreply@example.com' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.adminEmailAddr=admin@example.com' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.mail.transport=smtp' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.mail.hostname=localhost' >> /opt/mongodb/mms/conf/conf-mms.properties && \
  echo 'mms.mail.port=25' >> /opt/mongodb/mms/conf/conf-mms.properties

# Reduce the Java heap to 1.5GB
RUN sed -i 's/MMS_HEAP_SIZE=${MMS_HEAP_SIZE:-8096}/MMS_HEAP_SIZE=${MMS_HEAP_SIZE:-1500}/' /opt/mongodb/mms/conf/mms.conf

EXPOSE 8080

# The init script backgrounds the process, so we must tail the log to keep the container alive
ENTRYPOINT ["/bin/bash", "-c", "/opt/mongodb/mms/bin/mongodb-mms start && touch /opt/mongodb/mms/logs/mms0.log && tail -f /opt/mongodb/mms/logs/mms0.log"]
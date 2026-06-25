FROM docker.io/mongodb/mongodb-enterprise-server:latest

USER root

RUN apt-get update && apt-get install -y curl && \
  curl -OL https://cloud.mongodb.com/download/agent/automation/mongodb-mms-automation-agent-manager_13.53.0.10826-1_amd64.ubuntu2004.deb && \
  dpkg -i mongodb-mms-automation-agent-manager_13.53.0.10826-1_amd64.ubuntu2004.deb && \
  rm mongodb-mms-automation-agent-manager*.deb && \
  # The agent manages /data/db, so we must ensure the mongodb user owns all relevant directories
  chown -R mongodb:mongodb /var/lib/mongodb-mms-automation /var/log/mongodb-mms-automation /etc/mongodb-mms

USER mongodb

# Dynamically build the config file from environment variables at boot, then start the agent
ENTRYPOINT ["/bin/bash", "-c", "echo -e \"mmsGroupId=$MMS_GROUP_ID\\nmmsApiKey=$MMS_API_KEY\\nmmsBaseUrl=http://ops-manager:8080\" > /etc/mongodb-mms/automation-agent.config && exec /opt/mongodb-mms-automation/bin/mongodb-mms-automation-agent -config /etc/mongodb-mms/automation-agent.config"]
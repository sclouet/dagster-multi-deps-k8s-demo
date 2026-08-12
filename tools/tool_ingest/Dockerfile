# Stack legacy : pandas==1.5.3 ne supporte pas les Python recents.
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml ./
COPY tool_ingest ./tool_ingest

RUN pip install --no-cache-dir .

EXPOSE 4000

# dagster api grpc demarre le serveur que le webserver/daemon central
# (orchestrator/) vient interroger via workspace.yaml.
CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", \
     "-m", "tool_ingest.definitions"]

# Stack moderne : pandas==2.2.2 + pydantic v2.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY tool_enrich ./tool_enrich

RUN pip install --no-cache-dir .

EXPOSE 4000

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", \
     "-m", "tool_enrich.definitions"]

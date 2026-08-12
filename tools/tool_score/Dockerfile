# Stack ML legacy : numpy==1.23.5 fige par scikit-learn==1.0.2.
FROM python:3.9-slim

WORKDIR /app

COPY pyproject.toml ./
COPY tool_score ./tool_score

RUN pip install --no-cache-dir .

EXPOSE 4000

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", \
     "-m", "tool_score.definitions"]

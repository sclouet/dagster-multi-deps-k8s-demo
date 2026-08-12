# Whisper : outil autonome (aucune dependance tierce), pas encore branche
# sur le pipeline Dagster - image separee pour rester coherent avec les
# autres outils (chacun son environnement isole).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY whisper ./whisper

RUN pip install --no-cache-dir .

CMD ["python", "-m", "whisper"]

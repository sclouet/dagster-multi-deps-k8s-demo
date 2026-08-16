# Application partenaire : environnement isole (numpy), separe de Whisper
# (stdlib-only). Demontre l'echange de donnees entre deux environnements
# Python distincts, uniquement via un dossier partage (/exchange) - jamais
# de memoire/process partage.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY partner_app ./partner_app

RUN pip install --no-cache-dir .

CMD ["python", "-m", "partner_app"]

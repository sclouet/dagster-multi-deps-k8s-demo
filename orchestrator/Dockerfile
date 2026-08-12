# Image legere de l'orchestrateur central : ne contient AUCUNE des
# dependances "outil" (pandas, sklearn...). Elle parle aux 3 code locations
# uniquement via gRPC (voir workspace.yaml) - c'est ce qui permet a chaque
# outil de garder des dependances incompatibles entre elles.
FROM python:3.12-slim

WORKDIR /app

# Contexte de build = racine du projet (voir docker-compose.yaml) car ce
# Dockerfile a besoin de workspace.yaml/dagster.yaml situes a la racine.
COPY orchestrator/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY workspace.yaml dagster.yaml ./

# DAGSTER_HOME est un repertoire SEPARE de /app (monte en volume partage,
# voir docker-compose.yaml) : c'est le stockage d'instance (runs, event log)
# que webserver, daemon ET les 3 serveurs gRPC des outils doivent voir en
# commun pour que le DefaultRunLauncher puisse executer un run.
ENV DAGSTER_HOME=/dagster_home

EXPOSE 3000

# Commande par defaut = webserver. docker-compose.yaml surcharge cette
# commande pour le service dagster-daemon (necessaire aux asset sensors) et
# ajoute une etape d'initialisation qui copie dagster.yaml dans le volume
# partage au premier demarrage.
CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/app/workspace.yaml"]

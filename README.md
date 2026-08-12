# Démo : Dagster orchestrant des outils Python à dépendances incompatibles, déployée sur Kubernetes

## Le problème illustré

On a une chaîne de 3 "outils" Python (`ingest → enrich → score`) qui devraient logiquement s'enchaîner, mais dont les dépendances **ne peuvent pas cohabiter dans un seul environnement** :

| Outil | Dépendances clés | Python |
|---|---|---|
| `tool_ingest` | `pandas==1.5.3`, `numpy<2` | 3.10 |
| `tool_enrich` | `pandas==2.2.2`, `numpy>=1.26,<2`, `pydantic>=2` | 3.12 |
| `tool_score` | `numpy==1.23.5`, `scikit-learn==1.0.2` | 3.9 |

`tool_enrich` pin explicitement `numpy>=1.26,<2` (compatible avec pandas 2.2.2), alors que `scikit-learn==1.0.2` casse dès `numpy>=1.24` (suppression des alias `np.float`/`np.int`), d'où le pin `numpy==1.23.5` de `tool_score`. Ces deux plages ne se recoupent pas : impossible d'installer les deux stacks ensemble — vérifiable avec :

```powershell
scripts/check-incompatibility.ps1
```

## L'idée : une code location Dagster par outil

Dagster permet de garder plusieurs **code locations** dans un seul déploiement : chacune tourne dans son propre process/conteneur, avec son propre environnement Python, et communique avec le webserver/daemon central via **gRPC**. Le webserver n'a besoin d'aucune des dépendances des outils — il construit un graphe d'assets unifié à partir de ce que chaque code location expose.

```
                 ┌─────────────────────────┐
                 │   dagster-webserver      │
                 │   dagster-daemon         │   (aucune dépendance "outil")
                 └───────────┬─────────────┘
                     gRPC (workspace.yaml)
        ┌────────────────────┼────────────────────┐
        │                    │                    │
 ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
 │ tool_ingest │      │ tool_enrich │      │ tool_score  │
 │ pandas 1.5.3│      │ pandas 2.2.2│      │ numpy 1.23.5│
 │ python 3.10 │      │ pydantic v2 │      │ sklearn 1.0.2│
 │             │      │ python 3.12 │      │ python 3.9  │
 └──────┬──────┘      └──────┬──────┘      └──────┬──────┘
        │  raw_orders        │  enriched_orders    │
        └────────────►  MinIO (S3)  ◄───────────────┘
                    (stockage partagé)
```

**Un job Dagster ne peut pas s'exécuter à travers plusieurs code locations** (chaque job tourne dans un seul environnement). Le chaînage se fait donc en trois temps :

1. Chaque asset aval déclare l'asset amont comme **`SourceAsset` local** (même `AssetKey`, même `io_manager_key`) — c'est ce qui indique à Dagster de charger sa valeur via l'IO manager plutôt que d'exiger qu'il soit produit localement.
2. `AssetIn(key=AssetKey(...))` charge automatiquement cette valeur en argument de la fonction asset.
3. Un **asset sensor** (`tool_enrich`/`tool_score`) surveille la matérialisation de l'asset amont et déclenche automatiquement son propre job dès qu'elle a lieu — c'est le pattern officiel pour chaîner des code locations.

Les données elles-mêmes transitent par **MinIO** (S3-compatible), via `S3PickleIOManager` de `dagster-aws`, configuré à l'identique dans les 3 outils (mêmes variables d'environnement). C'est ce qui évite d'avoir à partager un filesystem entre pods (`ReadWriteMany`), problématique hors cluster mono-nœud.

## Structure du projet

```
tools/tool_ingest/   tools/tool_enrich/   tools/tool_score/
    Dockerfile, pyproject.toml, <package>/{__init__,logic,definitions}.py
orchestrator/         # image webserver+daemon (aucune dépendance "outil")
workspace.yaml         # docker-compose : pointe vers les 3 serveurs gRPC
dagster.yaml            # instance docker-compose (sqlite, run launcher par défaut)
docker-compose.yaml
k8s/
  helm-values.yaml            # chart officiel dagster/dagster : 1 déploiement par outil
  dagster-instance-values.yaml # réglages cluster local (imagePullPolicy, K8sRunLauncher)
  minio.yaml                   # MinIO en Deployment+PVC+Service+Job (création du bucket)
scripts/
  check-incompatibility.ps1
  build-images.ps1
  deploy-k8s.ps1
```

## Paliers de vérification

### Palier 1 — code (fait)

Syntaxe validée avec `python -m py_compile` sur tous les modules et parsing YAML/TOML de toute la config.

### Palier 2 — docker-compose (fait, testé de bout en bout)

```powershell
docker compose build
docker compose up -d
```

Puis :
1. Ouvrir http://localhost:3000
2. Matérialiser l'asset `raw_orders` (code location `tool_ingest`)
3. Les sensors déclenchent automatiquement `enriched_orders` puis `scored_orders` (~30s, intervalle d'évaluation par défaut du `SensorDaemon`)
4. Vérifier les objets dans la console MinIO : http://localhost:9001 (`dagster` / `dagster123`)
5. Lancer `scripts/check-incompatibility.ps1` pour la preuve du conflit de dépendances

**Bugs trouvés et corrigés pendant ce test réel** (le code initial ne fonctionnait pas du premier coup) :
- `tool_ingest` n'avait pas de borne sur `numpy` : pip résolvait `numpy 2.x`, incompatible avec l'ABI compilée de `pandas==1.5.3`. Fix : pin `numpy<2`.
- Les `AssetIn` cross-code-location ne se résolvent pas avec une simple `AssetKey` : il faut déclarer un `SourceAsset` local portant la même clé pour que Dagster sache charger la valeur via l'IO manager (sinon `DagsterInvalidDefinitionError` au chargement du serveur gRPC).
- Le `DefaultRunLauncher` exécute chaque run **dans** le serveur gRPC de sa code location : ce serveur doit donc voir le même `DAGSTER_HOME` (stockage de runs/event log) que le webserver/daemon — pas seulement l'orchestrateur. Fix : volume `dagster_home` partagé et monté sur les 3 outils en plus du webserver/daemon.
- `tool_enrich` (numpy 2.5.2 par défaut) picklait des DataFrames illisibles par `tool_score` (numpy 1.23.5) à cause du nouveau layout interne `numpy._core` introduit par numpy 2.0. Fix : pin `numpy>=1.26,<2` dans `tool_enrich` — garde le conflit pip voulu avec `tool_score` tout en gardant les pickles compatibles entre environnements 1.x.

### Palier 3 — Kubernetes (dès que minikube/kind + kubectl + helm sont installés)

```powershell
scripts/build-images.ps1
# charger les images dans le cluster (minikube image load ... / kind load docker-image ...)
scripts/deploy-k8s.ps1
kubectl get pods -w
kubectl port-forward svc/demo-dagster-webserver 3000:80
```

Puis ouvrir http://localhost:3000 et rejouer le même scénario de matérialisation : chaque outil tourne maintenant dans son propre pod, avec sa propre image — confirmable avec `kubectl get pods` (3 pods `demo-dagster-user-deployments-tool-*` + webserver + daemon + postgres + minio).

**Note** : le schéma exact des clés du chart Helm `dagster/dagster` évolue entre versions. Avant l'installation réelle, comparer `k8s/helm-values.yaml` / `k8s/dagster-instance-values.yaml` avec `helm show values dagster/dagster`.

## Prérequis à installer (côté utilisateur)

- Docker Desktop (avec WSL2 sur Windows)
- kubectl
- Un cluster local : minikube ou kind
- Helm

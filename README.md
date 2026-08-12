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

## Whisper : 4e outil, autonome (pas de code location Dagster)

`tools/whisper/` est un outil de calcul de trim avion, indépendant du pipeline `ingest → enrich → score` ci-dessus (autre domaine, pas de code location/asset Dagster). Il illustre la même isolation par outil (son propre `Dockerfile`/`pyproject.toml`), mais sans dépendance tierce — stdlib uniquement. Dagster est utilisé ponctuellement dans `example_sweep_dagster.py` (voir plus bas) comme simple bibliothèque d'exécution parallèle, pas comme orchestrateur déployé.

Sa classe principale, `Whisper`, est un **singleton** (`Whisper()` renvoie toujours la même instance dans un process) qui expose une API de préparation de données puis de calcul :

```python
from whisper import Whisper, TrimCondition, TrimParam

w = Whisper()
w.set_dir("./out")                       # dossier de sortie des out_<id>.csv (créé si absent)
w.set_seek(42)                           # graine de reproductibilité (facultatif)
w.load_aircraft("aircraft.xml")          # définition avion (XML)
w.set_trim_condition(TrimCondition(altitude_m=3000, speed_mps=120, mass_kg=18000))
w.set_trim_param(TrimParam(max_iterations=50))

w.run_trim()                             # écrit out_1.csv dans ./out
w.run_trim()                             # écrit out_2.csv (id = index d'appel sur l'instance)
w.run_trim(save_data=False)              # calcule sans écrire de fichier
```

`run_trim` lève une `RuntimeError` explicite si `load_aircraft`/`set_trim_condition`/`set_trim_param` n'ont pas été appelés au préalable. Le solveur de trim lui-même (`Whisper._solve_trim`) est un **stub** (calcul pseudo-aléatoire mais reproductible via `set_seek`) — à remplacer par le vrai calcul.

Tester :
- `python -m whisper` (démo autonome, génère son propre avion XML temporaire)
- `python tools/whisper/examples/example_usage.py` (script d'exemple pas à pas : instancie `Whisper`, appelle `set_dir`, `set_seek`, `load_aircraft`, `set_trim_condition`, `set_trim_param`, `run_trim`, avec `tools/whisper/examples/aircraft_example.xml`)
- `python tools/whisper/examples/example_sweep.py` (même principe, mais boucle sur l'altitude, la vitesse et la masse au décollage — un `run_trim()` par combinaison, donc `out_1.csv` … `out_27.csv`)
- ou `docker build -t whisper tools/whisper && docker run --rm whisper`

Whisper est aussi un service `docker-compose.yaml` (`whisper`) : `docker compose run --rm whisper` le construit/lance à la demande, ou il tourne une fois puis s'arrête proprement (code 0) lors d'un `docker compose up` complet — sans wiring Dagster, donc sans impact sur le reste de la stack.

### example_sweep_dagster.py : le même balayage, en parallèle via Dagster

`pip install tools/whisper/.[dagster]` puis `python tools/whisper/examples/example_sweep_dagster.py` exécute le même balayage 3×3×3 que `example_sweep.py`, mais chaque combinaison devient un **op Dagster** et le job utilise l'**executor multiprocess** : les 27 calculs tournent en parallèle sur plusieurs process (confirmé par les PID distincts dans les logs Dagster), au lieu d'une boucle séquentielle.

Deux points liés au fait que `Whisper` est un singleton :
- L'executor multiprocess exige une `DagsterInstance` **non-éphémère** (les process enfants doivent partager le même stockage de run).
- Chaque op tourne dans son propre process, donc sa propre instance `Whisper` (compteur d'appel reparti à 1) : sans précaution, les 27 ops écriraient tous un `out_1.csv` dans le même dossier. Le script donne donc un sous-dossier de sortie distinct par combinaison (`out_dagster/run_trim_<i>/out_1.csv`), sans modifier l'API de `Whisper`.

**Quelle instance Dagster ?** Par défaut (exécution autonome sur le poste), le script utilise `DagsterInstance.local_temp()` — une instance jetable, invisible en dehors du process. Mais si la variable d'environnement `DAGSTER_HOME` est définie, il bascule sur `DagsterInstance.get()` et écrit dans **cette** instance : c'est ce que fait le service docker-compose `whisper-sweep-dagster` (build via `tools/whisper/Dockerfile.dagster`, `DAGSTER_HOME=/dagster_home` partagé avec le webserver/daemon), pour que le run apparaisse dans l'UI Dagster :

```powershell
docker compose run --rm whisper-sweep-dagster
```

Puis ouvrir http://localhost:3000/runs : le run `whisper_sweep_job` y apparaît (27 steps en succès), aux côtés de `raw_orders`/`enriched_orders_job`/`scored_orders_job`. `Dockerfile.dagster` fige `dagster==1.8.13` (au lieu de la plage `>=1.8,<2` du extra `pyproject.toml`) — cette version **doit** matcher exactement celle du webserver/daemon (`orchestrator/requirements.txt`), car ce conteneur écrit directement dans le même stockage de run partagé ; une version différente risquerait une incompatibilité de schéma.

### Deux containers Whisper qui échangent des données

`example_producer.py` / `example_consumer.py` montrent deux instances `Whisper` **distinctes** (chacune dans son propre container **temporaire**, donc son propre process — pas de mémoire partagée) qui échangent des données via un **volume Docker partagé** (`whisper_shared`, monté sur `/shared` dans les deux) :

```powershell
docker compose run --rm whisper-producer   # calcule un trim, ecrit /shared/producer/out_1.csv
docker compose run --rm whisper-consumer   # lit ce CSV, l'utilise pour SON propre run_trim
```

Le consommateur ne recopie pas juste le résultat : il relit `altitude_m`/`speed_mps`/`mass_kg` du CSV du producteur et relance son propre calcul (masse +500 kg), avec sa propre instance `Whisper` (`set_seek(43)`, différent du producteur), et écrit dans son propre sous-dossier (`/shared/consumer/`) pour ne pas écraser le fichier du producteur.

`docker-compose.yaml` déclare `whisper-consumer` dépendant de `whisper-producer` (`condition: service_completed_successfully`) : lancer `docker compose run --rm whisper-consumer` seul, même sur un volume vide, déclenche automatiquement le producteur avant de lire son fichier — testé réellement. Le consommateur attend aussi activement (`time.sleep`, 30s max) le fichier du producteur, au cas où le script serait exécuté hors de cet ordonnancement docker-compose.

## Structure du projet

```
tools/tool_ingest/   tools/tool_enrich/   tools/tool_score/
    Dockerfile, pyproject.toml, <package>/{__init__,logic,definitions}.py
tools/whisper/         # outil autonome (voir section Whisper ci-dessus)
    Dockerfile, Dockerfile.dagster, pyproject.toml
    whisper/{__init__,core,trim,__main__}.py
    examples/{aircraft_example.xml, example_usage.py, example_sweep.py,
              example_sweep_dagster.py, example_producer.py, example_consumer.py}
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

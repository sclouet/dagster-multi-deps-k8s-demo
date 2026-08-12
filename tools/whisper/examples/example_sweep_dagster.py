"""Meme balayage que example_sweep.py (altitude x vitesse x masse), mais
chaque run_trim() est lance EN PARALLELE via un job Dagster (executor
multiprocess) au lieu d'une simple boucle sequentielle.

Pourquoi un sous-dossier de sortie par combinaison : Whisper est un
singleton, et l'executor multiprocess de Dagster lance chaque op dans son
propre process. Chaque process a donc SA PROPRE instance Whisper (compteur
d'appel reparti a 1) : sans separation, tous les ops ecriraient un
out_1.csv dans le meme dossier et s'ecraseraient les uns les autres. Chaque
combinaison ecrit donc dans out_dagster/run_trim_<i>/out_1.csv.

A executer depuis n'importe ou : `python example_sweep_dagster.py`.
Necessite le package `dagster` (extra facultatif, voir pyproject.toml) :
    pip install dagster

Instance Dagster utilisee :
- Si DAGSTER_HOME est definie dans l'environnement (ex : service
  docker-compose whisper-sweep-dagster, meme volume que le
  webserver/daemon), les runs sont ecrits dans cette instance partagee et
  apparaissent dans l'UI Dagster (http://localhost:3000/runs).
- Sinon (execution autonome sur le poste), une instance jetable dans un
  dossier temporaire est utilisee (comportement d'origine).
"""

import itertools
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dagster import (
    DagsterInstance,
    execute_job,
    job,
    multiprocess_executor,
    op,
    reconstructable,
)

from whisper import TrimCondition, TrimParam, Whisper

EXAMPLES_DIR = Path(__file__).resolve().parent
AIRCRAFT_XML = str(EXAMPLES_DIR / "aircraft_example.xml")
OUT_DIR = EXAMPLES_DIR / "out_dagster"

ALTITUDES_M = [0, 1500, 3000]
SPEEDS_MPS = [80, 100, 120]
MASSES_KG = [15000, 18000, 21000]


def _make_run_trim_op(name: str, altitude_m: float, speed_mps: float, mass_kg: float):
    @op(name=name)
    def _run_trim_op():
        whisper = Whisper()
        whisper.set_dir(str(OUT_DIR / name))
        whisper.set_seek(42)
        whisper.load_aircraft(AIRCRAFT_XML)
        whisper.set_trim_condition(
            TrimCondition(altitude_m=altitude_m, speed_mps=speed_mps, mass_kg=mass_kg)
        )
        whisper.set_trim_param(TrimParam(max_iterations=50))
        return whisper.run_trim()

    return _run_trim_op


_COMBINATIONS = list(itertools.product(ALTITUDES_M, SPEEDS_MPS, MASSES_KG))
_RUN_TRIM_OPS = [
    _make_run_trim_op(f"run_trim_{i}", altitude_m, speed_mps, mass_kg)
    for i, (altitude_m, speed_mps, mass_kg) in enumerate(_COMBINATIONS, start=1)
]


@job(executor_def=multiprocess_executor)
def whisper_sweep_job():
    # Aucune dependance entre les ops : l'executor multiprocess de Dagster
    # les repartit sur plusieurs process en parallele (par defaut, autant
    # que de coeurs disponibles).
    for run_trim_op in _RUN_TRIM_OPS:
        run_trim_op()


def _dagster_instance():
    # L'executor multiprocess exige une instance non-ephemere (les process
    # enfants doivent partager le meme stockage de run).
    if os.environ.get("DAGSTER_HOME"):
        # Instance partagee avec le webserver/daemon (DAGSTER_HOME) : les
        # runs de ce script apparaissent dans l'UI Dagster.
        return DagsterInstance.get()
    # Execution autonome : instance sur disque, dans un dossier temporaire
    # auto-nettoye, invisible en dehors de ce process.
    return DagsterInstance.local_temp()


def main() -> None:
    with _dagster_instance() as instance:
        result = execute_job(reconstructable(whisper_sweep_job), instance=instance)

    print(f"Succes : {result.success}")
    print(f"{len(_COMBINATIONS)} calculs de trim lances en parallele (executor multiprocess).")
    print(f"Resultats dans {OUT_DIR}/run_trim_<i>/out_1.csv")
    if os.environ.get("DAGSTER_HOME"):
        print("Visible dans l'UI Dagster : http://localhost:3000/runs")


if __name__ == "__main__":
    main()

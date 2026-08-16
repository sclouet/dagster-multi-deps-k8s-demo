"""Definitions Dagster pour le scenario d'echange Whisper <-> partner_app,
version "in-memory" (pas de fichiers).

Contrairement a examples/example_exchange.py (echange par CSV, dossier
partage), les tables transitent ici par le S3PickleIOManager deja utilise
par le pipeline principal (tool_ingest/enrich/score) : aucun fichier local
n'est ecrit pour l'echange lui-meme, Dagster (charge|decharge) les valeurs
Python automatiquement via AssetIn, en s'appuyant sur MinIO comme backend.

Deux code locations separees et persistantes restent necessaires : Whisper
(stdlib-only) et partner_app (numpy, voir tools/partner_app/) sont deux
environnements Python isoles, et un job Dagster ne peut pas traverser
plusieurs code locations. Le chainage se fait donc, comme pour
raw_orders -> enriched_orders, par SourceAsset + AssetIn + asset sensor -
mais ici dans LES DEUX SENS (aller ET retour) :
  1. trim_table (ici)              -> declenche partner_response_job (partner_app)
  2. partner_original/partner_random (partner_app) -> declenche verify_response_job (ici)

Le suivi de l'echange se fait via context.log dans chaque asset, visible
directement dans l'UI Dagster (http://localhost:3000/runs) - c'est
Dagster qui fournit cette observabilite, pas un fichier de log dedie.
"""

import random
from pathlib import Path

from dagster import (
    AssetIn,
    AssetKey,
    DefaultSensorStatus,
    Definitions,
    EnvVar,
    RunRequest,
    SourceAsset,
    asset,
    asset_sensor,
    define_asset_job,
)
from dagster_aws.s3 import S3PickleIOManager, S3Resource

from .core import Whisper
from .trim import TrimCondition, TrimParam

AIRCRAFT_XML = Path("examples/aircraft_example.xml")
N_VALUES = 500


@asset(
    description=(
        "Table de 500 floats aleatoires issue d'un trim Whisper - "
        "transmise via l'IO manager S3, jamais ecrite sur disque localement."
    ),
)
def trim_table(context):
    whisper = Whisper()
    whisper.set_seek(random.randint(0, 1_000_000))
    whisper.load_aircraft(str(AIRCRAFT_XML))
    whisper.set_trim_condition(
        TrimCondition(
            altitude_m=random.uniform(0, 5000),
            speed_mps=random.uniform(80, 140),
            mass_kg=random.uniform(15000, 20000),
        )
    )
    whisper.set_trim_param(TrimParam(max_iterations=50))
    result = whisper.run_trim(save_data=False)
    context.log.info(
        "Trim calcule : alpha=%.4f deg, converged=%s", result["alpha_deg"], result["converged"]
    )

    table = [random.uniform(0.0, 1.0) for _ in range(N_VALUES)]
    context.log.info("Table de %d floats generee, transmise via l'IO manager S3.", len(table))
    return table


trim_table_job = define_asset_job(name="trim_table_job", selection=[trim_table])

partner_original_source = SourceAsset(key=AssetKey("partner_original"), io_manager_key="io_manager")
partner_random_source = SourceAsset(key=AssetKey("partner_random"), io_manager_key="io_manager")


@asset(
    ins={
        "trim_table": AssetIn(key=AssetKey("trim_table")),
        "partner_original": AssetIn(key=AssetKey("partner_original")),
        "partner_random": AssetIn(key=AssetKey("partner_random")),
    },
    description="Verifie la reponse de partner_app : la table 'originale' doit correspondre exactement a l'envoi.",
)
def verify_response(context, trim_table, partner_original, partner_random):
    assert list(partner_original) == list(trim_table), (
        "la table 'originale' recue de partner_app ne correspond pas a l'envoi !"
    )
    assert len(partner_random) == len(trim_table), "la table random n'a pas la meme taille"
    context.log.info(
        "Reponse verifiee : table originale conforme (%d valeurs), table random distincte (%d valeurs).",
        len(partner_original), len(partner_random),
    )
    return {"match": True, "n_values": len(trim_table)}


verify_response_job = define_asset_job(name="verify_response_job", selection=[verify_response])


@asset_sensor(
    asset_key=AssetKey("partner_random"),
    job=verify_response_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=5,
    description=(
        "Declenche verify_response_job des que partner_app a renvoye sa table "
        "random (et donc, produites dans le meme run, l'originale aussi)."
    ),
)
def partner_response_sensor(context, asset_event):
    yield RunRequest(run_key=context.cursor)


io_manager = S3PickleIOManager(
    s3_resource=S3Resource(
        endpoint_url=EnvVar("DAGSTER_S3_ENDPOINT"),
        aws_access_key_id=EnvVar("DAGSTER_S3_ACCESS_KEY"),
        aws_secret_access_key=EnvVar("DAGSTER_S3_SECRET_KEY"),
    ),
    s3_bucket=EnvVar("DAGSTER_S3_BUCKET"),
)

defs = Definitions(
    assets=[trim_table, verify_response, partner_original_source, partner_random_source],
    jobs=[trim_table_job, verify_response_job],
    sensors=[partner_response_sensor],
    resources={"io_manager": io_manager},
)

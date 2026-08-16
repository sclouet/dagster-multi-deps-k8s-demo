"""Definitions Dagster pour partner_app (cote reception du scenario
d'echange Whisper <-> partner_app, version in-memory - voir
whisper/dagster_defs.py pour le contexte complet).

Environnement isole : numpy est installe ici, absent de Whisper
(stdlib-only). Chainage par SourceAsset + AssetIn + asset sensor (meme
pattern que tool_ingest -> tool_enrich) : ce code location ne peut pas
partager de process/job avec whisper_exchange, seulement des donnees via
le S3PickleIOManager partage (MinIO) - jamais de fichier local.
"""

import numpy as np
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

trim_table_source = SourceAsset(key=AssetKey("trim_table"), io_manager_key="io_manager")


@asset(
    ins={"trim_table": AssetIn(key=AssetKey("trim_table"))},
    description="Copie conforme de la table recue de Whisper.",
)
def partner_original(context, trim_table):
    context.log.info("Table recue de Whisper (%d valeurs), renvoi conforme.", len(trim_table))
    return list(trim_table)


@asset(
    ins={"trim_table": AssetIn(key=AssetKey("trim_table"))},
    description="Table equivalente a valeurs aleatoires NOUVELLES (numpy), meme taille que la table recue.",
)
def partner_random(context, trim_table):
    values = np.random.uniform(0.0, 1.0, size=len(trim_table)).tolist()
    context.log.info("Table random generee avec numpy (%d valeurs).", len(values))
    return values


partner_response_job = define_asset_job(
    name="partner_response_job", selection=[partner_original, partner_random]
)


@asset_sensor(
    asset_key=AssetKey("trim_table"),
    job=partner_response_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=5,
    description="Declenche partner_response_job des que Whisper materialise une nouvelle trim_table.",
)
def trim_table_materialized_sensor(context, asset_event):
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
    assets=[partner_original, partner_random, trim_table_source],
    jobs=[partner_response_job],
    sensors=[trim_table_materialized_sensor],
    resources={"io_manager": io_manager},
)

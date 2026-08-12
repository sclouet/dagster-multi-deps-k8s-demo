"""Code location Dagster pour tool_enrich.

Un job Dagster ne peut pas s'executer a travers plusieurs code locations
(chaque job tourne dans un seul environnement Python). Le chainage avec
tool_ingest se fait donc en trois temps :
  1. "raw_orders" est declare comme SourceAsset local (memes AssetKey et
     io_manager que tool_ingest) : Dagster sait alors qu'il doit charger sa
     valeur via l'IO manager plutot que de le materialiser lui-meme ;
  2. AssetIn charge automatiquement cette valeur en argument de fonction ;
  3. un asset sensor surveille la materialisation de "raw_orders" (produit
     par l'autre code location) et declenche automatiquement le job local
     des que l'amont est pret.
"""

import pandas as pd
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

from .logic import enrich_orders

raw_orders_source = SourceAsset(key=AssetKey("raw_orders"), io_manager_key="io_manager")


@asset(
    ins={"raw_orders": AssetIn(key=AssetKey("raw_orders"))},
    description=(
        "Commandes enrichies et converties en EUR "
        "(stack moderne: pandas==2.2.2, pydantic>=2, python 3.12)."
    ),
)
def enriched_orders(raw_orders: pd.DataFrame) -> pd.DataFrame:
    return enrich_orders(raw_orders)


enriched_orders_job = define_asset_job(
    name="enriched_orders_job", selection=[enriched_orders]
)


@asset_sensor(
    asset_key=AssetKey("raw_orders"),
    job=enriched_orders_job,
    default_status=DefaultSensorStatus.RUNNING,
    description="Declenche enriched_orders_job des que raw_orders (tool_ingest) est materialise.",
)
def raw_orders_materialized_sensor(context, asset_event):
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
    assets=[enriched_orders, raw_orders_source],
    jobs=[enriched_orders_job],
    sensors=[raw_orders_materialized_sensor],
    resources={"io_manager": io_manager},
)

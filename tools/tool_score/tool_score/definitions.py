"""Code location Dagster pour tool_score.

Meme pattern que tool_enrich : "enriched_orders" declare comme SourceAsset
local (charge via l'IO manager partage) + AssetIn pour la valeur, plus un
asset sensor qui declenche automatiquement ce job des que tool_enrich
materialise sa sortie.
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

from .logic import score_orders

enriched_orders_source = SourceAsset(
    key=AssetKey("enriched_orders"), io_manager_key="io_manager"
)


@asset(
    ins={"enriched_orders": AssetIn(key=AssetKey("enriched_orders"))},
    description=(
        "Commandes scorees "
        "(stack ML legacy: numpy==1.23.5, scikit-learn==1.0.2, python 3.9)."
    ),
)
def scored_orders(enriched_orders: pd.DataFrame) -> pd.DataFrame:
    return score_orders(enriched_orders)


scored_orders_job = define_asset_job(name="scored_orders_job", selection=[scored_orders])


@asset_sensor(
    asset_key=AssetKey("enriched_orders"),
    job=scored_orders_job,
    default_status=DefaultSensorStatus.RUNNING,
    description="Declenche scored_orders_job des que enriched_orders (tool_enrich) est materialise.",
)
def enriched_orders_materialized_sensor(context, asset_event):
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
    assets=[scored_orders, enriched_orders_source],
    jobs=[scored_orders_job],
    sensors=[enriched_orders_materialized_sensor],
    resources={"io_manager": io_manager},
)

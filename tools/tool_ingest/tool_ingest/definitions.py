"""Code location Dagster pour tool_ingest.

Chaque outil de cette demo expose sa propre `Definitions` et tourne dans son
propre serveur gRPC (sa propre image Docker / son propre environnement
Python). Le stockage partage (MinIO, compatible S3) permet aux autres code
locations de lire les assets produits ici sans jamais partager
d'environnement Python.
"""

from dagster import Definitions, EnvVar, asset, define_asset_job
from dagster_aws.s3 import S3PickleIOManager, S3Resource

from .logic import build_raw_orders


@asset(
    description=(
        "Commandes brutes ingerees (stack legacy: pandas==1.5.3, python 3.10)."
    ),
)
def raw_orders():
    return build_raw_orders()


raw_orders_job = define_asset_job(name="raw_orders_job", selection=[raw_orders])

io_manager = S3PickleIOManager(
    s3_resource=S3Resource(
        endpoint_url=EnvVar("DAGSTER_S3_ENDPOINT"),
        aws_access_key_id=EnvVar("DAGSTER_S3_ACCESS_KEY"),
        aws_secret_access_key=EnvVar("DAGSTER_S3_SECRET_KEY"),
    ),
    s3_bucket=EnvVar("DAGSTER_S3_BUCKET"),
)

defs = Definitions(
    assets=[raw_orders],
    jobs=[raw_orders_job],
    resources={"io_manager": io_manager},
)

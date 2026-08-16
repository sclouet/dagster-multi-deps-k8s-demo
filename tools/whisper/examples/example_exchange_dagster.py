"""Meme scenario que example_exchange.py (10 echanges Whisper <->
partner_app), mais orchestre par Dagster et SANS fichiers : les tables
transitent par le S3PickleIOManager (MinIO), voir whisper/dagster_defs.py
et tools/partner_app/partner_app/dagster_defs.py.

Ce script ne fait QUE declencher 10 materialisations de trim_table (via le
client GraphQL, comme un clic "Materialize" dans l'UI) sur le code
location whisper_exchange deja deploye (serveur gRPC persistant
whisper-exchange-server) - le reste de la sequence (partner_app puis
verification) se deroule via les asset sensors, comme pour
raw_orders -> enriched_orders -> scored_orders.

Le suivi de l'echange se fait via les logs de run Dagster (context.log
dans chaque asset), visibles dans l'UI - pas de fichier de log dedie ici,
Dagster fournit deja cette observabilite.

A executer une fois la stack complete demarree (webserver, daemon,
whisper-exchange-server, partner-app-server) :
    docker compose run --rm whisper-exchange-dagster
"""

import time

from dagster import DagsterInstance, DagsterRunStatus, RunsFilter
from dagster_graphql import DagsterGraphQLClient

N_EXCHANGES = 10
POLL_INTERVAL_S = 2
SUBMIT_TIMEOUT_S = 60
ROUNDTRIP_TIMEOUT_S = 90

WEBSERVER_HOST = "dagster-webserver"
WEBSERVER_PORT = 3000
LOCATION_NAME = "whisper_exchange"
REPOSITORY_NAME = "__repository__"


def _wait_for_submitted_run(client: DagsterGraphQLClient, run_id: str, exchange_i: int) -> None:
    waited = 0
    while True:
        status = client.get_run_status(run_id)
        if status == DagsterRunStatus.SUCCESS:
            return
        if status in (DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED):
            raise RuntimeError(f"[{exchange_i}/{N_EXCHANGES}] trim_table_job (run {run_id}) : {status}")
        if waited >= SUBMIT_TIMEOUT_S:
            raise TimeoutError(
                f"[{exchange_i}/{N_EXCHANGES}] trim_table_job (run {run_id}) toujours {status} "
                f"apres {SUBMIT_TIMEOUT_S}s"
            )
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S


def _count_successful_runs(instance: DagsterInstance, job_name: str) -> int:
    records = instance.get_run_records(
        filters=RunsFilter(job_name=job_name, statuses=[DagsterRunStatus.SUCCESS])
    )
    return len(records)


def main() -> None:
    client = DagsterGraphQLClient(WEBSERVER_HOST, port_number=WEBSERVER_PORT)
    instance = DagsterInstance.get()

    for i in range(1, N_EXCHANGES + 1):
        verified_before = _count_successful_runs(instance, "verify_response_job")

        print(f"[driver] echange {i}/{N_EXCHANGES} : declenchement de trim_table_job...")
        run_id = client.submit_job_execution(
            "trim_table_job",
            repository_location_name=LOCATION_NAME,
            repository_name=REPOSITORY_NAME,
        )
        _wait_for_submitted_run(client, run_id, i)
        print(f"[driver] echange {i}/{N_EXCHANGES} : trim_table materialise (run {run_id}).")

        waited = 0
        while _count_successful_runs(instance, "verify_response_job") <= verified_before:
            if waited >= ROUNDTRIP_TIMEOUT_S:
                raise TimeoutError(
                    f"[{i}/{N_EXCHANGES}] verify_response_job pas termine apres "
                    f"{ROUNDTRIP_TIMEOUT_S}s - partner-app-server / sensors actifs ?"
                )
            time.sleep(POLL_INTERVAL_S)
            waited += POLL_INTERVAL_S
        print(f"[driver] echange {i}/{N_EXCHANGES} : aller-retour verifie avec succes.")

    print(f"\nTermine : {N_EXCHANGES} echanges Whisper <-> partner_app, orchestres par Dagster.")
    print("Detail dans l'UI : http://localhost:3000/runs")
    print("(jobs trim_table_job / partner_response_job / verify_response_job)")


if __name__ == "__main__":
    main()

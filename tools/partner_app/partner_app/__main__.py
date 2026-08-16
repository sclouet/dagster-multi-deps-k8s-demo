"""Application partenaire de demo.

Recoit, pour chaque echange, une table de floats envoyee par Whisper
(dossier partage /exchange/to_partner/exchange_<i>.csv) et renvoie DEUX
tables : une copie conforme de la table recue (exchange_<i>_original.csv)
et une table equivalente a valeurs aleatoires NOUVELLES, generees avec
numpy (exchange_<i>_random.csv).

Environnement isole : cette application utilise numpy, Whisper (l'autre
cote de l'echange) reste stdlib-only - deux environnements Python
distincts (containers separes), qui ne communiquent QUE via le systeme de
fichiers partage, jamais par memoire/process partage.

A executer via docker-compose, EN MEME TEMPS que whisper-exchange (echange
bidirectionnel repete, pas un simple enchainement sequentiel) :
    docker compose up --build whisper-exchange partner-app
"""

import csv
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np

EXCHANGE_DIR = Path("/exchange")
TO_PARTNER_DIR = EXCHANGE_DIR / "to_partner"
FROM_PARTNER_DIR = EXCHANGE_DIR / "from_partner"
LOG_DIR = Path("logs")

N_EXCHANGES = 10
WAIT_TIMEOUT_S = 60


def _make_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    log_path = LOG_DIR / f"exchange_partner_{timestamp}.log"

    logger = logging.getLogger("exchange.partner")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _write_table(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "value"])
        writer.writerows(enumerate(values))


def _read_table(path: Path) -> list:
    with path.open(encoding="utf-8") as f:
        return [float(row["value"]) for row in csv.DictReader(f)]


def _wait_for(path: Path, logger: logging.Logger) -> None:
    waited = 0
    while not path.exists():
        if waited >= WAIT_TIMEOUT_S:
            raise TimeoutError(
                f"{path} absent apres {WAIT_TIMEOUT_S}s - whisper-exchange tourne-t-il ?"
            )
        time.sleep(1)
        waited += 1
    logger.debug("Fichier detecte : %s", path)


def main() -> None:
    logger = _make_logger()
    logger.info("Debut : attente de %d echanges depuis Whisper", N_EXCHANGES)

    for i in range(1, N_EXCHANGES + 1):
        incoming_path = TO_PARTNER_DIR / f"exchange_{i}.csv"
        logger.debug("[%d/%d] Attente de %s...", i, N_EXCHANGES, incoming_path)
        _wait_for(incoming_path, logger)

        table = _read_table(incoming_path)
        logger.info("[%d/%d] Table recue (%d valeurs)", i, N_EXCHANGES, len(table))

        original_path = FROM_PARTNER_DIR / f"exchange_{i}_original.csv"
        _write_table(original_path, table)
        logger.info("[%d/%d] Table originale renvoyee -> %s", i, N_EXCHANGES, original_path)

        random_table = np.random.uniform(0.0, 1.0, size=len(table)).tolist()
        random_path = FROM_PARTNER_DIR / f"exchange_{i}_random.csv"
        _write_table(random_path, random_table)
        logger.info("[%d/%d] Table random (numpy) renvoyee -> %s", i, N_EXCHANGES, random_path)

        print(f"[partner_app] echange {i}/{N_EXCHANGES} traite")

    logger.info("Termine : %d/%d echanges traites", N_EXCHANGES, N_EXCHANGES)
    print(f"Termine : {N_EXCHANGES} echanges traites. Logs dans {LOG_DIR}")


if __name__ == "__main__":
    main()

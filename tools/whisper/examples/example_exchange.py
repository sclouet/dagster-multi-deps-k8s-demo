"""Echange de donnees BIDIRECTIONNEL et REPETE entre Whisper et une autre
application isolee (tools/partner_app/, environnement numpy separe -
Whisper reste stdlib-only), via un dossier partage (/exchange), sans
jamais partager de process/memoire.

Sequence, repetee N_EXCHANGES fois :
  1. Whisper calcule un trim (run_trim), genere une table de N_VALUES
     floats aleatoires, l'envoie a partner_app
     (exchange/to_partner/exchange_<i>.csv).
  2. partner_app renvoie DEUX tables : la table originale (copie conforme)
     et une table equivalente a valeurs aleatoires NOUVELLES
     (exchange/from_partner/exchange_<i>_original.csv et _random.csv).
  3. Whisper recoit les deux tables et verifie que la copie "originale"
     correspond bien a l'envoi.

Log dedie (logs/exchange_whisper_<timestamp>.log) pour suivre cette
sequence d'echanges - distinct du log d'instance Whisper (methodes
set_*/run_trim), qui continue par ailleurs de s'ecrire normalement.

A executer via docker-compose, EN MEME TEMPS que partner_app (echange
bidirectionnel a chaque etape, pas un simple enchainement sequentiel) :
    docker compose up --build whisper-exchange partner-app
"""

import csv
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisper import TrimCondition, TrimParam, Whisper

EXAMPLES_DIR = Path(__file__).resolve().parent
AIRCRAFT_XML = EXAMPLES_DIR / "aircraft_example.xml"
EXCHANGE_DIR = Path("/exchange")
TO_PARTNER_DIR = EXCHANGE_DIR / "to_partner"
FROM_PARTNER_DIR = EXCHANGE_DIR / "from_partner"
LOG_DIR = Path("logs")

N_EXCHANGES = 10
N_VALUES = 500
WAIT_TIMEOUT_S = 60


def _make_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    log_path = LOG_DIR / f"exchange_whisper_{timestamp}.log"

    logger = logging.getLogger("exchange.whisper")
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
                f"{path} absent apres {WAIT_TIMEOUT_S}s - partner_app tourne-t-il ?"
            )
        time.sleep(1)
        waited += 1
    logger.debug("Fichier detecte : %s", path)


def main() -> None:
    logger = _make_logger()
    logger.info(
        "Debut de la sequence d'echange : %d trims / %d valeurs par table",
        N_EXCHANGES, N_VALUES,
    )

    whisper = Whisper()
    whisper.set_dir(str(EXAMPLES_DIR / "out"))
    whisper.set_seek(7)
    whisper.load_aircraft(str(AIRCRAFT_XML))
    whisper.set_trim_param(TrimParam(max_iterations=50))

    for i in range(1, N_EXCHANGES + 1):
        whisper.set_trim_condition(
            TrimCondition(altitude_m=500 * i, speed_mps=100, mass_kg=17000)
        )
        result = whisper.run_trim()
        logger.info("[%d/%d] Trim calcule (alpha=%.4f deg)", i, N_EXCHANGES, result["alpha_deg"])

        table_sent = [random.uniform(0.0, 1.0) for _ in range(N_VALUES)]
        to_partner_path = TO_PARTNER_DIR / f"exchange_{i}.csv"
        _write_table(to_partner_path, table_sent)
        logger.info(
            "[%d/%d] Table de %d floats envoyee -> %s",
            i, N_EXCHANGES, N_VALUES, to_partner_path,
        )

        original_path = FROM_PARTNER_DIR / f"exchange_{i}_original.csv"
        random_path = FROM_PARTNER_DIR / f"exchange_{i}_random.csv"
        logger.debug("[%d/%d] Attente de la reponse de partner_app...", i, N_EXCHANGES)
        _wait_for(original_path, logger)
        _wait_for(random_path, logger)

        table_original = _read_table(original_path)
        table_random = _read_table(random_path)
        assert table_original == table_sent, (
            f"[{i}/{N_EXCHANGES}] la table 'originale' recue ne correspond pas a l'envoi !"
        )
        logger.info(
            "[%d/%d] Reponse recue : table originale conforme (%d valeurs), "
            "table random distincte (%d valeurs)",
            i, N_EXCHANGES, len(table_original), len(table_random),
        )
        print(f"[whisper] echange {i}/{N_EXCHANGES} termine")

    logger.info("Sequence d'echange terminee (%d/%d)", N_EXCHANGES, N_EXCHANGES)
    print(f"Termine : {N_EXCHANGES} echanges. Logs dans {LOG_DIR}, tables dans {EXCHANGE_DIR}")


if __name__ == "__main__":
    main()

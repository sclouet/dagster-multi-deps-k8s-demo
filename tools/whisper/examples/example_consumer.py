"""Container "consommateur" : lit le out_1.csv ecrit par example_producer.py
(volume Docker partage) et l'utilise comme base pour son PROPRE calcul de
trim, avec sa PROPRE instance Whisper (singleton par process - ce container
n'a jamais vu l'instance Whisper du producteur, seulement son fichier).

Attente/poll avant lecture : les deux containers etant temporaires et lances
independamment, rien ne garantit que le producteur ait deja ecrit son
fichier au demarrage du consommateur - docker-compose.yaml gere l'ordre via
`depends_on: condition: service_completed_successfully`, mais on attend
quand meme ici par securite (execution possible hors docker-compose).

A executer via docker-compose, apres (ou avec) le producteur :
    docker compose run --rm whisper-producer
    docker compose run --rm whisper-consumer
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisper import TrimCondition, TrimParam, Whisper

AIRCRAFT_XML = Path(__file__).resolve().parent / "aircraft_example.xml"
PRODUCER_CSV = Path("/shared/producer/out_1.csv")
CONSUMER_DIR = Path("/shared/consumer")
WAIT_TIMEOUT_S = 30

waited = 0
while not PRODUCER_CSV.exists():
    if waited >= WAIT_TIMEOUT_S:
        raise TimeoutError(
            f"{PRODUCER_CSV} introuvable apres {WAIT_TIMEOUT_S}s - "
            "le container whisper-producer a-t-il tourne avant celui-ci ?"
        )
    time.sleep(1)
    waited += 1

with PRODUCER_CSV.open(encoding="utf-8") as f:
    producer_row = next(csv.DictReader(f))

print(f"[consumer] donnees recues du producteur ({PRODUCER_CSV}) : {producer_row}")

whisper = Whisper()
whisper.set_dir(str(CONSUMER_DIR))
whisper.set_seek(43)  # graine differente : instance distincte, pas une copie
whisper.load_aircraft(str(AIRCRAFT_XML))
whisper.set_trim_condition(
    TrimCondition(
        altitude_m=float(producer_row["altitude_m"]),
        speed_mps=float(producer_row["speed_mps"]),
        # masse au decollage du producteur + 500 kg : montre une reutilisation
        # des donnees recues, pas une simple copie du calcul.
        mass_kg=float(producer_row["mass_kg"]) + 500,
    )
)
whisper.set_trim_param(TrimParam(max_iterations=50))

result = whisper.run_trim()

print(f"[consumer] nouveau calcul base sur le producteur, ecrit dans {result['output_path']}")
print(f"[consumer] {result}")

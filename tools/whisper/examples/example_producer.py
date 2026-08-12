"""Container "producteur" : calcule un trim et ecrit son resultat dans un
volume Docker partage, pour qu'un AUTRE container (example_consumer.py),
avec sa propre instance Whisper (singleton par process), puisse le lire.

Chemin /shared/producer : cf. docker-compose.yaml (service whisper-producer,
volume whisper_shared monte sur /shared dans les deux containers).

A executer via docker-compose (le chemin /shared n'existe que dans les
containers) :
    docker compose run --rm whisper-producer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisper import TrimCondition, TrimParam, Whisper

AIRCRAFT_XML = Path(__file__).resolve().parent / "aircraft_example.xml"
SHARED_DIR = Path("/shared/producer")

whisper = Whisper()
whisper.set_dir(str(SHARED_DIR))
whisper.set_seek(42)
whisper.load_aircraft(str(AIRCRAFT_XML))
whisper.set_trim_condition(TrimCondition(altitude_m=3000, speed_mps=120, mass_kg=18000))
whisper.set_trim_param(TrimParam(max_iterations=50))

result = whisper.run_trim()

print(f"[producer] calcul termine, ecrit dans {result['output_path']}")
print(f"[producer] {result}")

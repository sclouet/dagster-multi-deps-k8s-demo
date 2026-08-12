"""Exemple d'utilisation de Whisper.

A executer depuis n'importe ou : `python example_usage.py`
(aucune dependance tierce, le dossier whisper/ est ajoute automatiquement
au sys.path s'il n'est pas deja installe).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisper import TrimCondition, TrimParam, Whisper

EXAMPLES_DIR = Path(__file__).resolve().parent

whisper = Whisper()

whisper.set_dir(str(EXAMPLES_DIR / "out"))
whisper.set_seek(42)
whisper.load_aircraft(str(EXAMPLES_DIR / "aircraft_example.xml"))
whisper.set_trim_condition(TrimCondition(altitude_m=3000, speed_mps=120, mass_kg=18000))
whisper.set_trim_param(TrimParam(max_iterations=50))

result = whisper.run_trim()

print("Calcul de trim termine :")
print(result)

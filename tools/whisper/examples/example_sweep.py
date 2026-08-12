"""Exemple de balayage (sweep) avec Whisper.

Meme principe que example_usage.py, mais on boucle sur l'altitude, la
vitesse et la masse au decollage : chaque combinaison declenche un
run_trim(), qui ecrit son propre out_<id>.csv dans le dossier de sortie.

A executer depuis n'importe ou : `python example_sweep.py`
(aucune dependance tierce, le dossier whisper/ est ajoute automatiquement
au sys.path s'il n'est pas deja installe).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whisper import TrimCondition, TrimParam, Whisper

EXAMPLES_DIR = Path(__file__).resolve().parent

ALTITUDES_M = [0, 1500, 3000]
SPEEDS_MPS = [80, 100, 120]
MASSES_KG = [15000, 18000, 21000]

whisper = Whisper()

whisper.set_dir(str(EXAMPLES_DIR / "out"))
whisper.set_seek(42)
whisper.load_aircraft(str(EXAMPLES_DIR / "aircraft_example.xml"))
whisper.set_trim_param(TrimParam(max_iterations=50))

run_count = 0
for altitude_m in ALTITUDES_M:
    for speed_mps in SPEEDS_MPS:
        for mass_kg in MASSES_KG:
            whisper.set_trim_condition(
                TrimCondition(altitude_m=altitude_m, speed_mps=speed_mps, mass_kg=mass_kg)
            )
            result = whisper.run_trim()
            run_count += 1
            print(
                f"out_{result['run_id']}.csv : "
                f"altitude={altitude_m} m, speed={speed_mps} m/s, mass={mass_kg} kg "
                f"-> alpha={result['alpha_deg']} deg, converged={result['converged']}"
            )

print(f"\n{run_count} calculs de trim termines dans {EXAMPLES_DIR / 'out'}")

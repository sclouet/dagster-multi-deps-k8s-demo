"""Demo autonome : `python -m whisper`.

Genere un avion XML minimal dans un dossier temporaire pour ne dependre
d'aucun fichier externe, puis enchaine 2 calculs de trim pour montrer que
out_1.csv et out_2.csv sont bien crees (id = index d'appel sur l'instance).
"""

import tempfile
from pathlib import Path

from . import TrimCondition, TrimParam, Whisper


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        aircraft_path = tmp_dir / "aircraft_example.xml"
        aircraft_path.write_text(
            '<?xml version="1.0"?>\n<aircraft name="demo-aircraft"/>\n',
            encoding="utf-8",
        )

        whisper = Whisper()
        whisper.set_dir(str(tmp_dir / "out"))
        whisper.set_seek(42)
        whisper.load_aircraft(str(aircraft_path))
        whisper.set_trim_condition(
            TrimCondition(altitude_m=3000, speed_mps=120, mass_kg=18000)
        )
        whisper.set_trim_param(TrimParam(max_iterations=50))

        for _ in range(2):
            result = whisper.run_trim()
            print(result)

        assert Whisper() is whisper, "Whisper doit rester un singleton"
        print("OK : singleton confirme, out_1.csv et out_2.csv generes dans", tmp_dir / "out")


if __name__ == "__main__":
    main()

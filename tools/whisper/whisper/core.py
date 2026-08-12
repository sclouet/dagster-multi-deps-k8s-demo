"""Whisper : outil de calcul de trim avion.

Classe singleton : `Whisper()` renvoie toujours la meme instance dans un
process donne. Les methodes set_* preparent les donnees du calcul ; run_trim
execute le calcul et, par defaut, ecrit son resultat dans out_<id>.csv (id =
index d'appel de run_trim sur cette instance, en partant de 1).
"""

import csv
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .trim import TrimCondition, TrimParam


class Whisper:
    _instance: Optional["Whisper"] = None

    def __new__(cls) -> "Whisper":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self) -> None:
        self._seek: Optional[int] = None
        self._dir: Optional[Path] = None
        self._aircraft_path: Optional[Path] = None
        self._aircraft_name: Optional[str] = None
        self._trim_condition: Optional[TrimCondition] = None
        self._trim_param: Optional[TrimParam] = None
        self._run_count: int = 0

    def set_seek(self, seek: int) -> "Whisper":
        """Graine de reproductibilite du calcul (facultative, run_trim retombe
        sur l'index d'appel si non definie)."""
        self._seek = seek
        return self

    def set_dir(self, path: str) -> "Whisper":
        """Dossier de sortie des out_<id>.csv (cree si absent)."""
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        self._dir = directory
        return self

    def load_aircraft(self, path: str) -> "Whisper":
        """Charge la definition avion depuis un fichier XML."""
        xml_path = Path(path)
        if not xml_path.is_file():
            raise FileNotFoundError(f"Fichier avion introuvable : {xml_path}")
        root = ET.parse(xml_path).getroot()
        self._aircraft_path = xml_path
        self._aircraft_name = root.get("name", xml_path.stem)
        return self

    def set_trim_condition(self, trim_condition: TrimCondition) -> "Whisper":
        self._trim_condition = trim_condition
        return self

    def set_trim_param(self, trim_param: TrimParam) -> "Whisper":
        self._trim_param = trim_param
        return self

    def run_trim(self, save_data: bool = True) -> dict:
        """Execute un calcul de trim et, si save_data, ecrit out_<id>.csv
        dans le dossier fixe par set_dir. id = index d'appel de run_trim sur
        cette instance (1 au premier appel, 2 au second, etc.)."""
        missing = [
            name
            for name, value in (
                ("aircraft (load_aircraft)", self._aircraft_path),
                ("trim_condition (set_trim_condition)", self._trim_condition),
                ("trim_param (set_trim_param)", self._trim_param),
            )
            if value is None
        ]
        if missing:
            raise RuntimeError(
                "Donnees manquantes avant run_trim : " + ", ".join(missing)
            )
        if save_data and self._dir is None:
            raise RuntimeError("save_data=True necessite un dossier (set_dir).")

        self._run_count += 1
        run_id = self._run_count

        result = self._solve_trim(run_id)

        if save_data:
            out_path = self._dir / f"out_{run_id}.csv"
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(result.keys()))
                writer.writeheader()
                writer.writerow(result)
            result["output_path"] = str(out_path)

        return result

    def _solve_trim(self, run_id: int) -> dict:
        """Calcul de trim - STUB : a remplacer par le vrai solveur.

        Reproductible via set_seek (ou, a defaut, via l'index d'appel).
        """
        rng = random.Random(self._seek if self._seek is not None else run_id)
        condition = self._trim_condition
        param = self._trim_param

        alpha_deg = round(2.0 + condition.mass_kg / 20000 + rng.uniform(-0.5, 0.5), 4)
        elevator_deg = round(-alpha_deg * 0.8 + rng.uniform(-0.2, 0.2), 4)
        thrust_n = round(condition.mass_kg * 9.81 * 0.08 + rng.uniform(-50, 50), 2)
        iterations = rng.randint(1, param.max_iterations)
        converged = iterations < param.max_iterations

        return {
            "run_id": run_id,
            "aircraft": self._aircraft_name,
            "altitude_m": condition.altitude_m,
            "speed_mps": condition.speed_mps,
            "mass_kg": condition.mass_kg,
            "cg_fraction": condition.cg_fraction,
            "alpha_deg": alpha_deg,
            "elevator_deg": elevator_deg,
            "thrust_n": thrust_n,
            "iterations": iterations,
            "converged": converged,
        }

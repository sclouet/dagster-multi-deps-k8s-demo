"""Whisper : outil de calcul de trim avion.

Classe singleton : `Whisper()` renvoie toujours la meme instance dans un
process donne. Les methodes set_* preparent les donnees du calcul ; run_trim
execute le calcul et, par defaut, ecrit son resultat dans out_<id>.csv (id =
index d'appel de run_trim sur cette instance, en partant de 1).

REGLE DE CONSTRUCTION - LOGGING (s'applique a toute methode ajoutee a cette
classe a l'avenir) :
  1. A la creation de l'instance (une seule fois, singleton), un fichier de
     log dedie est ouvert - nom unique, incluant l'heure de creation (voir
     _make_logger). Le constructeur y logue l'identifiant de l'instance.
  2. Toute methode PUBLIQUE doit etre decoree avec @_log_call : ca logue en
     DEBUG le nom de la methode et l'heure de l'appel, avant son execution.
"""

import csv
import functools
import logging
import random
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

from .trim import TrimCondition, TrimParam

LOG_DIR = Path("logs")


def _log_call(method):
    """Decorateur d'instrumentation - voir la REGLE DE CONSTRUCTION en tete
    de module. A appliquer a toute nouvelle methode publique de Whisper."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        self._logger.debug(
            "Appel de %s() a %s", method.__name__, datetime.now().isoformat()
        )
        return method(self, *args, **kwargs)

    return wrapper


class Whisper:
    _instance: Optional["Whisper"] = None

    def __new__(cls) -> "Whisper":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self) -> None:
        self._instance_id = uuid.uuid4().hex
        self._logger = self._make_logger()
        self._logger.info("Whisper cree, id=%s", self._instance_id)

        self._seek: Optional[int] = None
        self._dir: Optional[Path] = None
        self._aircraft_path: Optional[Path] = None
        self._aircraft_name: Optional[str] = None
        self._trim_condition: Optional[TrimCondition] = None
        self._trim_param: Optional[TrimParam] = None
        self._run_count: int = 0

    def _make_logger(self) -> logging.Logger:
        """Cree le fichier de log de cette instance : nom unique (heure de
        creation + identifiant d'instance), niveau DEBUG."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        log_path = LOG_DIR / f"whisper_{timestamp}_{self._instance_id}.log"

        logger = logging.getLogger(f"whisper.{self._instance_id}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    @_log_call
    def set_seek(self, seek: int) -> "Whisper":
        """Graine de reproductibilite du calcul (facultative, run_trim retombe
        sur l'index d'appel si non definie)."""
        self._seek = seek
        return self

    @_log_call
    def set_dir(self, path: str) -> "Whisper":
        """Dossier de sortie des out_<id>.csv (cree si absent)."""
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        self._dir = directory
        return self

    @_log_call
    def load_aircraft(self, path: str) -> "Whisper":
        """Charge la definition avion depuis un fichier XML."""
        xml_path = Path(path)
        if not xml_path.is_file():
            raise FileNotFoundError(f"Fichier avion introuvable : {xml_path}")
        root = ET.parse(xml_path).getroot()
        self._aircraft_path = xml_path
        self._aircraft_name = root.get("name", xml_path.stem)
        return self

    @_log_call
    def set_trim_condition(self, trim_condition: TrimCondition) -> "Whisper":
        self._trim_condition = trim_condition
        return self

    @_log_call
    def set_trim_param(self, trim_param: TrimParam) -> "Whisper":
        self._trim_param = trim_param
        return self

    @_log_call
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

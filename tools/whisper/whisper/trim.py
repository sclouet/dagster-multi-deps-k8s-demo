"""Types de donnees pour les calculs de trim de Whisper.

Champs volontairement simples/plausibles pour un calcul de trim avion -
a ajuster selon le besoin reel.
"""

from dataclasses import dataclass


@dataclass
class TrimCondition:
    """Point de vol a trimmer."""

    altitude_m: float
    speed_mps: float
    mass_kg: float
    cg_fraction: float = 0.25


@dataclass
class TrimParam:
    """Parametres numeriques du solveur de trim."""

    tolerance: float = 1e-6
    max_iterations: int = 100
    relaxation: float = 1.0

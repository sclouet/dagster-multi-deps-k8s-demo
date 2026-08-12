"""Logique metier de tool_score.

Tourne sous numpy==1.23.5 + scikit-learn==1.0.2 (stack "ML legacy", python
3.9). scikit-learn==1.0.2 casse avec numpy>=1.24 (suppression des alias
deprecies np.float/np.int), d'ou le pin numpy<1.24 - qui entre en conflit
avec pandas==2.2.2 de tool_enrich (numpy>=1.26 sur python 3.12). Voir
scripts/check-incompatibility.ps1.
"""

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def score_orders(enriched_orders: pd.DataFrame) -> pd.DataFrame:
    """Normalise amount_eur en un score [0, 1] avec MinMaxScaler (sklearn)."""
    df = enriched_orders.copy()
    scaler = MinMaxScaler()
    df["risk_score"] = scaler.fit_transform(df[["amount_eur"]])
    df["sklearn_stack"] = "scikit-learn==1.0.2 / numpy==1.23.5"
    return df

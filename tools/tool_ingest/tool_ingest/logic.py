"""Logique metier de tool_ingest.

Tourne sous pandas==1.5.3 (stack "legacy"). C'est deliberement une version
de pandas trop ancienne pour cohabiter avec tool_enrich (pandas==2.2.2) ou
tool_score (numpy==1.23.5 fige par scikit-learn==1.0.2) dans un seul
environnement - voir scripts/check-incompatibility.ps1.
"""

import pandas as pd

_RAW_ORDERS = [
    {"order_id": 1, "customer": "acme", "amount": 120.50, "currency": "EUR"},
    {"order_id": 2, "customer": "globex", "amount": 89.90, "currency": "EUR"},
    {"order_id": 3, "customer": "initech", "amount": 452.00, "currency": "USD"},
    {"order_id": 4, "customer": "acme", "amount": 15.00, "currency": "EUR"},
]


def build_raw_orders() -> pd.DataFrame:
    """Simule l'ingestion d'un lot de commandes brutes."""
    df = pd.DataFrame(_RAW_ORDERS)
    df["pandas_version"] = pd.__version__
    return df

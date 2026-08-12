"""Logique metier de tool_enrich.

Tourne sous pandas==2.2.2 + pydantic>=2 (stack "moderne"). pandas 2.2.2
exige numpy>=1.26, ce qui entre en conflit avec numpy==1.23.5 fige par
tool_score (scikit-learn==1.0.2) - voir scripts/check-incompatibility.ps1.
"""

from typing import Literal

import pandas as pd
from pydantic import BaseModel

_EUR_RATES = {"EUR": 1.0, "USD": 0.92}


class OrderRow(BaseModel):
    order_id: int
    customer: str
    amount: float
    currency: Literal["EUR", "USD"]


def enrich_orders(raw_orders: pd.DataFrame) -> pd.DataFrame:
    """Valide chaque ligne (pydantic v2) puis convertit les montants en EUR."""
    validated = [
        OrderRow(**row) for row in raw_orders.to_dict(orient="records")
    ]
    df = pd.DataFrame([row.model_dump() for row in validated])
    df["amount_eur"] = df.apply(
        lambda r: round(r["amount"] * _EUR_RATES[r["currency"]], 2), axis=1
    )
    df["pandas_version"] = pd.__version__
    return df

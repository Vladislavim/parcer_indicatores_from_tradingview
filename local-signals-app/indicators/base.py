from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class Signal:
    type: str      # "BUY" | "SELL" | "INFO"
    name: str      # "BOS" | "CHoCH" | "Trend"
    message: str
    ts_ms: int

class IndicatorBase:
    name: str = "Unnamed"

    @staticmethod
    def default_params() -> Dict[str, Any]:
        return {}

    def compute(self, candles, state: Dict[str, Any], params: Dict[str, Any]) -> List[Signal]:
        raise NotImplementedError

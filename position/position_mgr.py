from dataclasses import dataclass, field
from typing import Dict

@dataclass
class PosState:
    peak_profit_pct: float = 0.0   # 進場後最高的利潤%
    add_count: int = 0             # 已加碼次數
    last_breakout_price: float = 0.0  # 最近一次突破加碼的觸發價（避免連續觸發）

class PositionManager:
    def __init__(self):
        self.state: Dict[str, PosState] = {}

    def get(self, symbol: str) -> PosState:
        if symbol not in self.state:
            self.state[symbol] = PosState()
        return self.state[symbol]

    def reset(self, symbol: str):
        self.state[symbol] = PosState()

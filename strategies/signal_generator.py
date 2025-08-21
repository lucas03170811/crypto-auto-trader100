# strategies/signal_generator.py
from typing import Optional
from .trend import generate_trend_signal
from .revert import generate_revert_signal

async def generate_signal(client, symbol: str) -> Optional[str]:
    # 先看趨勢，再看反轉（保留你原本優先順序）
    t = await generate_trend_signal(client, symbol)
    if t:
        return t
    r = await generate_revert_signal(client, symbol)
    return r

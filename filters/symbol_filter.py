import asyncio
from typing import List
from decimal import Decimal
import config

async def _metrics_for(client, symbol: str):
    try:
        prem = await client.get_premium_index(symbol)
        funding = Decimal(str(prem.get("lastFundingRate", "0"))) if prem else Decimal("0")
    except Exception:
        funding = Decimal("0")
    try:
        info = await client.get_24h_stats(symbol)
        vol = Decimal(str(info.get("quoteVolume", "0"))) if info else Decimal("0")
    except Exception:
        vol = Decimal("0")
    return symbol, funding, vol

async def shortlist(client, max_candidates: int = 6) -> List[str]:
    tasks = [ _metrics_for(client, s) for s in config.SYMBOL_POOL ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    rows = []
    for r in results:
        if isinstance(r, Exception): continue
        rows.append(r)

    approved = [
        s for s,f,v in rows
        if f >= Decimal(str(config.FUNDING_RATE_MIN)) and v >= Decimal(str(config.VOLUME_MIN_USD))
    ]
    if approved:
        return approved[:max_candidates]

    rows.sort(key=lambda x: x[2], reverse=True)
    return [s for s,_,_ in rows[:max_candidates]]

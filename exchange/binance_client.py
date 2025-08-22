import os, asyncio
from typing import Optional, Dict, Any
from decimal import Decimal, getcontext
from binance.um_futures import UMFutures
import config

getcontext().prec = 28

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        base_url = "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"
        self.client = UMFutures(key=api_key, secret=api_secret, base_url=base_url)
        self._sem = asyncio.Semaphore(int(os.getenv("BINANCE_MAX_CONCURRENCY", "5")))

    async def _run(self, fn, *args, **kwargs):
        async with self._sem:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    @staticmethod
    def _D(x) -> Decimal: return Decimal(str(x))
    @staticmethod
    def _floor_step(value: Decimal, step: Decimal) -> Decimal:
        if step == 0: return value
        return (value // step) * step

    # ----- market/info -----
    async def exchange_info(self) -> Dict[str, Any]:
        return await self._run(self.client.exchange_info)

    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        try:
            info = await self.exchange_info()
            for s in info.get("symbols", []):
                if s.get("symbol") == symbol: return s
        except Exception: pass
        return None

    async def get_price(self, symbol: str) -> Optional[Decimal]:
        try:
            res = await self._run(self.client.ticker_price, symbol=symbol)
            return self._D(res.get("price"))
        except Exception: return None

    async def get_24h_stats(self, symbol: str) -> Optional[dict]:
        try: return await self._run(self.client.ticker_24hr, symbol=symbol)
        except Exception: return None

    async def get_premium_index(self, symbol: str) -> Optional[dict]:
        try: return await self._run(self.client.premium_index, symbol=symbol)
        except Exception: return None

    async def get_klines(self, symbol: str, interval: str = None, limit: int = None):
        interval = interval or config.KLINE_INTERVAL
        limit = limit or config.KLINE_LIMIT
        return await self._run(self.client.klines, symbol=symbol, interval=interval, limit=limit)

    # ----- account/position -----
    async def get_equity(self) -> Decimal:
        try:
            balances = await self._run(self.client.balance)
            for b in balances:
                if b.get("asset") == "USDT":
                    return self._D(b.get("balance"))
        except Exception: pass
        return Decimal("0")

    async def change_leverage(self, symbol: str, leverage: int):
        try: return await self._run(self.client.change_leverage, symbol=symbol, leverage=leverage)
        except Exception: return None

    async def get_position(self, symbol: str) -> Optional[dict]:
        try:
            res = await self._run(self.client.position_risk, symbol=symbol)
            if isinstance(res, list):
                for p in res:
                    if p.get("symbol") == symbol:
                        return {
                            "entryPrice": self._D(p.get("entryPrice", "0")),
                            "positionAmt": self._D(p.get("positionAmt", "0")),
                            "unrealizedProfit": self._D(p.get("unRealizedProfit", p.get("unrealizedProfit", "0"))),
                            "leverage": self._D(p.get("leverage", "0"))
                        }
        except Exception: pass
        return None

    # ----- order helpers -----
    async def _lot_size_constraints(self, symbol_info: dict):
        stepSize = minQty = minNotional = Decimal("0")
        for f in symbol_info.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                stepSize = self._D(f.get("stepSize")); minQty = self._D(f.get("minQty"))
            if f.get("filterType") == "MIN_NOTIONAL":
                minNotional = self._D(f.get("notional", f.get("minNotional", "0")))
        return stepSize, minQty, minNotional

    async def _quantize_qty(self, symbol: str, qty: Decimal) -> Decimal:
        info = await self.get_symbol_info(symbol)
        if not info: return qty
        step, minQty, _ = await self._lot_size_constraints(info)
        q = self._floor_step(qty, step)
        if q < minQty: return Decimal("0")
        return q

    async def open_long(self, symbol: str, qty: Decimal):
        q = await self._quantize_qty(symbol, qty)
        if q <= 0: return None
        return await self._run(self.client.new_order, symbol=symbol, side="BUY", type="MARKET", quantity=str(q))

    async def open_short(self, symbol: str, qty: Decimal):
        q = await self._quantize_qty(symbol, qty)
        if q <= 0: return None
        return await self._run(self.client.new_order, symbol=symbol, side="SELL", type="MARKET", quantity=str(q))

    async def close_position(self, symbol: str):
        pos = await self.get_position(symbol)
        if not pos: return None
        amt = pos["positionAmt"]
        if amt == 0: return None
        side = "SELL" if amt > 0 else "BUY"
        qty = await self._quantize_qty(symbol, abs(amt))
        if qty <= 0: return None
        try:
            return await self._run(self.client.new_order, symbol=symbol, side=side, type="MARKET",
                                   quantity=str(qty), reduceOnly=True)
        except Exception as e:
            print(f"[CLIENT] close_position error {symbol}: {e}")
            return None

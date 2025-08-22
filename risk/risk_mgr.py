from decimal import Decimal, getcontext
from typing import Optional, Dict
import config
from exchange.binance_client import BinanceClient

getcontext().prec = 28

class RiskManager:
    def __init__(self, client: BinanceClient, equity_ratio: float = None):
        self.client = client
        self.equity_ratio = Decimal(str(equity_ratio if equity_ratio is not None else config.EQUITY_RATIO))
        self.high_water: Dict[str, Decimal] = {}
        self.pyramids: Dict[str, int] = {}

    async def get_order_qty(self, symbol: str) -> Decimal:
        price = await self.client.get_price(symbol)
        if not price or price <= 0: return Decimal("0")
        equity = await self.client.get_equity()
        if equity <= 0: return Decimal("0")
        notional = Decimal(str(equity)) * self.equity_ratio
        raw_qty = (notional * Decimal(str(config.LEVERAGE))) / Decimal(str(price))
        q = await self.client._quantize_qty(symbol, raw_qty)
        return q

    async def _place_with_resize(self, symbol: str, side: str, qty: Decimal, max_retries: int = 3):
        cur = qty
        for _ in range(max_retries + 1):
            try:
                if side == "LONG": return await self.client.open_long(symbol, cur)
                if side == "SHORT": return await self.client.open_short(symbol, cur)
                print(f"[RISK] Unknown side {side}"); return None
            except Exception as e:
                emsg = str(e)
                if "-2019" in emsg or "Margin is insufficient" in emsg:
                    cur = (cur * Decimal("0.5")).quantize(Decimal("0.00000001"))
                    if cur <= 0:
                        print(f"[RISK] qty too small after resize: {symbol}")
                        return None
                    print(f"[RISK] Margin insufficient, retry with smaller qty={cur} ({symbol})")
                    continue
                else:
                    print(f"[RISK] place order error {symbol}: {e}")
                    return None
        return None

    async def execute_trade(self, symbol: str, side: str):
        try:
            qty = await self.get_order_qty(symbol)
            if qty <= 0:
                print(f"[RISK] qty too small: {symbol}")
                return None
            return await self._place_with_resize(symbol, side, qty)
        except Exception as e:
            print(f"[RISK] execute_trade error {symbol}: {e}")
            return None

    async def add_pyramid(self, symbol: str, side: str):
        if self.pyramids.get(symbol, 0) >= config.MAX_PYRAMID:
            return None
        res = await self.execute_trade(symbol, side)
        if res:
            self.pyramids[symbol] = self.pyramids.get(symbol, 0) + 1
            print(f"[PYRAMID] {symbol} count={self.pyramids[symbol]}")
        return res

    async def _profit_ratio(self, symbol: str) -> Optional[Decimal]:
        pos = await self.client.get_position(symbol)
        if not pos or pos["positionAmt"] == 0 or pos["entryPrice"] == 0: return None
        notional = abs(pos["positionAmt"]) * pos["entryPrice"]
        if notional <= 0: return None
        return pos["unrealizedProfit"] / notional

    async def monitor_symbol(self, symbol: str):
        pos = await self.client.get_position(symbol)
        if not pos or pos["positionAmt"] == 0:
            self.high_water.pop(symbol, None)
            self.pyramids.pop(symbol, None)
            return

        side = "LONG" if pos["positionAmt"] > 0 else "SHORT"
        pr = await self._profit_ratio(symbol)
        if pr is None: return

        hw = self.high_water.get(symbol, Decimal("0"))
        if pr > hw:
            self.high_water[symbol] = pr
            hw = pr

        if pr <= Decimal(str(-config.MAX_LOSS_PCT)):
            print(f"[STOP-LOSS] {symbol} pr={pr:.4f} <= -{config.MAX_LOSS_PCT*100:.1f}% → close")
            await self.client.close_position(symbol)
            self.high_water.pop(symbol, None)
            self.pyramids.pop(symbol, None)
            return

        if pr >= Decimal(str(config.PROFIT_ADD_THRESHOLD_PCT)):
            if self.pyramids.get(symbol, 0) < config.MAX_PYRAMID:
                print(f"[PYRAMID-ON-PROFIT] {symbol} pr={pr:.4f} >= {config.PROFIT_ADD_THRESHOLD_PCT*100:.1f}% → add")
                await self.add_pyramid(symbol, side)

        if hw > 0:
            giveback = (hw - pr)
            if giveback >= hw * Decimal(str(config.TRAILING_GIVEBACK_PCT)):
                print(f"[TRAIL-EXIT] {symbol} pr={pr:.4f}, hw={hw:.4f}, giveback={giveback:.4f} → close")
                await self.client.close_position(symbol)
                self.high_water.pop(symbol, None)
                self.pyramids.pop(symbol, None)
                return

    async def monitor_all(self, symbols):
        from asyncio import gather
        tasks = [ self.monitor_symbol(s) for s in symbols ]
        await gather(*tasks, return_exceptions=True)

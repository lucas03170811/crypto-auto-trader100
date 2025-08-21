# risk/risk_mgr.py
from decimal import Decimal, getcontext
from typing import Optional, Dict
import config
from exchange.binance_client import BinanceClient

getcontext().prec = 28

class RiskManager:
    """
    - 動態計算下單數量（依 EQUITY_RATIO × LEVERAGE）
    - 下單失敗（-2019 保證金不足）時自動縮量重試
    - 追蹤每個 symbol 的「獲利高水位」，用於移動停利
    - 監控持倉：>40% 獲利加碼；回撤20% 平倉；下跌達 -30% 停損
    - 控制加碼層數不超過 MAX_PYRAMID
    """
    def __init__(self, client: BinanceClient, equity_ratio: float = None):
        self.client = client
        self.equity_ratio = Decimal(str(equity_ratio if equity_ratio is not None else config.EQUITY_RATIO))
        # per-symbol 狀態
        self.high_water: Dict[str, Decimal] = {}     # 最高獲利比（相對名目 notional）
        self.pyramids: Dict[str, int] = {}           # 已加碼層數

    # ---------- qty & place ----------
    async def get_order_qty(self, symbol: str) -> Decimal:
        price = await self.client.get_price(symbol)
        if not price or price <= 0:
            return Decimal("0")

        equity = await self.client.get_equity()
        if equity <= 0:
            return Decimal("0")

        notional = Decimal(str(equity)) * self.equity_ratio
        raw_qty = (notional * Decimal(str(config.LEVERAGE))) / Decimal(str(price))
        q = await self.client._quantize_qty(symbol, raw_qty)
        return q

    async def _place_with_resize(self, symbol: str, side: str, qty: Decimal, max_retries: int = 3):
        """
        下單；若提示資金不足，數量每次*0.5重試，最多 max_retries 次
        """
        cur = qty
        for i in range(max_retries + 1):
            try:
                if side == "LONG":
                    return await self.client.open_long(symbol, cur)
                elif side == "SHORT":
                    return await self.client.open_short(symbol, cur)
                else:
                    print(f"[RISK] Unknown side {side}")
                    return None
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
        """
        受 MAX_PYRAMID 限制的加碼行為（外部如 should_pyramid 或獲利加碼調用）
        """
        if self.pyramids.get(symbol, 0) >= config.MAX_PYRAMID:
            return None
        res = await self.execute_trade(symbol, side)
        if res:
            self.pyramids[symbol] = self.pyramids.get(symbol, 0) + 1
            print(f"[PYRAMID] {symbol} count={self.pyramids[symbol]}")
        return res

    # ---------- monitor & trailing ----------
    async def _profit_ratio(self, symbol: str) -> Optional[Decimal]:
        """
        回傳獲利比（未實現損益 / 名目總額），等同於價格變動比例（不含槓桿放大）
        """
        pos = await self.client.get_position(symbol)
        if not pos or pos["positionAmt"] == 0 or pos["entryPrice"] == 0:
            return None
        notional = abs(pos["positionAmt"]) * pos["entryPrice"]
        if notional <= 0:
            return None
        return pos["unrealizedProfit"] / notional  # 例如 0.12 = +12%

    async def monitor_symbol(self, symbol: str):
        pos = await self.client.get_position(symbol)
        if not pos or pos["positionAmt"] == 0:
            # 無倉位，清除狀態
            self.high_water.pop(symbol, None)
            self.pyramids.pop(symbol, None)
            return

        side = "LONG" if pos["positionAmt"] > 0 else "SHORT"
        pr = await self._profit_ratio(symbol)
        if pr is None:
            return

        # 更新高水位
        hw = self.high_water.get(symbol, Decimal("0"))
        if pr > hw:
            self.high_water[symbol] = pr
            hw = pr

        # 1) 最大虧損停損（例如 -30%）
        if pr <= Decimal(str(-config.MAX_LOSS_PCT)):
            print(f"[STOP-LOSS] {symbol} pr={pr:.4f} <= -{config.MAX_LOSS_PCT*100:.1f}% → close")
            await self.client.close_position(symbol)
            self.high_water.pop(symbol, None)
            self.pyramids.pop(symbol, None)
            return

        # 2) 獲利加碼滾倉（例如 +40%）
        if pr >= Decimal(str(config.PROFIT_ADD_THRESHOLD_PCT)):
            if self.pyramids.get(symbol, 0) < config.MAX_PYRAMID:
                print(f"[PYRAMID-ON-PROFIT] {symbol} pr={pr:.4f} >= {config.PROFIT_ADD_THRESHOLD_PCT*100:.1f}% → add")
                await self.add_pyramid(symbol, side)

        # 3) 移動停利：從高水位回撤 >= TRAILING_GIVEBACK_PCT（例如 20%）
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

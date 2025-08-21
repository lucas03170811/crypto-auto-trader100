# engine/hedge_engine.py
import asyncio
from strategies.filter import filter_symbols  # 原本就存在的輕量版篩選
from strategies.trend import generate_trend_signal, should_pyramid
from strategies.revert import generate_revert_signal

class HedgeEngine:
    def __init__(self, client, risk_mgr):
        self.client = client
        self.risk_mgr = risk_mgr

    async def run(self):
        print("[Engine] Running scan...")
        symbols = await filter_symbols(self.client)
        print(f"[Engine] Filtered: {symbols}")

        for symbol in symbols:
            try:
                trend_sig = await generate_trend_signal(self.client, symbol)
                revert_sig = await generate_revert_signal(self.client, symbol)
                signal = trend_sig or revert_sig
                if signal:
                    print(f"[SIGNAL] {symbol} -> {signal}")
                    await self.risk_mgr.execute_trade(symbol, signal)
                    if await should_pyramid(self.client, symbol, side_long=(signal=="LONG")):
                        await self.risk_mgr.execute_trade(symbol, signal)
                else:
                    print(f"[NO SIGNAL] {symbol} no entry")
            except Exception as e:
                print(f"[Engine] error {symbol}: {e}")

import pandas as pd, numpy as np
from typing import Optional
import config

def klines_to_df(klines):
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_asset_volume","num_trades","taker_buy_base","taker_buy_quote","ignore"]
    try:
        df = pd.DataFrame(klines, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df
    except Exception:
        return None

def ema(series, period): return series.ewm(span=period, adjust=False).mean()

async def generate_trend_signal(client, symbol: str) -> Optional[str]:
    try:
        kl = await client.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = klines_to_df(kl)
        if df is None or len(df) < max(config.TREND_EMA_FAST, config.TREND_EMA_SLOW) + 5:
            return None

        close = df["close"]
        ema_fast = ema(close, config.TREND_EMA_FAST)
        ema_slow = ema(close, config.TREND_EMA_SLOW)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=config.MACD_SIGNAL, adjust=False).mean()

        ema_golden = ema_fast.iloc[-2] <= ema_slow.iloc[-2] and ema_fast.iloc[-1] > ema_slow.iloc[-1]
        ema_dead   = ema_fast.iloc[-2] >= ema_slow.iloc[-2] and ema_fast.iloc[-1] < ema_slow.iloc[-1]
        macd_up    = macd_line.iloc[-2] <= signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_dn    = macd_line.iloc[-2] >= signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]

        if ema_golden or macd_up:  return "LONG"
        if ema_dead   or macd_dn:  return "SHORT"
        return None
    except Exception as e:
        print(f"[STRATEGY:trend] error {symbol}: {e}")
        return None

async def should_pyramid(client, symbol: str, side_long: bool) -> bool:
    if not config.PYRAMID_BREAKOUT_ENABLED: return False
    try:
        kl = await client.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = klines_to_df(kl)
        if df is None or len(df) < config.PYRAMID_BREAKOUT_LOOKBACK + 2:
            return False
        curr = df["close"].iloc[-1]
        if side_long:
            prev_high = df["high"].iloc[-(config.PYRAMID_BREAKOUT_LOOKBACK+1):-1].max()
            return curr > prev_high
        else:
            prev_low  = df["low"].iloc[-(config.PYRAMID_BREAKOUT_LOOKBACK+1):-1].min()
            return curr < prev_low
    except Exception as e:
        print(f"[STRATEGY:trend] should_pyramid error {symbol}: {e}")
        return False

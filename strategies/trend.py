# strategies/trend.py
import pandas as pd
import numpy as np
from typing import Optional
import config

# ---- utils ----
def klines_to_df(klines):
    cols = [
        "open_time","open","high","low","close","volume","close_time",
        "quote_asset_volume","num_trades","taker_buy_base","taker_buy_quote","ignore"
    ]
    try:
        df = pd.DataFrame(klines, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df
    except Exception:
        return None

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def macd(series: pd.Series, fast: int, slow: int, signal: int):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, ema_fast, ema_slow

# ---- strategy ----
async def generate_trend_signal(client, symbol: str, interval: str = None) -> Optional[str]:
    """
    保留你原本的趨勢策略：EMA 交叉 + MACD 交叉 擇一觸發
    回傳 "LONG"/"SHORT"/None
    """
    try:
        kl = await client.get_klines(symbol, interval=interval or config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = klines_to_df(kl)
        if df is None or len(df) < max(config.TREND_EMA_SLOW, config.MACD_SIGNAL) + 5:
            return None

        close = df["close"]
        macd_line, signal_line, ema_fast, ema_slow = macd(
            close, config.TREND_EMA_FAST, config.TREND_EMA_SLOW, config.MACD_SIGNAL
        )

        # EMA 交叉
        ema_golden = ema_fast.iloc[-2] <= ema_slow.iloc[-2] and ema_fast.iloc[-1] > ema_slow.iloc[-1]
        ema_dead   = ema_fast.iloc[-2] >= ema_slow.iloc[-2] and ema_fast.iloc[-1] < ema_slow.iloc[-1]

        # MACD 交叉
        macd_up = macd_line.iloc[-2] <= signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_dn = macd_line.iloc[-2] >= signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]

        if ema_golden or macd_up:
            return "LONG"
        if ema_dead or macd_dn:
            return "SHORT"
        return None
    except Exception as e:
        print(f"[STRATEGY:trend] error {symbol}: {e}")
        return None

async def should_pyramid(client, symbol: str, side_long: bool) -> bool:
    """
    保留你原本的「突破前高/前低」加碼邏輯。
    """
    if not config.PYRAMID_BREAKOUT_ENABLED or config.MAX_PYRAMID <= 0:
        return False
    try:
        kl = await client.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=config.PYRAMID_BREAKOUT_LOOKBACK + 5)
        df = klines_to_df(kl)
        if df is None or len(df) < config.PYRAMID_BREAKOUT_LOOKBACK + 2:
            return False

        curr = df["close"].iloc[-1]
        if side_long:
            prev_high = df["high"].iloc[-(config.PYRAMID_BREAKOUT_LOOKBACK+1):-1].max()
            return curr > prev_high
        else:
            prev_low = df["low"].iloc[-(config.PYRAMID_BREAKOUT_LOOKBACK+1):-1].min()
            return curr < prev_low
    except Exception as e:
        print(f"[STRATEGY:trend] should_pyramid error {symbol}: {e}")
        return False

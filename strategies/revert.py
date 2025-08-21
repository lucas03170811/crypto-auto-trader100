# strategies/revert.py
import pandas as pd
import numpy as np
from typing import Optional
import config

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

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

async def generate_revert_signal(client, symbol: str, interval: str = None) -> Optional[str]:
    """
    保留你原本的反轉策略：RSI + 布林帶
    回傳 "LONG"/"SHORT"/None
    """
    try:
        kl = await client.get_klines(symbol, interval=interval or config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = klines_to_df(kl)
        if df is None or len(df) < max(config.REVERT_RSI_PERIOD, config.BOLL_WINDOW) + 5:
            return None

        close = df["close"]
        r = rsi(close, config.REVERT_RSI_PERIOD)
        ma = close.rolling(config.BOLL_WINDOW).mean()
        std = close.rolling(config.BOLL_WINDOW).std()
        upper = ma + config.BOLL_STDDEV * std
        lower = ma - config.BOLL_STDDEV * std

        last_close = close.iloc[-1]
        last_rsi = r.iloc[-1] if len(r) > 0 else None

        # 寬鬆的反轉入場條件（保留你原本閾值 40/60）
        if last_close <= lower.iloc[-1] and last_rsi is not None and last_rsi <= config.REVERT_RSI_OVERSOLD:
            return "LONG"
        if last_close >= upper.iloc[-1] and last_rsi is not None and last_rsi >= config.REVERT_RSI_OVERBOUGHT:
            return "SHORT"
        return None
    except Exception as e:
        print(f"[STRATEGY:revert] error {symbol}: {e}")
        return None

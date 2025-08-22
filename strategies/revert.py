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

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.ewm(alpha=1/period, adjust=False).mean() / down.ewm(alpha=1/period, adjust=False).mean()
    return 100 - (100 / (1 + rs))

async def generate_revert_signal(client, symbol: str) -> Optional[str]:
    try:
        kl = await client.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = klines_to_df(kl)
        if df is None or len(df) < max(config.BOLL_WINDOW, config.REVERT_RSI_PERIOD) + 5:
            return None

        close = df["close"]
        ma = close.rolling(config.BOLL_WINDOW).mean()
        std = close.rolling(config.BOLL_WINDOW).std()
        upper = ma + config.BOLL_STDDEV * std
        lower = ma - config.BOLL_STDDEV * std
        r = rsi(close, config.REVERT_RSI_PERIOD)

        last_close = close.iloc[-1]
        last_rsi = r.iloc[-1] if len(r) > 0 else None

        if last_close <= lower.iloc[-1] and last_rsi is not None and last_rsi <= config.REVERT_RSI_OVERSOLD:
            return "LONG"
        if last_close >= upper.iloc[-1] and last_rsi is not None and last_rsi >= config.REVERT_RSI_OVERBOUGHT:
            return "SHORT"
        return None
    except Exception as e:
        print(f"[STRATEGY:revert] error {symbol}: {e}")
        return None

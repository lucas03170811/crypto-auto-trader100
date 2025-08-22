import pandas as pd
from typing import Optional
import config

def _klines_to_df(klines):
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

def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

async def generate_trend_signal(client, symbol: str) -> Optional[str]:
    """
    趨勢策略（保留）：EMA 快慢線 + MACD 訊號交叉
    - 多頭條件：EMA12 上穿 EMA26 或 MACD 線上穿訊號線 → LONG
    - 空頭條件：EMA12 下穿 EMA26 或 MACD 線下穿訊號線 → SHORT
    - 其餘 → None
    """
    try:
        kl = await client.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
        df = _klines_to_df(kl)
        if df is None or len(df) < max(config.TREND_EMA_FAST, config.TREND_EMA_SLOW) + 5:
            return None

        close = df["close"]
        ema_fast = _ema(close, config.TREND_EMA_FAST)
        ema_slow = _ema(close, config.TREND_EMA_SLOW)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=config.MACD_SIGNAL, adjust=False).mean()

        ema_golden = ema_fast.iloc[-2] <= ema_slow.iloc[-2] and ema_fast.iloc[-1] > ema_slow.iloc[-1]
        ema_dead   = ema_fast.iloc[-2] >= ema_slow.iloc[-2] and ema_fast.iloc[-1] < ema_slow.iloc[-1]
        macd_up    = macd_line.iloc[-2] <= signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_dn    = macd_line.iloc[-2] >= signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]

        if ema_golden or macd_up:
            return "LONG"
        if ema_dead or macd_dn:
            return "SHORT"
        return None
    except Exception as e:
        print(f"[STRATEGY:trend] error {symbol}: {e}")
        return None

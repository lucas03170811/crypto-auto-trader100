# config.py
import os
import sys
from typing import List

print("===== [CONFIG] 載入設定 =====")

API_KEY = os.getenv("API_KEY") or os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_KEY")
API_SECRET = os.getenv("API_SECRET") or os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_SECRET")
TESTNET = os.getenv("TESTNET", "false").lower() in ("1", "true", "yes")

if not API_KEY or not API_SECRET:
    print("[ERROR] 請設定 API_KEY / API_SECRET（或 BINANCE_API_KEY / BINANCE_API_SECRET）")
    sys.exit(1)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))

SYMBOL_POOL: List[str] = [
    "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","ADAUSDT",
    "DOGEUSDT","1000PEPEUSDT", "SUIUSDT","SEIUSDT",

]

EQUITY_RATIO = float(os.getenv("EQUITY_RATIO", "0.02"))
LEVERAGE = int(os.getenv("LEVERAGE", "30"))
MAX_PYRAMID = int(os.getenv("MAX_PYRAMID", "8"))

# ===== 新增：獲利>40% 觸發加碼滾倉（0.40 = 40%）=====
PROFIT_ADD_THRESHOLD_PCT = float(os.getenv("PROFIT_ADD_THRESHOLD_PCT", "0.40"))

# ===== 既有（沿用）：移動停利（回撤%）與最大虧損% =====
TRAILING_GIVEBACK_PCT = float(os.getenv("TRAILING_GIVEBACK_PCT", "0.20"))
MAX_LOSS_PCT = float(os.getenv("MAX_LOSS_PCT", "0.30"))

KLINE_INTERVAL = os.getenv("KLINE_INTERVAL", "15m")
KLINE_LIMIT = int(os.getenv("KLINE_LIMIT", "200"))

TREND_EMA_FAST = int(os.getenv("TREND_EMA_FAST", "12"))
TREND_EMA_SLOW = int(os.getenv("TREND_EMA_SLOW", "26"))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

REVERT_RSI_PERIOD = int(os.getenv("REVERT_RSI_PERIOD", "14"))
REVERT_RSI_OVERSOLD = int(os.getenv("REVERT_RSI_OVERSOLD", "40"))
REVERT_RSI_OVERBOUGHT = int(os.getenv("REVERT_RSI_OVERBOUGHT", "60"))
BOLL_WINDOW = int(os.getenv("BOLL_WINDOW", "20"))
BOLL_STDDEV = float(os.getenv("BOLL_STDDEV", "2.0"))

PYRAMID_BREAKOUT_ENABLED = os.getenv("PYRAMID_BREAKOUT_ENABLED", "true").lower() in ("1","true","yes")
PYRAMID_BREAKOUT_LOOKBACK = int(os.getenv("PYRAMID_BREAKOUT_LOOKBACK", "20"))

VOLUME_MIN_USD = float(os.getenv("VOLUME_MIN_USD", "3000000"))
FUNDING_RATE_MIN = float(os.getenv("FUNDING_RATE_MIN", "-0.03"))

DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() in ("1","true","yes")

print("=================================")

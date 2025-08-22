import pandas as pd

class RevertStrategy:
    def __init__(self, client):
        self.client = client

    def generate_signal(self, symbol, interval="15m", lookback=100):
        """
        反轉策略：
        - RSI < 30 → 做多
        - RSI > 70 → 做空
        - 否則不動作
        """
        try:
            klines = self.client.klines(symbol=symbol, interval=interval, limit=lookback)
            df = pd.DataFrame(klines, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)

            # 計算 RSI
            df["diff"] = df["close"].diff()
            df["gain"] = df["diff"].clip(lower=0)
            df["loss"] = -df["diff"].clip(upper=0)

            avg_gain = df["gain"].rolling(window=14).mean()
            avg_loss = df["loss"].rolling(window=14).mean()

            rs = avg_gain / avg_loss
            df["rsi"] = 100 - (100 / (1 + rs))

            last_rsi = df["rsi"].iloc[-1]

            if last_rsi < 30:
                return "LONG"
            elif last_rsi > 70:
                return "SHORT"
            else:
                return None

        except Exception as e:
            print(f"[STRATEGY:revert] error {symbol}: {e}")
            return None

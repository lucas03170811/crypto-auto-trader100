import pandas as pd

class TrendStrategy:
    def __init__(self, client):
        self.client = client

    def generate_signal(self, symbol, interval="15m", lookback=100):
        """
        簡單趨勢策略：
        - 均線多頭排列 → 做多
        - 均線空頭排列 → 做空
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

            df["ma7"] = df["close"].rolling(window=7).mean()
            df["ma25"] = df["close"].rolling(window=25).mean()
            df["ma99"] = df["close"].rolling(window=99).mean()

            last = df.iloc[-1]

            # 多頭排列 → 做多
            if last["ma7"] > last["ma25"] > last["ma99"]:
                return "LONG"
            # 空頭排列 → 做空
            elif last["ma7"] < last["ma25"] < last["ma99"]:
                return "SHORT"
            else:
                return None

        except Exception as e:
            print(f"[STRATEGY:trend] error {symbol}: {e}")
            return None

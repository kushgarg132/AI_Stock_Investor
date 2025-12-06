import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()

    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, std_dev: int = 2):
        """Bollinger Bands"""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, lower

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """Applies all core indicators to the dataframe"""
        df = df.copy()
        # Ensure required columns exist
        required = ['close', 'high', 'low', 'volume']
        if not all(col in df.columns for col in required):
            raise ValueError(f"DataFrame must contain {required}")

        df['rsi_14'] = Indicators.rsi(df['close'])
        df['sma_50'] = Indicators.sma(df['close'], 50)
        df['sma_200'] = Indicators.sma(df['close'], 200)
        df['ema_9'] = Indicators.ema(df['close'], 9)
        df['atr_14'] = Indicators.atr(df['high'], df['low'], df['close'])
        df['vwap'] = Indicators.vwap(df['high'], df['low'], df['close'], df['volume'])
        
        upper, lower = Indicators.bollinger_bands(df['close'])
        df['bb_upper'] = upper
        df['bb_lower'] = lower
        
        return df

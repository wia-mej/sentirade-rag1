import pandas as pd
import numpy as np
import os

# Fonction pour calculer le RSI (Relative Strength Index)
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

tickers = ["AAPL", "TSLA", "NVDA"]
all_features = []

# Calcul des features techniques pour chaque ticker
for ticker in tickers:
    df = pd.read_csv(f"data/{ticker}_ohlcv.csv", parse_dates=["Date"])
    df = df.set_index("Date")

    feat = pd.DataFrame(index=df.index)
    feat["ticker"] = ticker
    feat["rsi"] = compute_rsi(df["Close"])
    feat["volatility"] = df["Close"].pct_change().rolling(14).std()
    feat["ma_spread"] = df["Close"].rolling(10).mean() - df["Close"].rolling(50).mean()

    all_features.append(feat)

# Concaténer les features de tous les tickers et les sauvegarder dans un fichier CSV
features = pd.concat(all_features).dropna()
features.to_csv("data/features_technical.csv")
print(f"✅ features_technical.csv généré — {len(features)} lignes")
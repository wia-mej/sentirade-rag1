import pandas as pd
import numpy as np
import os

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def process_features(ticker):
    """
    Calcule les indicateurs techniques pour un ticker donné
    """
    path = f"data/{ticker}_ohlcv.csv"
    if not os.path.exists(path):
        return None
    
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.set_index("Date")

    feat = pd.DataFrame(index=df.index)
    feat["ticker"] = ticker
    feat["rsi"] = compute_rsi(df["Close"])
    feat["volatility"] = df["Close"].pct_change().rolling(14).std()
    ma_10 = df["Close"].rolling(10).mean()
    ma_50 = df["Close"].rolling(50).mean()
    feat["ma_spread"] = (ma_10 - ma_50) / ma_50
    
    # Mettre à jour le fichier global
    output_path = "data/features_technical.csv"
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path, index_col=0, parse_dates=True)
        # Supprimer les anciennes features du même ticker
        existing = existing[existing["ticker"] != ticker]
        updated = pd.concat([existing, feat]).dropna()
    else:
        updated = feat.dropna()
        
    updated.to_csv(output_path)
    print(f"[SUCCESS] Features updated for {ticker}")

    # Calculate Benchmarks (Global Universe stats)
    # We take the mean/std of the entire universe to provide context
    benchmark_stats = {
        "rsi_mean": float(updated["rsi"].mean()),
        "volatility_mean": float(updated["volatility"].mean()),
        "spread_mean": float(updated["ma_spread"].mean())
    }

    # Extract latest features for this ticker
    latest = feat.iloc[-1].to_dict()
    latest["date"] = feat.index[-1].strftime("%Y-%m-%d")

    return {
        "ticker_features": latest,
        "market_benchmarks": benchmark_stats
    }

if __name__ == "__main__":
    for t in ["AAPL", "TSLA", "NVDA"]:
        process_features(t)
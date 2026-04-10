import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
import os

def update_regime_labels():
    """
    Recalcule les régimes pour tous les tickers dans features_technical.csv
    """
    path = "data/features_technical.csv"
    if not os.path.exists(path):
        return
    
    features = pd.read_csv(path, index_col=0, parse_dates=True)
    feature_cols = ["rsi", "volatility", "ma_spread"]
    
    scaler = StandardScaler()
    X = scaler.fit_transform(features[feature_cols])
    
    gmm = GaussianMixture(n_components=3, random_state=42)
    features["regime_id"] = gmm.fit_predict(X)
    
    features[["ticker", "regime_id"]].to_csv("data/regime_labels.csv")
    print("[SUCCESS] regime_labels.csv updated")
    return features

def get_regime(ticker, date):
    df_path = "data/regime_labels.csv"
    if not os.path.exists(df_path):
        update_regime_labels()
        
    df = pd.read_csv(df_path, index_col=0, parse_dates=True)
    row = df[(df["ticker"] == ticker) & (df.index == date)]
    if row.empty:
        # Si la date n'est pas trouvée, on prend le régime le plus récent
        ticker_df = df[df["ticker"] == ticker]
        if not ticker_df.empty:
            return int(ticker_df.iloc[-1]["regime_id"])
        return 1 # Défaut: calme
    return int(row["regime_id"].values[0])

if __name__ == "__main__":
    update_regime_labels()
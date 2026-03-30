import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture # pour la détection de régimes
from sklearn.preprocessing import StandardScaler # pour normaliser les features avant GMM

# Charger les features
features = pd.read_csv("data/features_technical.csv", index_col=0, parse_dates=True)
feature_cols = ["rsi", "volatility", "ma_spread"]

# Normalisation
scaler = StandardScaler()
X = scaler.fit_transform(features[feature_cols])

# GMM avec 3 régimes
gmm = GaussianMixture(n_components=3, random_state=42)
features["regime_id"] = gmm.fit_predict(X)

# Sauvegarder
features[["ticker", "regime_id"]].to_csv("data/regime_labels.csv")
print("✅ regime_labels.csv généré")
print(features["regime_id"].value_counts())

# Fonction get_regime()
def get_regime(ticker, date):
    df = pd.read_csv("data/regime_labels.csv", index_col=0, parse_dates=True)
    row = df[(df["ticker"] == ticker) & (df.index == date)]
    if row.empty:
        return None
    return int(row["regime_id"].values[0])

# Test rapide
if __name__ == "__main__":
    result = get_regime("AAPL", "2023-06-01")
    print(f"✅ Régime AAPL le 2023-06-01 : {result}")
import pandas as pd
import numpy as np
import os # pour vérifier l'existence du fichier et sa taille

tickers = ["AAPL", "TSLA", "NVDA"] # les tickers à générer
dates = pd.date_range(start="2020-01-01", end="2024-12-31", freq="B") # génère des dates de jours ouvrables entre 2020 et 2024

prix_depart = {"AAPL": 75, "TSLA": 30, "NVDA": 60}


# Génération de données synthétiques pour chaque ticker
for ticker in tickers:
    path = f"data/{ticker}_ohlcv.csv" # OHLCV = Open, High, Low, Close, Volume

    if os.path.exists(path) and os.path.getsize(path) > 100:
        print(f"⏭️ {ticker} déjà téléchargé — skip")
        continue

    np.random.seed({"AAPL": 1, "TSLA": 2, "NVDA": 3}[ticker])
    close = prix_depart[ticker] * np.cumprod(1 + np.random.normal(0.0003, 0.02, len(dates)))

    df = pd.DataFrame({
        "Date": dates,
        "Open": close * np.random.uniform(0.98, 1.0, len(dates)),
        "High": close * np.random.uniform(1.0, 1.03, len(dates)),
        "Low": close * np.random.uniform(0.97, 1.0, len(dates)),
        "Close": close,
        "Volume": np.random.randint(1000000, 50000000, len(dates))
    })

    df.to_csv(path, index=False)
    print(f"✅ {ticker} généré — {len(df)} jours")
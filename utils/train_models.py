import pandas as pd
import numpy as np
from xgboost import XGBClassifier, XGBRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import LabelEncoder
import pickle
import json

# Charger la feature matrix
df = pd.read_csv("data/feature_matrix_final.csv")
print(f"[SUCCESS] {len(df)} rows loaded")

# Encoder les colonnes catégorielles
le_sentiment = LabelEncoder()
le_signal = LabelEncoder()
df["sentiment_enc"] = le_sentiment.fit_transform(df["sentiment"])
df["rag_signal_enc"] = le_signal.fit_transform(df["rag_signal"])

# Features
feature_cols = ["rsi", "volatility", "ma_spread", "regime_id", 
                "sentiment_enc", "confidence", "rag_signal_enc"]

# Charger les prix pour calculer les targets
prices = {}
for ticker in ["AAPL", "TSLA", "NVDA"]:
    p = pd.read_csv(f"data/{ticker}_ohlcv.csv", parse_dates=["Date"])
    p = p.set_index("Date")
    prices[ticker] = p["Close"]

# Calculer les targets
targets_clf = []
targets_reg = []

for _, row in df.iterrows():
    ticker = row["ticker"]
    date = pd.Timestamp(row["date"])
    
    try:
        price_series = prices[ticker]
        idx = price_series.index.get_loc(date)
        if idx + 1 < len(price_series):
            ret = (price_series.iloc[idx+1] - price_series.iloc[idx]) / price_series.iloc[idx]
            targets_clf.append(1 if ret > 0.01 else 0)
            targets_reg.append(ret)
        else:
            targets_clf.append(0)
            targets_reg.append(0)
    except:
        targets_clf.append(0)
        targets_reg.append(0)

df["target_clf"] = targets_clf
df["target_reg"] = targets_reg

print(f"[SUCCESS] Targets calculated — {sum(targets_clf)} bullish / {len(targets_clf)-sum(targets_clf)} bearish")

# Split temporel
df = df.sort_values("date")
X = df[feature_cols]
y_clf = df["target_clf"]
y_reg = df["target_reg"]

train_size = int(len(df) * 0.7)
val_size = int(len(df) * 0.85)

X_train = X[:train_size]
X_val = X[train_size:val_size]
X_test = X[val_size:]

y_clf_train = y_clf[:train_size]
y_clf_val = y_clf[train_size:val_size]
y_clf_test = y_clf[val_size:]

y_reg_train = y_reg[:train_size]
y_reg_test = y_reg[val_size:]

print(f"[SUCCESS] Split — Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

# XGBoost Classifier
print("\n[PROCESS] Training XGBoost Classifier...")
clf = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
clf.fit(X_train, y_clf_train)

y_pred = clf.predict(X_test)
y_prob = clf.predict_proba(X_test)[:, 1]

metrics_clf = {
    "precision": round(precision_score(y_clf_test, y_pred, zero_division=0), 3),
    "recall": round(recall_score(y_clf_test, y_pred, zero_division=0), 3),
    "f1": round(f1_score(y_clf_test, y_pred, zero_division=0), 3),
    "auc_roc": round(roc_auc_score(y_clf_test, y_prob), 3)
}

print(f"[SUCCESS] Classifier — {metrics_clf}")

with open("models/model_classifier.pkl", "wb") as f:
    pickle.dump(clf, f)

with open("data/metrics_clf.json", "w") as f:
    json.dump(metrics_clf, f, indent=2)

# XGBoost Regressor
print("\n[PROCESS] Training XGBoost Regressor...")
reg = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
reg.fit(X_train, y_reg_train)

with open("models/model_regressor.pkl", "wb") as f:
    pickle.dump(reg, f)

print("[SUCCESS] Regressor saved")
print("\n[FINISH] Training complete!")
print(f"   model_classifier.pkl [SUCCESS]")
print(f"   model_regressor.pkl  [SUCCESS]")
print(f"   metrics_clf.json     [SUCCESS]")
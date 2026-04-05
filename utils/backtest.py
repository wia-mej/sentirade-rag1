import pandas as pd
import numpy as np
import pickle
import json
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, mean_absolute_error, mean_squared_error

# ── Charger les données ──
df = pd.read_csv("data/feature_matrix_final.csv")
df = df.sort_values("date").reset_index(drop=True)

# ── Charger le modèle ──
with open("models/model_classifier.pkl", "rb") as f:
    clf = pickle.load(f)

with open("models/model_regressor.pkl", "rb") as f:
    reg = pickle.load(f)

# ── Encoder les features ──
from sklearn.preprocessing import LabelEncoder
le_sentiment = LabelEncoder()
le_signal = LabelEncoder()
df["sentiment_enc"] = le_sentiment.fit_transform(df["sentiment"])
df["rag_signal_enc"] = le_signal.fit_transform(df["rag_signal"])

feature_cols = ["rsi", "volatility", "ma_spread", "regime_id",
                "sentiment_enc", "confidence", "rag_signal_enc"]

# ── Charger les prix réels ──
prices = {}
for ticker in ["AAPL", "TSLA", "NVDA"]:
    p = pd.read_csv(f"data/{ticker}_ohlcv.csv", parse_dates=["Date"])
    p = p.set_index("Date")
    prices[ticker] = p["Close"]

# ── Calculer les targets ──
targets_clf, targets_reg = [], []
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
            targets_reg.append(0.0)
    except:
        targets_clf.append(0)
        targets_reg.append(0.0)

df["target_clf"] = targets_clf
df["target_reg"] = targets_reg

# ── Split temporel ──
test_size = int(len(df) * 0.15)
df_test = df.iloc[-test_size:]
X_test = df_test[feature_cols]
y_test_clf = df_test["target_clf"]
y_test_reg = df_test["target_reg"]

# ── Prédictions ──
y_pred_clf = clf.predict(X_test)
y_prob_clf = clf.predict_proba(X_test)[:, 1]
y_pred_reg = reg.predict(X_test)

# ── Métriques Classification ──
metrics_clf = {
    "precision": round(precision_score(y_test_clf, y_pred_clf, zero_division=0), 3),
    "recall": round(recall_score(y_test_clf, y_pred_clf, zero_division=0), 3),
    "f1": round(f1_score(y_test_clf, y_pred_clf, zero_division=0), 3),
    "auc_roc": round(roc_auc_score(y_test_clf, y_prob_clf), 3)
}
print("📊 Métriques Classification :", metrics_clf)

# ── Métriques Régression ──
mae = mean_absolute_error(y_test_reg, y_pred_reg)
rmse = np.sqrt(mean_squared_error(y_test_reg, y_pred_reg))
directional = np.mean(np.sign(y_pred_reg) == np.sign(y_test_reg))

metrics_reg = {
    "mae": round(mae, 4),
    "rmse": round(rmse, 4),
    "directional_accuracy": round(directional, 3)
}
print("📊 Métriques Régression :", metrics_reg)

# ── Backtesting ──
portfolio = 10000
cash = portfolio
position = 0
portfolio_values = []

for i, (_, row) in enumerate(df_test.iterrows()):
    ticker = row["ticker"]
    date = pd.Timestamp(row["date"])
    pred = y_pred_clf[i]
    
    try:
        price = prices[ticker].loc[date]
    except:
        portfolio_values.append(cash + position * price if position > 0 else cash)
        continue
    
    if pred == 1 and cash > 0:
        position = cash / price
        cash = 0
    elif pred == 0 and position > 0:
        cash = position * price
        position = 0
    
    total = cash + (position * price if position > 0 else 0)
    portfolio_values.append(total)

# ── Métriques Trading ──
returns = pd.Series(portfolio_values).pct_change().dropna()
sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
max_dd = ((pd.Series(portfolio_values) - pd.Series(portfolio_values).cummax()) / pd.Series(portfolio_values).cummax()).min()
total_return = (portfolio_values[-1] - portfolio) / portfolio * 100

trading_metrics = {
    "sharpe_ratio": round(sharpe, 3),
    "max_drawdown": round(max_dd, 3),
    "total_return_pct": round(total_return, 2),
    "final_portfolio": round(portfolio_values[-1], 2)
}
print("📊 Métriques Trading :", trading_metrics)

# ── Graphique ──
plt.figure(figsize=(12, 5))
plt.plot(portfolio_values, label="Stratégie Agent RAG", color="blue")
plt.axhline(y=portfolio, color="red", linestyle="--", label="Capital initial")
plt.title("Courbe de rendement — Sentirade RAG")
plt.xlabel("Jours")
plt.ylabel("Valeur portfolio ($)")
plt.legend()
plt.tight_layout()
plt.savefig("data/backtest_chart.png")
print("✅ backtest_chart.png sauvegardé")

# ── Sauvegarder les métriques ──
with open("data/trading_metrics.json", "w") as f:
    json.dump(trading_metrics, f, indent=2)

print("\n🎉 Backtesting terminé !")
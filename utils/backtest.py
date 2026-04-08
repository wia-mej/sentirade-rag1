import pandas as pd
import numpy as np
import os
import sys
import pickle
import json
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, mean_absolute_error, mean_squared_error

# ── Charger les données ──
try:
    if os.path.exists("data/feature_matrix_final.csv"):
        df = pd.read_csv("data/feature_matrix_final.csv")
    elif os.path.exists("data/features_technical.csv"):
        print("[WARNING] feature_matrix_final.csv missing, using features_technical.csv + regime_labels.")
        df = pd.read_csv("data/features_technical.csv", index_col=0, parse_dates=True)
        
        # Charger les régimes
        if os.path.exists("data/regime_labels.csv"):
            rl = pd.read_csv("data/regime_labels.csv", index_col=0, parse_dates=True)
            df = df.join(rl["regime_id"], how="left")
        
        # Valeurs palliatives si toujours manquant
        if "regime_id" not in df.columns:
            df["regime_id"] = 1 # Défaut
        
        df["sentiment"] = "neutral"
        df["confidence"] = 0.5
        df["rag_signal"] = "hold"
        df["date"] = df.index
    else:
        print("[ERROR] No data found in 'data/'. Please analyze a ticker first.")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Data loading error: {e}")
    sys.exit(1)

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

# ── Charger les prix réels et le benchmark ──
prices = {}
data_files = [f for f in os.listdir("data") if f.endswith("_ohlcv.csv")]
for f in data_files:
    ticker = f.replace("_ohlcv.csv", "")
    p = pd.read_csv(os.path.join("data", f), parse_dates=["Date"])
    p = p.set_index("Date")
    if hasattr(p.columns, 'nlevels') and p.columns.nlevels > 1:
        p.columns = p.columns.get_level_values(0)
    prices[ticker] = p["Close"]

# Télécharger le benchmark réel (S&P 500) s'il manque
if "^GSPC" not in prices:
    print("[FETCH] Downloading S&P 500 benchmark (^GSPC)...")
    import yfinance as yf
    try:
        sp500 = yf.download("^GSPC", period="5y")
        if hasattr(sp500.columns, 'nlevels') and sp500.columns.nlevels > 1:
            sp500.columns = sp500.columns.get_level_values(0)
        prices["^GSPC"] = sp500["Close"]
        sp500.reset_index().to_csv("data/^GSPC_ohlcv.csv", index=False)
    except Exception as e:
        print(f"[WARNING] Could not download benchmark: {e}")
        prices["^GSPC"] = None

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
test_size = int(len(df) * 0.50)  # On passe à 50% pour plus de visibilité historique
df_test = df.iloc[-test_size:]
X_test = df_test[feature_cols]

# ── Backtesting (Direct Signal Approach) ──
ticker_returns = []
for ticker in df_test["ticker"].unique():
    t_df = df_test[df_test["ticker"] == ticker].copy()
    if ticker not in prices or len(prices[ticker]) < 2:
        continue
    p_series = prices[ticker]
    t_returns, bh_returns = [0.0], [0.0]
    for i in range(1, len(t_df)):
        date_prev, date_curr = pd.Timestamp(t_df.iloc[i-1]["date"]), pd.Timestamp(t_df.iloc[i]["date"])
        try:
            p_prev, p_curr = p_series.loc[date_prev], p_series.loc[date_curr]
            daily_ret = (p_curr - p_prev) / p_prev
            
            # Utilisation DIRECTE du signal de l'agent
            signal = t_df.iloc[i-1]["rag_signal"]
            is_invested = (signal == "buy" or signal == "hold")
            
            t_returns.append(daily_ret if is_invested else 0.0)
            bh_returns.append(daily_ret)
        except:
            t_returns.append(0.0)
            bh_returns.append(0.0)
    t_df["strat_ret"], t_df["bh_ret"] = t_returns, bh_returns
    ticker_returns.append(t_df)

full_results = pd.concat(ticker_returns).sort_values("date")
portfolio_daily = full_results.groupby("date")[["strat_ret", "bh_ret"]].mean()
portfolio_daily.index = pd.to_datetime(portfolio_daily.index) # Courbes d'équité
portfolio_values = (1 + portfolio_daily["strat_ret"]).cumprod() * 10000
buy_hold_values = (1 + portfolio_daily["bh_ret"]).cumprod() * 10000

# Benchmark Réel : S&P 500 (^GSPC)
if prices.get("^GSPC") is not None:
    # Aligner le S&P 500 sur les dates du portfolio
    sp500_series = prices["^GSPC"]
    # On prend les mêmes dates que portfolio_daily pour l'alignement
    benchmark_daily_rets = sp500_series.reindex(portfolio_daily.index).pct_change().fillna(0)
    benchmark_values = (1 + benchmark_daily_rets).cumprod() * 10000
else:
    # Fallback sur le Buy & Hold du ticker si SP500 échoue
    benchmark_values = buy_hold_values
    benchmark_daily_rets = portfolio_daily["bh_ret"]

# ── Métriques Trading ──
start_date, end_date = portfolio_daily.index[0].strftime("%Y-%m-%d"), portfolio_daily.index[-1].strftime("%Y-%m-%d")
returns = portfolio_daily["strat_ret"]
market_returns = portfolio_daily["bh_ret"]

sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
max_dd = ((portfolio_values - portfolio_values.cummax()) / portfolio_values.cummax()).min()
market_max_dd = ((buy_hold_values - buy_hold_values.cummax()) / buy_hold_values.cummax()).min()

# Volatility & Protection vs Real Benchmark
returns = portfolio_daily["strat_ret"]
benchmark_returns = benchmark_daily_rets

strat_vol = returns.std() * np.sqrt(252)
bench_vol = benchmark_returns.std() * np.sqrt(252)
vol_reduction = (bench_vol - strat_vol) / bench_vol * 100 if bench_vol > 0 else 0

bench_max_dd = ((benchmark_values - benchmark_values.cummax()) / benchmark_values.cummax()).min()
dd_ratio = abs(bench_max_dd / max_dd) if abs(max_dd) > 0 else 10.0

# Win rate (days where strategy was right)
win_days = (returns > 0).sum()
total_days = (returns != 0).sum()
win_rate = (win_days / total_days * 100) if total_days > 0 else 0

trading_metrics = {
    "period": f"{start_date} to {end_date}",
    "sharpe_ratio": round(float(sharpe), 3),
    "risk_reduction": f"{round(vol_reduction, 1)}% less volatile than S&P 500",
    "drawdown_protection": f"{round(dd_ratio, 1)}x safer than S&P 500" if abs(max_dd) > 0 else "Total protection",
    "win_rate": f"{round(win_rate, 1)}%",
    "total_return_pct": round(float((portfolio_values.iloc[-1] - 10000) / 100), 2),
    "status": "Alpha Generated" if sharpe > 1.2 else "Preservation Mode"
}
print("[METRICS] Trading Metrics:", trading_metrics)

# ── Graphique Professionnel (Real-World Benchmark) ──
plt.figure(figsize=(14, 7))
plt.style.use('dark_background')
color_strat, color_bench = "#8b5cf6", "#9ca3af"

plt.plot(portfolio_daily.index, portfolio_values, label="Sentirade Agent Strategy", color=color_strat, linewidth=3)
plt.fill_between(portfolio_daily.index, portfolio_values, 10000, color=color_strat, alpha=0.1)
plt.plot(portfolio_daily.index, benchmark_values, label="S&P 500 Benchmark (Real Data)", color=color_bench, linewidth=1.5, alpha=0.6, linestyle="--")
plt.axhline(y=10000, color="white", alpha=0.1, linestyle="-", linewidth=1)

plt.title("STRATEGY PERFORMANCE BENCHMARK (REAL-WORLD INDEX)", loc="left", fontsize=14, fontweight="bold", pad=25, color="white")
plt.text(0, 1.02, f"Period: {start_date} to {end_date} | High-Fidelity RAG Decisions", transform=plt.gca().transAxes, fontsize=9, alpha=0.6)
plt.xlabel("DATE", fontsize=10, alpha=0.5); plt.ylabel("EQUITY ($)", fontsize=10, alpha=0.5)
plt.legend(frameon=False, loc="upper left")
plt.grid(True, which='major', axis='y', alpha=0.05)
plt.gca().spines[['top', 'right']].set_visible(False)
plt.gcf().autofmt_xdate()
plt.tight_layout()
plt.savefig("data/backtest_chart.png", dpi=120, transparent=True)

with open("data/trading_metrics.json", "w") as f:
    json.dump(trading_metrics, f, indent=2)

print("[SUCCESS] Backtesting terminé et graphique mis à jour !")
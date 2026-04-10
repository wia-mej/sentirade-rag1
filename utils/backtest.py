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
test_size = int(len(df) * 0.70)  # On passe à 70% pour une vue historique encore plus large
df_test = df.iloc[-test_size:]
X_test = df_test[feature_cols]

# ── Backtesting ──
ticker_returns = []
COMMISSION = 0.001  # 0.1%
SLIPPAGE = 0.0005   # 0.05%

for ticker in df_test["ticker"].unique():
    t_df = df_test[df_test["ticker"] == ticker].copy().sort_values("date")
    if ticker not in prices:
        continue
        
    ohlcv_path = f"data/{ticker}_ohlcv.csv"
    if not os.path.exists(ohlcv_path): continue
    ohlcv = pd.read_csv(ohlcv_path, parse_dates=["Date"]).set_index("Date")
    if hasattr(ohlcv.columns, 'nlevels') and ohlcv.columns.nlevels > 1:
        ohlcv.columns = ohlcv.columns.get_level_values(0)
    
    t_rets = []
    bh_rets = []
    in_position = False
    
    for i in range(len(t_df)):
        date_curr = pd.Timestamp(t_df.iloc[i]["date"])
        signal = t_df.iloc[i]["rag_signal"]
        
        try:
            idx = ohlcv.index.get_loc(date_curr)
            if idx + 1 >= len(ohlcv):
                t_rets.append(0.0)
                bh_rets.append(0.0)
                continue
                
            p_open_next = ohlcv.iloc[idx+1]["Open"]
            p_close_next = ohlcv.iloc[idx+1]["Close"]
            p_close_curr = ohlcv.iloc[idx]["Close"]
            
            daily_bh_ret = (p_close_next - p_close_curr) / p_close_curr
            bh_rets.append(daily_bh_ret)
            
            strat_ret = 0.0
            # Aggressive Weights: BUY=1.2, HOLD=1.0. Amplitude is a kicker.
            is_buy = signal == "buy"
            is_hold = signal == "hold"
            base_weight = 1.2 if is_buy else 1.0 if is_hold else 0.0
            
            amp_pred = abs(t_df.iloc[i].get("amplitude_predite", 0.01))
            # Kicker: if predicted move > 1.5%, boost position further
            kicker = max(amp_pred / 0.015, 1.0)
            pos_multiplier = min(base_weight * kicker, 2.0)
            
            if (is_buy or is_hold) and not in_position:
                # Execution: Buy at T+1 Open
                ret_trade = (p_close_next - p_open_next) / p_open_next
                strat_ret = (ret_trade * pos_multiplier) - (COMMISSION + SLIPPAGE)
                in_position = True
            elif signal == "sell" and in_position:
                # Execution: Sell at T+1 Open
                ret_trade = (p_open_next - p_close_curr) / p_close_curr
                strat_ret = (ret_trade * pos_multiplier) - (COMMISSION + SLIPPAGE)
                in_position = False
            elif in_position:
                strat_ret = daily_bh_ret * pos_multiplier
            else:
                strat_ret = 0.0
                
            t_rets.append(strat_ret)
        except:
            t_rets.append(0.0)
            bh_rets.append(0.0)
            
    t_df["strat_ret"] = t_rets
    t_df["bh_ret"] = bh_rets
    ticker_returns.append(t_df)

full_results = pd.concat(ticker_returns).sort_values("date")
portfolio_daily = full_results.groupby("date")[["strat_ret", "bh_ret"]].mean()
portfolio_daily.index = pd.to_datetime(portfolio_daily.index)

portfolio_values = (1 + portfolio_daily["strat_ret"]).cumprod() * 10000
buy_hold_values = (1 + portfolio_daily["bh_ret"]).cumprod() * 10000

if "^GSPC" in prices and prices["^GSPC"] is not None:
    sp500_series = prices["^GSPC"]
    benchmark_daily_rets = sp500_series.reindex(portfolio_daily.index).pct_change().fillna(0)
    benchmark_values = (1 + benchmark_daily_rets).cumprod() * 10000
else:
    benchmark_values = buy_hold_values
    benchmark_daily_rets = portfolio_daily["bh_ret"]

# ── Metrics ──
start_date = portfolio_daily.index[0].strftime("%Y-%m-%d")
end_date = portfolio_daily.index[-1].strftime("%Y-%m-%d")
returns = portfolio_daily["strat_ret"]
sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
max_dd = ((portfolio_values - portfolio_values.cummax()) / portfolio_values.cummax()).min()
vol_strat = returns.std() * np.sqrt(252)
vol_bench = benchmark_daily_rets.std() * np.sqrt(252)
risk_red = (vol_bench - vol_strat) / vol_bench * 100 if vol_bench > 0 else 0
win_rate = (returns > 0).sum() / (returns != 0).sum() * 100 if (returns != 0).sum() > 0 else 0

trading_metrics = {
    "period": f"{start_date} to {end_date}",
    "sharpe_ratio": round(float(sharpe), 3),
    "risk_reduction": f"{round(risk_red, 1)}% vs S&P 500",
    "win_rate": f"{round(win_rate, 1)}%",
    "total_return_pct": round(float((portfolio_values.iloc[-1] - 10000) / 100), 2),
    "drawdown": f"{round(max_dd * 100, 2)}%",
    "status": "Alpha Generated" if sharpe > 1.2 else "Preservation Mode"
}
print("[METRICS] Trading Metrics:", trading_metrics)

# ── Plot ──
plt.figure(figsize=(14, 7))
plt.style.use('dark_background')
color_strat, color_bench = "#8b5cf6", "#9ca3af"
plt.plot(portfolio_daily.index, portfolio_values, label="Sentirade Strategy", color=color_strat, linewidth=3)
plt.fill_between(portfolio_daily.index, portfolio_values, 10000, color=color_strat, alpha=0.1)
plt.plot(portfolio_daily.index, benchmark_values, label="S&P 500 Benchmark", color=color_bench, linewidth=1.5, alpha=0.6, linestyle="--")
plt.axhline(y=10000, color="white", alpha=0.1)
plt.title("STRATEGY PERFORMANCE", loc="left", fontsize=14, fontweight="bold", pad=25)
plt.text(0, 1.02, f"Costs: 0.15% | Next-Open Execution | Period: {start_date} to {end_date}", transform=plt.gca().transAxes, fontsize=9, alpha=0.6)
plt.xlabel("DATE"); plt.ylabel("EQUITY ($)")
plt.legend(frameon=False); plt.grid(True, alpha=0.05)
plt.tight_layout()
plt.savefig("data/backtest_chart.png", dpi=120, transparent=True)

with open("data/trading_metrics.json", "w") as f:
    json.dump(trading_metrics, f, indent=2)

print("[SUCCESS] Backtesting complete.")
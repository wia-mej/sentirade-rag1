import pandas as pd
import numpy as np
import json
import csv
import os
import sys
import pickle
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import search_news_db, get_market_regime
from llm_generate import generate_signal

# ── Load XGBoost Models (once at module level) ──
_clf = None
_reg = None

def _load_models():
    global _clf, _reg
    if _clf is None:
        clf_path = "models/model_classifier.pkl"
        reg_path = "models/model_regressor.pkl"
        if os.path.exists(clf_path) and os.path.exists(reg_path):
            with open(clf_path, "rb") as f:
                _clf = pickle.load(f)
            with open(reg_path, "rb") as f:
                _reg = pickle.load(f)
    return _clf, _reg


def _get_technical_features(ticker, date):
    """
    Retrieve the technical features for a given ticker and date.
    Falls back to the nearest available date if exact match not found.
    """
    path = "data/features_technical.csv"
    if not os.path.exists(path):
        return None, None

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df = df[df["ticker"] == ticker]

    if df.empty:
        return None, None

    target_date = pd.Timestamp(date)
    if target_date in df.index:
        row = df.loc[target_date]
        used_date = target_date
    else:
        # Take the closest past date
        past = df[df.index <= target_date]
        if past.empty:
            past = df
        row = past.iloc[-1]
        used_date = past.index[-1]

    features = {
        "rsi": float(row["rsi"]) if "rsi" in row else 50.0,
        "volatility": float(row["volatility"]) if "volatility" in row else 0.02,
        "ma_spread": float(row["ma_spread"]) if "ma_spread" in row else 0.0,
    }
    return features, used_date


def _predict_xgboost(technical_features, regime_id, sentiment, confidence, rag_signal):
    """
    Use loaded XGBoost models to predict direction probability and amplitude.
    """
    clf, reg = _load_models()
    if clf is None or reg is None:
        return None

    # Encode categorical cols the same way train_models.py does
    sentiment_map = {"bearish": 0, "bullish": 1, "neutral": 2}
    signal_map = {"buy": 0, "hold": 1, "sell": 2}

    sentiment_enc = sentiment_map.get(sentiment, 2)
    rag_signal_enc = signal_map.get(rag_signal, 1)

    X = pd.DataFrame([{
        "rsi": technical_features["rsi"],
        "volatility": technical_features["volatility"],
        "ma_spread": technical_features["ma_spread"],
        "regime_id": regime_id if regime_id is not None else 1,
        "sentiment_enc": sentiment_enc,
        "confidence": confidence,
        "rag_signal_enc": rag_signal_enc,
    }])

    prob = float(clf.predict_proba(X)[0][1])
    amplitude = float(reg.predict(X)[0])
    direction = "hausse" if prob >= 0.5 else "baisse"

    return {
        "direction": direction,
        "probabilite": round(prob, 3),
        "amplitude_predite": round(amplitude, 4)
    }


def run_agent(ticker, date, n_results=3, api_key=None, model=None):
    """
    Orchestrated 3-Layer ReAct Loop
    Layer 1: Market Context    (yfinance -> Indicators -> GMM Regime)
    Layer 2: News Intelligence (Headlines -> ChromaDB -> Groq LLaMA)
    Layer 3: Decision          (7-feature Matrix -> XGBoost)
    """
    max_iter = 3
    print(f"\n🚀 Analysis for {ticker} on {date}")
    print("=" * 60)

    decision_log = []
    context = {
        "regime": None,
        "technical": None,
        "news": [],
        "signal": None,
        "xgb": None
    }

    # Layers map to iterations for a clean ReAct flow
    for i in range(max_iter):
        step_num = i + 1
        
        # --- LAYER 1: MARKET CONTEXT ---
        if i == 0:
            layer_name = "LAYER 1 — Market Context"
            reasoning = "Détection du régime de marché et calcul des indicateurs techniques."
            print(f"🔹 {layer_name}")
            print(f"   [DATA] yfinance OHLCV → RSI · Vol · MA Spread")
            feat, used_date = _get_technical_features(ticker, date)
            context["technical"] = feat
            
            print(f"   [INTEL] GMM Regime Detection")
            context["regime"] = get_market_regime(ticker, date)
            regime_name = context["regime"]["regime_name"] if context["regime"] else "unknown"
            
            summary = ""
            if feat:
                summary = f"RSI: {feat['rsi']:.1f} | Vol: {feat['volatility']:.4f} | Regime: {regime_name.upper()}"
                print(f"   → {summary}")
            
            decision_log.append({
                "iteration": step_num,
                "ticker": ticker,
                "date": date,
                "reasoning": reasoning,
                "action": layer_name,
                "findings": summary
            })

        # --- LAYER 2: NEWS INTELLIGENCE (RAG) ---
        elif i == 1:
            layer_name = "LAYER 2 — News Intelligence (RAG)"
            reasoning = "Extraction et analyse des actualités via ChromaDB et Groq LLaMA 3.3."
            print(f"🔹 {layer_name}")
            print(f"   [DATA] Retrieval from ChromaDB (Embeddings Index)")
            context["news"] = search_news_db(f"{ticker} stock news earnings", ticker, date, n_results=n_results)
            
            news_summary = ""
            if not context["news"]:
                print(f"   → [WARNING] No news found. Fallback to Neutral.")
                news_summary = "Aucune news trouvée."
            else:
                for n in context["news"][:2]:
                    print(f"   → News: {n['headline'][:75]}...")
                news_summary = f"{len(context['news'])} news trouvées."
            
            print(f"   [INTEL] LLaMA 3.3 @ Groq Sentiment Analysis")
            try:
                context["signal"] = generate_signal(ticker, date, context["news"], context["regime"], api_key=api_key, model=model)
            except Exception as e:
                print(f"   → [ERROR] LLM analysis failed: {e}")
                context["signal"] = {"sentiment": "neutral", "confidence": 0.5, "signal": "hold", "reasoning": "LLM fallback due to error."}
            
            sentiment_summary = ""
            if context["signal"]:
                s = context["signal"]
                sentiment_summary = f"Sentiment: {s.get('sentiment','?').upper()} (Conf: {s.get('confidence',0):.2f})"
                print(f"   → {sentiment_summary}")

            decision_log.append({
                "iteration": step_num,
                "ticker": ticker,
                "date": date,
                "reasoning": reasoning,
                "action": layer_name,
                "findings": f"{news_summary} | {sentiment_summary}"
            })

        # --- LAYER 3: DECISION ---
        elif i == 2:
            layer_name = "LAYER 3 — Decision"
            reasoning = "Fusion des données techniques et fondamentales via XGBoost."
            print(f"🔹 {layer_name}")
            print(f"   [DATA] Constructing 7-Feature Matrix")
            
            print(f"   [INTEL] XGBoost Classifier + Regressor")
            findings = ""
            if context["technical"] and context["signal"]:
                regime_id = context["regime"]["regime_id"] if context["regime"] else 1
                xgb_res = _predict_xgboost(
                    context["technical"],
                    regime_id,
                    context["signal"].get("sentiment", "neutral"),
                    context["signal"].get("confidence", 0.5),
                    context["signal"].get("signal", "hold")
                )
                context["xgb"] = xgb_res
                if xgb_res:
                    dir_icon = "📈" if xgb_res["direction"] == "hausse" else "📉"
                    findings = f"Direction: {xgb_res['direction'].upper()} | Amplitude: {xgb_res['amplitude_predite']*100:+.2f}%"
                    print(f"   → {findings}")
            
            decision_log.append({
                "iteration": step_num,
                "ticker": ticker,
                "date": date,
                "reasoning": reasoning,
                "action": layer_name,
                "findings": findings
            })

            # Final Conclusion
            sig = context["signal"]
            xgb = context["xgb"] or {}
            print("\n" + "🏁" + "─" * 58)
            print(f"   FINAL DECISION: {sig.get('signal','HOLD').upper()}")
            print(f"   REASONING: {sig.get('reasoning','No consensus achieved.')[:100]}...")
            print("─" * 60)

    # Final result construction
    sig = context["signal"] or {"signal": "hold", "sentiment": "neutral", "reasoning": "Agent loop incomplete."}
    xgb = context["xgb"] or {}
    
    return sig, context["regime"], decision_log, xgb


def build_feature_matrix():
    """
    Build the complete feature matrix for all tickers and dates,
    now including XGBoost direction, probability, and amplitude.
    """
    features_df = pd.read_csv("data/features_technical.csv",
                               index_col=0, parse_dates=True)

    results = []
    log_rows = []

    tickers = ["AAPL", "TSLA", "NVDA"]

    for ticker in tickers:
        ticker_df = features_df[features_df["ticker"] == ticker]
        # Continuous window: last 30 trading days
        sampled = ticker_df.tail(30)

        for date, row in sampled.iterrows():
            date_str = str(date.date())
            print(f"⏳ {ticker} — {date_str}")

            try:
                signal, regime, logs, xgb = run_agent(ticker, date_str)

                xgb = xgb or {}
                results.append({
                    "date": date_str,
                    "ticker": ticker,
                    "rsi": row["rsi"],
                    "volatility": row["volatility"],
                    "ma_spread": row["ma_spread"],
                    "regime_id": regime["regime_id"] if regime else -1,
                    "sentiment": signal.get("sentiment", "neutral") if signal else "neutral",
                    "confidence": signal.get("confidence", 0.5) if signal else 0.5,
                    "rag_signal": signal.get("signal", "hold") if signal else "hold",
                    "direction": xgb.get("direction", "?"),
                    "probabilite": xgb.get("probabilite", 0.5),
                    "amplitude_predite": xgb.get("amplitude_predite", 0.0),
                })

                log_rows.extend(logs)

            except Exception as e:
                print(f"[ERROR] {ticker} {date_str}: {e}")

    df = pd.DataFrame(results)
    df.to_csv("data/feature_matrix_final.csv", index=False)
    print(f"[SUCCESS] feature_matrix_final.csv — {len(df)} lines")

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv("data/decision_log.csv", index=False)
    print(f"[SUCCESS] decision_log.csv — {len(log_df)} lines")

    return df


if __name__ == "__main__":
    print("[RUNTIME] Launching 5-Step ReAct Agent...")
    signal, regime, logs, xgb = run_agent("AAPL", "2024-06-01")
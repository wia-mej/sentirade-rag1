import pandas as pd
import json
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import search_news_db, get_market_regime
from llm_generate import generate_signal

def run_agent(ticker, date, max_iter=3, relevance_threshold=0.6, n_results=3, api_key=None, model=None):
    """
    Boucle ReAct : Reasoning + Acting
    """
    decision_log = []
    context = {"news": [], "regime": None, "signal": None}
    
    for i in range(max_iter):
        # REASONING
        if context["regime"] is None:
            action = "get_regime"
            reasoning = f"Je dois d'abord connaître le régime de marché pour {ticker} le {date}"
        elif "search_news" not in [d["action"] for d in decision_log]:
            action = "search_news"
            reasoning = f"Je dois chercher les news récentes sur {ticker}"
        elif context["signal"] is None:
            action = "generate_signal"
            reasoning = "J'ai assez d'informations pour générer un signal"
        else:
            reasoning = "Signal généré, arrêt de la boucle"
            break

        decision_log.append({
            "iteration": i + 1,
            "ticker": ticker,
            "date": date,
            "reasoning": reasoning,
            "action": action
        })

        # ACTING
        if action == "get_regime":
            context["regime"] = get_market_regime(ticker, date)
            
        elif action == "search_news":
            context["news"] = search_news_db(
                f"{ticker} stock earnings news",
                ticker,
                date,
                n_results=n_results
            )
            # If still no news after search, bail out with Neutral
            if not context["news"]:
                context["signal"] = {
                    "signal": "NEUTRAL",
                    "confidence": 0.0,
                    "sentiment": "neutral",
                    "reasoning": f"No recent news found for {ticker}. Analysis cannot proceed without data."
                }
                decision_log.append({
                    "iteration": i + 1,
                    "ticker": ticker,
                    "date": date,
                    "reasoning": "Zero news items retrieved. Terminating reasoning with Neutral fallback.",
                    "action": "finalize"
                })
                break
            
        elif action == "generate_signal":
            context["signal"] = generate_signal(
                ticker, date,
                context["news"],
                context["regime"],
                api_key=api_key,
                model=model
            )
            if context["signal"]:
                break # Success!

    # Final check if signal was generated
    if context["signal"] is None:
        reason = "Maximum iterations reached."
        if not context["news"]:
            reason = "No relevant news found for this ticker."
            
        context["signal"] = {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "sentiment": "neutral",
            "reasoning": f"Reasoning loop reached limit. {reason}"
        }
        decision_log.append({
            "iteration": max_iter + 1,
            "ticker": ticker,
            "date": date,
            "reasoning": f"Analysis complete. {reason} Returning neutral fallback signal.",
            "action": "finalize"
        })

    return context["signal"], context["regime"], decision_log


def build_feature_matrix():
    """
    Construit la feature matrix complète pour tous les tickers et dates
    """
    features_df = pd.read_csv("data/features_technical.csv", 
                               index_col=0, parse_dates=True)
    
    results = []
    log_rows = []
    
    tickers = ["AAPL", "TSLA", "NVDA"]
    
    # Sample 50 dates par ticker pour aller vite
    for ticker in tickers:
        ticker_df = features_df[features_df["ticker"] == ticker]
        sampled = ticker_df.sample(n=min(50, len(ticker_df)), random_state=42)
        
        for date, row in sampled.iterrows():
            date_str = str(date.date())
            print(f"⏳ {ticker} — {date_str}")
            
            try:
                signal, regime, logs = run_agent(ticker, date_str)
                
                results.append({
                    "date": date_str,
                    "ticker": ticker,
                    "rsi": row["rsi"],
                    "volatility": row["volatility"],
                    "ma_spread": row["ma_spread"],
                    "regime_id": regime["regime_id"] if regime else -1,
                    "sentiment": signal.get("sentiment", "neutral") if signal else "neutral",
                    "confidence": signal.get("confidence", 0.5) if signal else 0.5,
                    "rag_signal": signal.get("signal", "hold") if signal else "hold"
                })
                
                log_rows.extend(logs)
                
            except Exception as e:
                print(f"[ERROR] {ticker} {date_str}: {e}")
    
    # Sauvegarder
    df = pd.DataFrame(results)
    df.to_csv("data/feature_matrix_final.csv", index=False)
    print(f"[SUCCESS] feature_matrix_final.csv — {len(df)} lines")
    
    log_df = pd.DataFrame(log_rows)
    log_df.to_csv("data/decision_log.csv", index=False)
    print(f"[SUCCESS] decision_log.csv — {len(log_df)} lines")
    
    return df


if __name__ == "__main__":
    print("[RUNTIME] Launching ReAct Agent...")
    df = build_feature_matrix()
    print(df.head())
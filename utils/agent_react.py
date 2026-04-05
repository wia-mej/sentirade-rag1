import pandas as pd
import json
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import search_news_db, get_market_regime
from llm_generate import generate_signal

def run_agent(ticker, date, max_iter=3, relevance_threshold=0.6):
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
        elif len(context["news"]) == 0:
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
                n_results=3
            )
            
        elif action == "generate_signal":
            context["signal"] = generate_signal(
                ticker, date,
                context["news"],
                context["regime"]
            )

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
                print(f"❌ Erreur {ticker} {date_str}: {e}")
    
    # Sauvegarder
    df = pd.DataFrame(results)
    df.to_csv("data/feature_matrix_final.csv", index=False)
    print(f"✅ feature_matrix_final.csv — {len(df)} lignes")
    
    log_df = pd.DataFrame(log_rows)
    log_df.to_csv("data/decision_log.csv", index=False)
    print(f"✅ decision_log.csv — {len(log_df)} lignes")
    
    return df


if __name__ == "__main__":
    print("🚀 Lancement de l'agent ReAct...")
    df = build_feature_matrix()
    print(df.head())
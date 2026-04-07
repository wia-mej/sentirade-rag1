import chromadb
import pandas as pd
import sys
import os
import yfinance as yf
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.regime_detection import get_regime

# Initialiser ChromaDB
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name="financial_news")



def fetch_live_news(ticker, n_results=5):
    """
    Récupère les news en direct de yfinance et les ajoute à ChromaDB
    """
    print(f"🌐 Récupération des news en direct pour {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        ids = []
        documents = []
        metadatas = []
        
        for i, item in enumerate(news[:n_results]):
            content = item.get("title", "") + ". " + item.get("content", {}).get("summary", "")
            news_id = f"{ticker}_live_{datetime.now().timestamp()}_{i}"
            
            ids.append(news_id)
            documents.append(content)
            metadatas.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "stock": ticker,
                "source": "yfinance_live"
            })
            
        if ids:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            print(f"✅ {len(ids)} news en direct ajoutées à ChromaDB.")
            
    except Exception as e:
        print(f"⚠️ Erreur fetch_live_news: {e}")

def search_news_db(query, ticker, date, n_results=3):
    """
    Cherche les news pertinentes dans ChromaDB, avec fallback live
    """
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"stock": ticker}
    )
    
    # Si pas de résultats ou news trop anciennes dans la base de test
    if not results["documents"][0] or len(results["documents"][0]) < 1:
        fetch_live_news(ticker)
        # Relancer la requête
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"stock": ticker}
        )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    
    output = []
    for doc, meta in zip(documents, metadatas):
        output.append({
            "headline": doc[:500] + "..." if len(doc) > 500 else doc,
            "date": meta["date"],
            "stock": meta["stock"]
        })
    
    return output

def get_market_regime(ticker, date):
    """
    Retourne le régime de marché pour un ticker et une date
    """
    regime = get_regime(ticker, date)
    regime_names = {0: "haussier", 1: "calme", 2: "baissier"}
    return {
        "regime_id": regime,
        "regime_name": regime_names.get(regime, "inconnu")
    }

# Test
if __name__ == "__main__":
    print("Test search_news_db :")
    results = search_news_db("Apple earnings", "AAPL", "2023-06-01")
    for r in results:
        print(f"  [{r['stock']}] {r['headline']}")
    
    print("\nTest get_market_regime :")
    regime = get_market_regime("AAPL", "2023-06-01")
    print(f"  Régime : {regime['regime_name']}")
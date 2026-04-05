import chromadb
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.regime_detection import get_regime

# Initialiser ChromaDB
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name="financial_news")

def search_news_db(query, ticker, date, n_results=3):
    """
    Cherche les news pertinentes dans ChromaDB
    """
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
            "headline": doc,
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
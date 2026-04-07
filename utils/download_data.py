import pandas as pd
import yfinance as yf
import os

def download_ticker(ticker, period="5y", force=False):
    """
    Télécharge les données réelles via yfinance pour un ticker donné
    """
    path = f"data/{ticker}_ohlcv.csv"
    
    if not force and os.path.exists(path) and os.path.getsize(path) > 100:
        print(f"⏭️ {ticker} déjà présent — skip")
        return True

    print(f"📥 Téléchargement des données pour {ticker} (période={period})...")
    try:
        df = yf.download(ticker, period=period)
        if df.empty:
            print(f"❌ Aucune donnée trouvée pour {ticker}")
            return False
        
        # Nettoyage yfinance (parfois multi-index)
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        df.to_csv(path, index=False)
        print(f"✅ {ticker} sauvegardé — {len(df)} lignes")
        return True
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de {ticker}: {e}")
        return False

if __name__ == "__main__":
    for t in ["AAPL", "TSLA", "NVDA"]:
        download_ticker(t)
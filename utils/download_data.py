import pandas as pd
import yfinance as yf
import os

def download_ticker(ticker, period="5y", force=False):
    """
    Télécharge les données réelles via yfinance pour un ticker donné
    """
    path = f"data/{ticker}_ohlcv.csv"
    
    if not force and os.path.exists(path) and os.path.getsize(path) > 100:
        print(f"[SKIP] {ticker} already present")
        return True

    print(f"[FETCH] Downloading data for {ticker} (period={period})...")
    try:
        df = yf.download(ticker, period=period)
        if df.empty:
            print(f"[ERROR] No data found for {ticker}")
            return False
        
        # Nettoyage yfinance (parfois multi-index)
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        df.to_csv(path, index=False)
        print(f"[SUCCESS] {ticker} saved — {len(df)} rows")
        return True
    except Exception as e:
        print(f"[ERROR] Download error for {ticker}: {e}")
        return False

if __name__ == "__main__":
    for t in ["AAPL", "TSLA", "NVDA"]:
        download_ticker(t)
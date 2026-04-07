from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import pandas as pd
from datetime import datetime

# Adjust path to import from utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.agent_react import run_agent
from utils.tools import search_news_db, fetch_live_news

app = FastAPI(title="Sentirade API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from utils.download_data import download_ticker
from utils.compute_features import process_features
from utils.regime_detection import update_regime_labels

@app.get("/api/signal/{ticker}")
async def get_signal(ticker: str, date: str = None, force: bool = False):
    ticker = ticker.upper()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Auto-discovery and preparation
    ohlcv_path = f"data/{ticker}_ohlcv.csv"
    if force or not os.path.exists(ohlcv_path):
        print(f"Preparing data for {ticker} (Force={force})...")
        success = download_ticker(ticker, period="5y", force=force)
        if not success:
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} introuvable sur yfinance.")
        
        process_features(ticker)
        update_regime_labels()

    try:
        signal, regime, logs = run_agent(ticker, date)
        return {
            "ticker": ticker,
            "date": date,
            "signal": signal,
            "regime": regime,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics")
async def get_metrics():
    try:
        import json
        with open("data/trading_metrics.json", "r") as f:
            return json.load(f)
    except Exception as e:
        return {"error": "Metrics not found. Run backtest first."}

@app.post("/api/backtest")
async def run_backtest():
    import subprocess
    try:
        # Use sys.executable to ensure we use the same venv
        script_path = os.path.join("utils", "backtest.py")
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout}
        else:
            raise HTTPException(status_code=500, detail=result.stderr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse
@app.get("/api/chart")
async def get_chart():
    path = "data/backtest_chart.png"
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Chart not found")

@app.get("/api/news/{ticker}")
async def get_news(ticker: str, query: str = "earnings news", n_results: int = 5, force: bool = False):
    ticker = ticker.upper()
    from utils.tools import fetch_live_news, search_news_db
    
    if force:
        fetch_live_news(ticker)
        
    try:
        date = datetime.now().strftime("%Y-%m-%d")
        news = search_news_db(query, ticker, date, n_results=n_results)
        return {"ticker": ticker, "news": news}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

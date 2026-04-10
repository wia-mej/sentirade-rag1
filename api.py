from fastapi import FastAPI, HTTPException, Header, Query
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
async def get_signal(
    ticker: str, 
    date: str = None, 
    force: bool = False, 
    n_results: int = Query(None),
    x_groq_api_key: str = Header(None, alias="X-Groq-API-Key"),
    x_model_name: str = Header(None, alias="X-Model-Name")
):
    # Dynamic defaults and clamping
    n_results = min(max(int(n_results or 5), 1), 50)
    ticker = ticker.upper()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Auto-discovery and preparation
    ohlcv_path = f"data/{ticker}_ohlcv.csv"
    if force or not os.path.exists(ohlcv_path):
        print(f"Preparing data for {ticker} (Force={force})...")
        success = download_ticker(ticker, period="5y", force=force)
        if not success:
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found on yfinance.")
        
        feat_data = process_features(ticker)
        update_regime_labels()

    try:
        signal, regime, logs, xgb = run_agent(
            ticker, 
            date, 
            n_results=n_results,
            api_key=x_groq_api_key,
            model=x_model_name
        )
        # Re-fetch or use latest calculation
        feat_data = process_features(ticker)
        
        return {
            "ticker": ticker,
            "date": date,
            "signal": signal,
            "regime": regime,
            "logs": logs,
            "xgb": xgb,
            "benchmarks": feat_data["market_benchmarks"],
            "ticker_metrics": feat_data["ticker_features"]
        }
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[ERROR] Backend Error in get_signal: {error_msg}")
        traceback.print_exc()
        
        status_code = 500
        # Precise Groq error mapping
        if "INVALID API KEY" in error_msg.upper() or "401" in error_msg:
            status_code = 401
            error_msg = "Invalid Groq API Key. Please verify it in your Settings."
        elif "RATE LIMIT" in error_msg.upper() or "429" in error_msg:
            status_code = 429
            error_msg = "Groq API rate limit exceeded. Please wait a moment."
        elif "INSUFFICIENT QUOTA" in error_msg.upper():
            status_code = 402 # Payment Required / Quota issues
            error_msg = "Groq API quota exhausted. Please check your billing settings."
            
        raise HTTPException(status_code=status_code, detail=error_msg)

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
async def get_news(ticker: str, query: str = "earnings news", n_results: int = Query(None), force: bool = False):
    n_results = min(max(int(n_results or 5), 1), 50)
    ticker = ticker.upper()
    from utils.tools import fetch_live_news, search_news_db
    
    if force:
        fetch_live_news(ticker, n_results=n_results)
        
    try:
        date = datetime.now().strftime("%Y-%m-%d")
        news = search_news_db(query, ticker, date, n_results=n_results)
        return {"ticker": ticker, "news": news}
    except Exception as e:
        print(f"[ERROR] Backend Error in get_news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
# Sentirade RAG — Technical Changes & Setup

This document outlines the core logic transformations and provides a guide for setting up the environment.

---

## Core Logic Deep Dive

The architecture has evolved from a static prototype to a dynamic, real-time-ready benchmarking engine.

### 1. Unified Auto-Discovery & Data ETL
The API now features a "Self-Healing" data pipeline in the `/api/signal/{ticker}` endpoint.
- **Workflow:** When a new ticker is requested, the system automatically checks for `data/{ticker}_ohlcv.csv`. If missing, it triggers `utils.download_data.download_ticker`, followed by `utils.compute_features.process_features` and `utils.regime_detection.update_regime_labels`.
- **Logic:** This ensures the agent never operates on stale or missing data, abstracting the complexity of data preparation from the frontend.

### 2. Dynamic GMM Regime Detection
Market regimes are no longer static.
- **Refitting:** The Gaussian Mixture Model (GMM) is now refitted on every new ticker addition. This normalization step (using `StandardScaler`) ensures that Regime IDs (0, 1, 2) consistently represent the same relative volatility states across the entire technical feature set.
- **Improved Retrieval:** `get_regime` now proactively updates labels if they are missing and provides a "last-known-state" fallback, ensuring the ReAct agent always has a regime context.

### 3. Smart RAG & Live Feed Fallback
The `search_news_db` tool has transitioned from a simple DB query into a proactive data fetcher.
- **Logic:** If the ChromaDB query returns fewer than 3 relevant results, `utils.tools.fetch_live_news` is triggered. This scrapes the latest news from Yahoo Finance, injects it into the vector store with metadata (stock, date, source), and re-executes the query.
- **Impact:** This solves the "Cold Start" problem for news and ensures the LLM's reasoning is grounded in current market catalysts.

---

## Aesthetic Vision
The project has adopted a **"Mission Control"** aesthetic—a premium financial dashboard look utilizing dark mode, and micro-animations for real-time status tracking.

---

## Installation & Setup

### 1. Prerequisites
- **Python:** 3.10+
- **Node.js:** 18+ (for the Desktop App)
- **API Key:** A valid Groq API Key is required for the LLM.

### 2. Python Backend Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment:
   Create a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_key_here
   ```

### 3. Desktop Frontend Setup
1. Navigate to the desktop directory:
   ```bash
   cd desktop
   ```
2. Install npm packages:
   ```bash
   npm install
   ```

### 4. Running the Application
To launch the full integrated experience:
```bash
cd desktop
npm start
```
*Note: The Electron app automatically spawns the Python FastAPI backend on port 8000.*

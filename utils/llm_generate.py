import os
from groq import Groq
from dotenv import load_dotenv
import json

load_dotenv()

def generate_signal(ticker, date, news, regime, api_key=None, model=None):
    """
    Envoie les news et le régime au LLM et retourne un signal JSON
    """
    # Use dynamic model or fallback
    target_model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # Initialize client dynamically
    key = api_key or os.getenv("GROQ_API_KEY")
    client = Groq(api_key=key)
    news_text = "\n".join([f"- {n['headline']}" for n in news])
    
    prompt = f"""
You are a financial analyst. Analyze the following information and return a JSON signal.

Ticker: {ticker}
Date: {date}
Market Regime: {regime['regime_name']}
Recent News:
{news_text}

Return ONLY a valid JSON object with this exact structure:
{{
    "sentiment": "bullish" or "bearish" or "neutral",
    "confidence": float between 0 and 1,
    "signal": "buy" or "sell" or "hold",
    "reasoning": "brief explanation in one sentence"
}}
"""

    response = client.chat.completions.create(
        model=target_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    content = response.choices[0].message.content
    
    # Parser le JSON
    try:
        signal = json.loads(content)
    except:
        # Extraire le JSON si entouré de texte
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        signal = json.loads(match.group()) if match else {}
    
    return signal

# Test
if __name__ == "__main__":
    from tools import search_news_db, get_market_regime
    
    ticker = "AAPL"
    date = "2023-06-01"
    
    news = search_news_db("Apple stock earnings", ticker, date)
    regime = get_market_regime(ticker, date)
    
    signal = generate_signal(ticker, date, news, regime)
    print(f"[SUCCESS] Signal generated:")
    print(json.dumps(signal, indent=2))
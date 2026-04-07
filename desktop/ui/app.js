const API_URL = 'http://127.0.0.1:8000/api';

// UI Elements
const tickerInput = document.getElementById('ticker-search');
const analyzeBtn = document.getElementById('analyze-btn');
const thoughtLog = document.getElementById('thought-log');
const displayTicker = document.getElementById('display-ticker');
const displaySignal = document.getElementById('display-signal');
const confidenceFill = document.getElementById('confidence-fill');
const confidenceValue = document.getElementById('confidence-value');
const sentimentText = document.getElementById('sentiment-text');
const regimeText = document.getElementById('regime-text');
const newsContainer = document.getElementById('news-container');
const agentStatus = document.getElementById('agent-status');
const currentDateEl = document.getElementById('current-date');

// Set current date
currentDateEl.innerText = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

// Add Log Entry
function addLog(text, type = 'system') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerText = `> ${text}`;
    thoughtLog.appendChild(entry);
    thoughtLog.scrollTop = thoughtLog.scrollHeight;
}

// Update News
function updateNews(news) {
    if (!news || news.length === 0) {
        newsContainer.innerHTML = '<div class="news-placeholder">No catalysts found for this ticker.</div>';
        return;
    }

    // Déduplication par titre + nettoyage du texte
    const processed = [];
    const seen = new Set();

    news.forEach(n => {
        let cleanText = n.headline
            .replace(/^\s*[\.\,\-]\s*/, '') // Enlever les points/virgules au début
            .trim();

        if (!seen.has(cleanText.toLowerCase()) && cleanText.length > 10) {
            seen.add(cleanText.toLowerCase());
            processed.push({ ...n, headline: cleanText });
        }
    });

    newsContainer.innerHTML = processed.map(n => `
        <div class="news-item">
            <div class="news-header">
                <span class="news-date">${n.date || 'LATEST'}</span>
            </div>
            <div class="news-content">${n.headline}</div>
        </div>
    `).join('');
}

// Reset UI
function resetUI(ticker) {
    displayTicker.innerText = ticker.toUpperCase();
    displaySignal.innerText = '--';
    displaySignal.className = 'main-signal';
    confidenceFill.style.width = '0%';
    confidenceValue.innerText = '0%';
    sentimentText.innerText = 'Analyzing...';
    regimeText.innerText = 'Checking...';
    thoughtLog.innerHTML = '';
    newsContainer.innerHTML = '<div class="news-placeholder">Fetching data...</div>';
}

// Handle Analysis
async function runAnalysis(force = false) {
    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) return;

    resetUI(ticker);
    analyzeBtn.disabled = true;
    agentStatus.innerText = 'ANALYZING';
    agentStatus.style.borderColor = '#8b5cf6';

    addLog(`Initializing RAG pipeline for ${ticker}...`, 'system');
    if (force) addLog('Force refreshing market data...', 'system');

    try {
        // We use the ticker search to fetch news first for feedback
        addLog(`Querying ChromaDB for recent ${ticker} news...`, 'acting');
        const newsRes = await fetch(`${API_URL}/news/${ticker}?force=${force}`);
        const newsData = await newsRes.json();
        updateNews(newsData.news);
        addLog(`Found ${newsData.news.length} relevant news items.`, 'result');

        // Now run the full agent
        addLog(`Starting Agent ReAct loop...`, 'thinking');
        const res = await fetch(`${API_URL}/signal/${ticker}`);
        const data = await res.json();

        // Process Logs
        if (data.logs) {
            data.logs.forEach((log, i) => {
                setTimeout(() => {
                    addLog(`[Iteration ${log.iteration}] ${log.reasoning}`, 'thinking');
                    addLog(`Executing Action: ${log.action}`, 'acting');
                }, i * 800);
            });
        }

        // Final Result Display (delayed for effect)
        const totalDelay = (data.logs ? data.logs.length * 800 : 0) + 500;

        setTimeout(() => {
            const signal = data.signal;
            const regime = data.regime;

            displaySignal.innerText = signal.signal;
            displaySignal.classList.add(signal.signal.toLowerCase());

            confidenceFill.style.width = `${signal.confidence * 100}%`;
            confidenceValue.innerText = `${Math.round(signal.confidence * 100)}%`;

            sentimentText.innerText = signal.sentiment;
            sentimentText.style.color = signal.sentiment === 'bullish' ? '#10b981' : (signal.sentiment === 'bearish' ? '#ef4444' : '#f3f4f6');

            regimeText.innerText = regime.regime_name;

            addLog(`Final Signal: ${signal.signal.toUpperCase()} with ${Math.round(signal.confidence * 100)}% confidence.`, 'result');
            addLog(`Reasoning: ${signal.reasoning}`, 'result');

            agentStatus.innerText = 'IDLE';
            agentStatus.style.borderColor = 'rgba(255,255,255,0.08)';
            analyzeBtn.disabled = false;
        }, totalDelay);

    } catch (err) {
        console.error(err);
        addLog(`Error: ${err.message}`, 'system');
        agentStatus.innerText = 'ERROR';
        analyzeBtn.disabled = false;
    }
}

// Event Listeners
analyzeBtn.addEventListener('click', () => runAnalysis(false));
document.getElementById('refresh-btn').addEventListener('click', () => runAnalysis(true));

tickerInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') runAnalysis(false);
});

// Window controls
document.getElementById('min-btn').addEventListener('click', () => {
    window.electronAPI.minimizeWindow();
});

document.getElementById('max-btn').addEventListener('click', () => {
    window.electronAPI.maximizeWindow();
});

document.getElementById('close-btn').addEventListener('click', () => {
    window.electronAPI.closeWindow();
});

// View Switching Logic
const navItems = document.querySelectorAll('.nav-item');
const views = document.querySelectorAll('.view');

navItems.forEach(item => {
    item.addEventListener('click', () => {
        const targetView = item.getAttribute('data-view');

        // Update nav
        navItems.forEach(ni => ni.classList.remove('active'));
        item.classList.add('active');

        // Update view
        views.forEach(v => v.classList.remove('active'));
        document.getElementById(`view-${targetView}`).classList.add('active');

        if (targetView === 'backtest') loadMetrics();
    });
});

// Metric Interpretations
function getInterpretation(key, value) {
    if (typeof value !== 'number') return null;

    switch (key) {
        case 'sharpe_ratio':
            if (value >= 1) return { text: 'Good (>1)', color: '#10b981' };
            if (value >= 0.5) return { text: 'Okay (~0.5)', color: '#f59e0b' };
            return { text: 'Bad (<0.5)', color: '#ef4444' };
        case 'max_drawdown':
            const absDd = Math.abs(value);
            if (absDd <= 0.1) return { text: 'Good (<10%)', color: '#10b981' };
            if (absDd <= 0.2) return { text: 'Okay (<20%)', color: '#f59e0b' };
            return { text: 'Bad (>20%)', color: '#ef4444' };
        case 'total_return_pct':
            if (value > 10) return { text: 'Good (>10%)', color: '#10b981' };
            if (value > 0) return { text: 'Okay (>0%)', color: '#f59e0b' };
            return { text: 'Bad (<0%)', color: '#ef4444' };
        case 'outperformance':
            if (value > 0) return { text: 'Good (Positive)', color: '#10b981' };
            if (value === 0) return { text: 'Neutral', color: '#f59e0b' };
            return { text: 'Bad (Negative)', color: '#ef4444' };
        default:
            return null;
    }
}

async function loadMetrics() {
    const container = document.getElementById('metrics-container');
    try {
        const res = await fetch(`${API_URL}/metrics`);
        const data = await res.json();

        if (data.error) {
            container.innerHTML = `<div class="news-placeholder">${data.error}</div>`;
            return;
        }

        if (data.period) {
            const periodDiv = document.createElement('div');
            periodDiv.className = 'metric-period';
            periodDiv.innerHTML = `<span>Simulation Period: ${data.period}</span>`;
            container.appendChild(periodDiv);
        }

        Object.entries(data).forEach(([key, value]) => {
            if (key === 'period' || key === 'real_life_analogy') return;
            const div = document.createElement('div');
            div.className = 'metric-item';

            const interpretation = getInterpretation(key, value);
            let interpHtml = '';
            if (interpretation) {
                interpHtml = `<div class="metric-interpretation" style="color: ${interpretation.color}; opacity: 0.8; font-size: 0.75rem; margin-top: 4px;">
                    <span>Interpretation: ${interpretation.text}</span>
                </div>`;
            }

            let extra = '';
            if (key === 'status') {
                if (value === 'Alpha Generated') {
                    extra = '<div class="metric-desc">Risk-adjusted excellence (Sharpe > 1). The agent is beating the market.</div>';
                } else if (value === 'Preservation Mode') {
                    extra = '<div class="metric-desc">Defensive posture. The agent is prioritizing capital safety.</div>';
                }
            }

            div.innerHTML = `
                <div class="metric-main">
                    <span class="metric-label">${key.replace(/_/g, ' ').toUpperCase()}</span>
                    <span class="metric-value">${typeof value === 'number' ? value.toLocaleString() : value}</span>
                </div>
                ${extra}
                ${interpHtml}
            `;
            container.appendChild(div);
        });

        // Force reload the chart image
        const chartImg = document.getElementById('backtest-chart');
        chartImg.src = `${API_URL}/chart?t=${new Date().getTime()}`;
    } catch (err) {
        container.innerHTML = '<div class="news-placeholder">Error loading metrics.</div>';
    }
}

// Settings
document.getElementById('save-settings-btn').addEventListener('click', () => {
    const key = document.getElementById('api-key-input').value;
    if (key) {
        addLog('Settings saved locally. Refresh app to apply.', 'system');
    }
});

// Run Backtest
const runBacktestBtn = document.getElementById('run-backtest-btn');
runBacktestBtn.addEventListener('click', async () => {
    runBacktestBtn.disabled = true;
    runBacktestBtn.innerText = 'Simulating...';

    try {
        const res = await fetch(`${API_URL}/backtest`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success') {
            await loadMetrics();
            alert('Simulation completed successfully!');
        } else {
            alert('Error running simulation: ' + (data.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        runBacktestBtn.disabled = false;
        runBacktestBtn.innerText = 'Run Simulation';
    }
});

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
const notificationContainer = document.getElementById('notification-container');
const statusDot = document.getElementById('backend-status-dot');
const statusText = document.getElementById('backend-status-text');

// --- Settings & Persistence ---

const DEFAULT_SETTINGS = {
    apiKey: '',
    maxIter: 3,
    newsCount: 5,
    model: 'llama-3.3-70b-versatile'
};

let currentSettings = { ...DEFAULT_SETTINGS };

function loadSettings() {
    console.log('--- Initializing Sentirade Settings ---');
    const saved = localStorage.getItem('sentirade_settings');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            currentSettings = {
                apiKey: parsed.apiKey || DEFAULT_SETTINGS.apiKey,
                maxIter: Number(parsed.maxIter) || DEFAULT_SETTINGS.maxIter,
                newsCount: Number(parsed.newsCount) || DEFAULT_SETTINGS.newsCount,
                model: parsed.model || DEFAULT_SETTINGS.model
            };
            console.log('[SUCCESS] Configuration loaded from persistent storage.');
        } catch (e) {
            console.error('[ERROR] Failed to parse settings:', e);
            currentSettings = { ...DEFAULT_SETTINGS };
        }
    } else {
        console.log('[INFO] No saved settings found. Using defaults.');
    }

    // Populate UI
    if (document.getElementById('api-key-input')) document.getElementById('api-key-input').value = currentSettings.apiKey;
    if (document.getElementById('max-iter-input')) document.getElementById('max-iter-input').value = currentSettings.maxIter;
    if (document.getElementById('news-count-input')) document.getElementById('news-count-input').value = currentSettings.newsCount;
    if (document.getElementById('model-select')) document.getElementById('model-select').value = currentSettings.model;
}

function saveSettings() {
    const rawMaxIter = parseInt(document.getElementById('max-iter-input').value);
    const rawNewsCount = parseInt(document.getElementById('news-count-input').value);

    currentSettings = {
        apiKey: document.getElementById('api-key-input').value,
        maxIter: Math.max(rawMaxIter, 1),
        newsCount: Math.max(rawNewsCount, 1),
        model: document.getElementById('model-select').value
    };

    localStorage.setItem('sentirade_settings', JSON.stringify(currentSettings));
    notifyUser('Configuration saved and applied.', 'success');
}

// Set current date
currentDateEl.innerText = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

// Initialize Settings
loadSettings();

// --- Error Handling & Notifications ---

function notifyUser(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;

    let icon = '';
    switch (type) {
        case 'error':
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
            break;
        case 'warning':
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
            break;
        case 'success':
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
            break;
        case 'info':
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
            break;
    }

    notification.innerHTML = `<span class="notification-icon">${icon}</span> <span>${message}</span>`;
    notificationContainer.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 500);
    }, duration);
}

async function fetchWithTimeout(resource, options = {}) {
    const { timeout = 15000 } = options;

    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(resource, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(id);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const err = new Error(errorData.detail || `Server responded with ${response.status}: ${response.statusText}`);
            err.status = response.status; // Attach status code
            throw err;
        }

        return response;
    } catch (error) {
        clearTimeout(id);
        if (error.name === 'AbortError') {
            throw new Error('Analysis timed out. The engine is taking longer than expected.');
        }
        throw error;
    }
}

// --- Backend Status Monitoring ---

if (window.electronAPI && window.electronAPI.onBackendStatus) {
    window.electronAPI.onBackendStatus((data) => {
        console.log('Backend Status Update:', data);

        switch (data.status) {
            case 'connected':
                statusDot.className = 'pulse green';
                statusText.innerText = 'Backend Online';
                break;
            case 'disconnected':
                statusDot.className = 'pulse red';
                statusText.innerText = 'Backend Offline';
                notifyUser('Backend offline. Attempting to restart...', 'warning');
                break;
            case 'reconnecting':
                statusDot.className = 'pulse orange';
                statusText.innerText = 'Connecting...';
                break;
            case 'error':
                statusDot.className = 'pulse red';
                statusText.innerText = 'Backend Error';
                notifyUser('Backend encounterted a critical error.', 'error');
                break;
        }
    });
}

// --- UI Helpers ---

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
        return 0;
    }

    // Deduplication by title + text cleaning
    const processed = [];
    const seen = new Set();

    news.forEach(n => {
        let cleanText = n.headline
            .replace(/^\s*[\.\,\-]\s*/, '') // Remove dots/commas at start
            .trim();

        if (!seen.has(cleanText.toLowerCase()) && cleanText.length > 5) {
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

    return processed.length;
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

    const reasoningCard = document.getElementById('reasoning-summary-card');
    if (reasoningCard) reasoningCard.style.display = 'none';
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
        const newsRes = await fetchWithTimeout(`${API_URL}/news/${ticker}?force=${force}&n_results=${currentSettings.newsCount}`);
        const newsData = await newsRes.json();
        const shownCount = updateNews(newsData.news);
        addLog(`Found ${newsData.news.length} news items (${shownCount} unique displayed).`, 'result');

        // Now run the full agent
        addLog(`Starting Agent ReAct loop (Max Iterations: ${currentSettings.maxIter})...`, 'thinking');
        const res = await fetchWithTimeout(`${API_URL}/signal/${ticker}?max_iter=${currentSettings.maxIter}&n_results=${currentSettings.newsCount}`, {
            method: 'GET',
            headers: {
                'X-Groq-API-Key': currentSettings.apiKey,
                'X-Model-Name': currentSettings.model
            },
            timeout: 60000
        });
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

            if (signal) {
                displaySignal.innerText = signal.signal.toUpperCase();
                displaySignal.className = `main-signal ${signal.signal.toLowerCase()}`;

                confidenceFill.style.width = `${(signal.confidence || 0) * 100}%`;
                confidenceValue.innerText = `${Math.round((signal.confidence || 0) * 100)}%`;

                sentimentText.innerText = signal.sentiment || 'Neutral';
                sentimentText.style.color = signal.sentiment === 'bullish' ? '#10b981' : (signal.sentiment === 'bearish' ? '#ef4444' : '#f3f4f6');

                addLog(`Final Signal: ${signal.signal.toUpperCase()} (${Math.round((signal.confidence || 0) * 100)}% confidence).`, 'result');
                if (signal.reasoning) {
                    addLog(`Reasoning: ${signal.reasoning}`, 'result');
                    // Show final reasoning card
                    const reasoningCard = document.getElementById('reasoning-summary-card');
                    const reasoningSummary = document.getElementById('reasoning-summary');
                    if (reasoningCard && reasoningSummary) {
                        reasoningSummary.innerText = signal.reasoning;
                        reasoningCard.style.display = 'block';
                    }
                }
            } else {
                displaySignal.innerText = 'NEUTRAL';
                displaySignal.className = 'main-signal hold';
                addLog('Warning: Agent completed without a definitive signal. Defaulting to Neutral.', 'system');
            }

            if (regime) {
                regimeText.innerText = regime.regime_name || `Regime ${regime.regime_id}`;
                regimeText.style.color = '#a78bfa';
            } else {
                regimeText.innerText = 'Unknown';
            }

            // Populate Benchmarks
            const benchContainer = document.getElementById('benchmark-stats-container');
            if (data.benchmarks && data.ticker_metrics) {
                if (benchContainer) benchContainer.style.display = 'flex';

                // RSI
                const rsiVal = data.ticker_metrics.rsi;
                const rsiMean = data.benchmarks.rsi_mean;
                const rsiDiff = rsiVal - rsiMean;
                const rsiElem = document.querySelector('#bench-rsi .bench-value');
                const rsiDiffElem = document.querySelector('#bench-rsi .bench-diff');

                if (rsiElem) rsiElem.innerText = Math.round(rsiVal);
                if (rsiDiffElem) {
                    rsiDiffElem.innerText = `${rsiDiff >= 0 ? '+' : ''}${Math.round(rsiDiff)}`;
                    rsiDiffElem.className = `bench-diff ${rsiDiff > 5 ? 'positive' : (rsiDiff < -5 ? 'negative' : 'neutral')}`;
                }

                // Volatility
                const volVal = data.ticker_metrics.volatility;
                const volMean = data.benchmarks.volatility_mean;
                const volDiff = ((volVal - volMean) / volMean) * 100;
                const volElem = document.querySelector('#bench-vol .bench-value');
                const volDiffElem = document.querySelector('#bench-vol .bench-diff');

                if (volElem) volElem.innerText = volVal.toFixed(3);
                if (volDiffElem) {
                    volDiffElem.innerText = `${volDiff >= 0 ? '+' : ''}${Math.round(volDiff)}%`;
                    volDiffElem.className = `bench-diff ${volDiff < -10 ? 'positive' : (volDiff > 10 ? 'negative' : 'neutral')}`;
                }
            } else {
                if (benchContainer) benchContainer.style.display = 'none';
            }

            agentStatus.innerText = 'IDLE';
            agentStatus.style.borderColor = 'rgba(255,255,255,0.08)';
            analyzeBtn.disabled = false;

            notifyUser(`Analysis for ${ticker} completed.`, 'success');
        }, totalDelay);

    } catch (err) {
        console.error(err);
        addLog(`Error: ${err.message}`, 'system');

        // High-fidelity error handling
        if (err.status === 401 || err.message.includes('API Key')) {
            notifyUser('Please check your API key in Settings.', 'error');
            // Flash the settings tab
            const settingsTab = document.querySelector('[data-tab="settings"]');
            if (settingsTab) {
                settingsTab.classList.add('pulse-error');
                setTimeout(() => settingsTab.classList.remove('pulse-error'), 4000);
            }
        } else if (err.status === 429) {
            notifyUser('Rate limit exceeded. Waiting for cool-down...', 'warn');
        } else {
            notifyUser(err.message, 'error');
        }

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
        const res = await fetchWithTimeout(`${API_URL}/metrics`);
        const data = await res.json();

        if (data.error) {
            container.innerHTML = `<div class="news-placeholder">${data.error}</div>`;
            return;
        }

        container.innerHTML = ''; // Clear previous

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
        container.innerHTML = `<div class="news-placeholder">Error loading metrics: ${err.message}</div>`;
        notifyUser(`Failed to load metrics: ${err.message}`, 'error');
    }
}

// Run Backtest
const runBacktestBtn = document.getElementById('run-backtest-btn');
runBacktestBtn.addEventListener('click', async () => {
    runBacktestBtn.disabled = true;
    runBacktestBtn.innerText = 'Simulating...';

    try {
        const res = await fetchWithTimeout(`${API_URL}/backtest`, { method: 'POST', timeout: 60000 });
        const data = await res.json();

        if (data.status === 'success') {
            await loadMetrics();
            notifyUser('Simulation completed successfully!', 'success');
        } else {
            notifyUser('Error running simulation: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (err) {
        notifyUser('Error: ' + err.message, 'error');
    } finally {
        runBacktestBtn.disabled = false;
        runBacktestBtn.innerText = 'Run Simulation';
    }
});

// Initialize Uptime Tracking
const startTime = new Date();
function updateUptime() {
    const now = new Date();
    const diff = Math.floor((now - startTime) / 1000);
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    const el = document.getElementById('uptime-val');
    if (el) el.innerText = `${mins}m ${secs}s`;
}

setInterval(updateUptime, 1000);

// Settings Save Event
const saveBtn = document.getElementById('save-settings-btn');
if (saveBtn) saveBtn.addEventListener('click', saveSettings);

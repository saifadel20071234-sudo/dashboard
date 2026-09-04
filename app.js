// ============================================================
// PowerStep Grid — Dashboard JavaScript
// ============================================================

const MOCK_MODE = true; // 1. MOCK DATA GENERATOR FLAG
const API = window.location.origin;

// ------------------------------------------------------------
// Chart.js — Energy Chart
// ------------------------------------------------------------
let chart;

function initChart() {
  const ctx = document.getElementById('energyChart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'مولَّدة (Gen)', data: [], borderColor: '#00ffcc', backgroundColor: 'rgba(0,255,204,.15)', fill: true, tension: .4, pointRadius: 0, borderWidth: 2 },
        { label: 'مستهلَكة (Con)', data: [], borderColor: '#ffaa00', backgroundColor: 'rgba(255,170,0,.1)', fill: true, tension: .4, pointRadius: 0, borderWidth: 2, borderDash: [5, 3] },
      ]
    },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { position: 'top', rtl: true, labels: { font: { family: 'Cairo', size: 11 }, color: '#e2e8f0' } } },
      scales: {
        x: { ticks: { font: { family: 'Consolas', size: 10 }, color: '#94a3b8', maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { font: { family: 'Consolas', size: 10 }, color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

// ------------------------------------------------------------
// Gauge Helper
// ------------------------------------------------------------
function setGauge(id, pct, valEl, val) {
  const gauge = document.getElementById(id);
  const valueElement = document.getElementById(valEl);
  if (gauge) gauge.style.setProperty('--pct', Math.min(pct, 100));
  if (valueElement) valueElement.textContent = val;
}

// ------------------------------------------------------------
// Load Badge Class
// ------------------------------------------------------------
function loadBadgeClass(state) {
  if (state.startsWith('ON')) return 'on';
  if (state.startsWith('Standby')) return 'wait';
  return 'off';
}

// ------------------------------------------------------------
// Update Live Data (called on each WebSocket message or by mock)
// ------------------------------------------------------------
function updateLive(d) {
  try {
    // Day & Time
    if (document.getElementById('dayNum')) document.getElementById('dayNum').textContent = d.day;
    if (document.getElementById('simTime')) document.getElementById('simTime').textContent = d.sim_time;

    // Gauges
    if (d.generation_w !== undefined) {
      setGauge('gaugeGen', d.generation_w * 10, 'genVal', d.generation_w.toFixed(1));
    }
    if (d.forecast_w !== undefined && document.getElementById('forecastVal')) {
      document.getElementById('forecastVal').textContent = d.forecast_w.toFixed(1);
    }

    // CO2 Savings & Generated Wh
    if (d.co2_saved_grams !== undefined) {
      if (document.getElementById('co2SavedVal')) document.getElementById('co2SavedVal').textContent = d.co2_saved_grams.toFixed(2);
      if (document.getElementById('totalSavedCO2')) document.getElementById('totalSavedCO2').textContent = d.co2_saved_grams.toFixed(2);
    } else if (d.cumulative_gen_wh !== undefined) {
      const co2Grams = d.cumulative_gen_wh * 0.4;
      if (document.getElementById('co2SavedVal')) document.getElementById('co2SavedVal').textContent = co2Grams.toFixed(2);
      if (document.getElementById('totalSavedCO2')) document.getElementById('totalSavedCO2').textContent = co2Grams.toFixed(2);
    }

    if (d.cumulative_gen_wh !== undefined && document.getElementById('totalGenWh')) {
      document.getElementById('totalGenWh').textContent = d.cumulative_gen_wh.toFixed(4);
    }
    if (d.cumulative_con_wh !== undefined && document.getElementById('totalConWh')) {
      document.getElementById('totalConWh').textContent = d.cumulative_con_wh.toFixed(4);
    }

    if (d.consumption_w !== undefined) {
      setGauge('gaugeCon', d.consumption_w * 10, 'conVal', d.consumption_w.toFixed(1));
    }
    if (d.self_sufficiency_pct !== undefined) {
      setGauge('gaugeSelf', d.self_sufficiency_pct, 'selfVal', Math.round(d.self_sufficiency_pct));
    }

    // Battery
    if (d.storage_soc_pct !== undefined) {
      const battFill = document.getElementById('battFill');
      const battVal = document.getElementById('battVal');
      if (battFill) battFill.style.width = d.storage_soc_pct + '%';
      if (battVal) battVal.textContent = Math.round(d.storage_soc_pct);
    }

    // Power Source
    const sourceTag = document.getElementById('sourceTag');
    const sourceLabel = document.getElementById('sourceLabel');
    if (sourceTag && sourceLabel && d.power_source) {
      if (d.power_source === 'harvested') {
        sourceTag.classList.remove('grid');
        sourceLabel.textContent = 'طاقة نظيفة (Harvested)';
      } else {
        sourceTag.classList.add('grid');
        sourceLabel.textContent = 'شبكة الطوارئ (Grid)';
      }
    }

    // Footfall
    if (d.footfall !== undefined && document.getElementById('footfallNow')) {
      document.getElementById('footfallNow').textContent = Math.round(d.footfall);
    }

    // Loads
    const loadsList = document.getElementById('loadsList');
    if (loadsList && d.loads) {
      loadsList.innerHTML = '';
      Object.values(d.loads).forEach(l => {
        const row = document.createElement('div');
        row.className = 'row';
        row.innerHTML = `<span>${l.name}</span><span class="badge ${loadBadgeClass(l.state)}">${l.state}</span>`;
        loadsList.appendChild(row);
      });
    }

    // Alerts
    const alertsList = document.getElementById('alertsList');
    if (alertsList && d.alerts) {
      if (d.alerts.length === 0) {
        alertsList.innerHTML = '<div class="alerts-empty">النظام مستقر — لا توجد شذوذ (Anomalies)</div>';
        window.lastAlertCount = 0;
      } else {
        alertsList.innerHTML = '';
        d.alerts.forEach(a => {
          const row = document.createElement('div');
          row.className = 'alert';
          row.innerHTML = `<span class="dot ${a.level}"></span><span>${a.text}</span>`;
          alertsList.appendChild(row);
        });
        
        // Play sound and show toast if new alerts appeared
        if (window.lastAlertCount === undefined) window.lastAlertCount = 0;
        if (d.alerts.length > window.lastAlertCount) {
          playAlertSound();
          const newAlerts = d.alerts.slice(window.lastAlertCount);
          newAlerts.forEach(a => showToast(a.text, a.level));
        }
        window.lastAlertCount = d.alerts.length;
      }
    }

    // Tiles Heatmap
    const tilesGrid = document.getElementById('tilesGrid');
    if (tilesGrid && d.tiles) {
      tilesGrid.innerHTML = '';
      d.tiles.forEach(t => {
        const chip = document.createElement('div');
        chip.className = 'tile-chip';

        if (t.stepped_on) {
          chip.classList.add('stepped');
        }
        if (t.efficiency_pct < 80) {
          chip.classList.add('faulty');
        }

        chip.innerHTML = `<span>Tile ${t.id}</span><span class="eff">${Math.round(t.efficiency_pct)}%</span>`;
        tilesGrid.appendChild(chip);
      });
    }

    // NEW FIELDS
    if (d.voltage_v !== undefined && document.getElementById('voltageVal')) {
      document.getElementById('voltageVal').textContent = d.voltage_v.toFixed(1);
    }
    if (d.current_a !== undefined && document.getElementById('currentVal')) {
      document.getElementById('currentVal').textContent = d.current_a.toFixed(1);
    }
    if (d.system_uptime !== undefined && document.getElementById('uptimeVal')) {
      document.getElementById('uptimeVal').textContent = d.system_uptime;
    }
    if (d.cost_saved !== undefined && document.getElementById('costSavedVal')) {
      document.getElementById('costSavedVal').textContent = d.cost_saved.toFixed(2);
    }
    if (d.exported_wh !== undefined && document.getElementById('exportedWhVal')) {
      document.getElementById('exportedWhVal').textContent = d.exported_wh.toFixed(1);
    }
    if (d.battery_temperature !== undefined && document.getElementById('battTempVal')) {
      document.getElementById('battTempVal').textContent = d.battery_temperature.toFixed(1);
    }
    if (d.ai_status !== undefined) {
      const fStatus = document.getElementById('aiStatusForecast');
      if (fStatus) {
        if (d.ai_status.forecast_model === 'Online') fStatus.classList.remove('offline');
        else fStatus.classList.add('offline');
      }
      const aStatus = document.getElementById('aiStatusAnomaly');
      if (aStatus) {
        if (d.ai_status.anomaly_model === 'Online') aStatus.classList.remove('offline');
        else aStatus.classList.add('offline');
      }
    }

  } catch (e) {
    console.error("Connection error:", e);
  }
}

// ------------------------------------------------------------
// Refresh History (for charts)
// ------------------------------------------------------------
async function refreshHistory() {
  try {
    const r = await fetch(API + "/api/history");
    const d = await r.json();
    if (!chart) return;

    chart.data.labels = d.t.map(h => {
      const hh = Math.floor(h);
      const mm = Math.round((h - hh) * 60);
      return `${hh}:${mm.toString().padStart(2, '0')}`;
    });
    chart.data.datasets[0].data = d.gen_wh;
    chart.data.datasets[1].data = d.con_wh;
    chart.update();

    const strip = document.getElementById('footfallStrip');
    if (strip) {
      strip.innerHTML = '';
      const recent = d.footfall.slice(-40);
      const max = Math.max(...recent, 1);
      recent.forEach(v => {
        const bar = document.createElement('div');
        bar.className = 'bar';
        bar.style.height = Math.max(4, (v / max) * 50) + 'px';
        strip.appendChild(bar);
      });
    }
  } catch (e) { /* silent */ }
}

// ------------------------------------------------------------
// Sound Effects
// ------------------------------------------------------------
const AudioContext = window.AudioContext || window.webkitAudioContext;
const audioCtx = new AudioContext();

function playClickSound() {
  if (audioCtx.state === 'suspended') audioCtx.resume();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = 'sine';
  osc.frequency.setValueAtTime(600, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(300, audioCtx.currentTime + 0.05);
  gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.05);
  osc.start();
  osc.stop(audioCtx.currentTime + 0.05);
}

function playAlertSound() {
  if (audioCtx.state === 'suspended') audioCtx.resume();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = 'square';
  osc.frequency.setValueAtTime(400, audioCtx.currentTime);
  osc.frequency.setValueAtTime(600, audioCtx.currentTime + 0.1);
  gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
  gain.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.3);
  osc.start();
  osc.stop(audioCtx.currentTime + 0.3);
}

// ------------------------------------------------------------
// Real Clock & Loading Screen & Hover Sounds
// ------------------------------------------------------------
setInterval(() => {
  const now = new Date();
  const realClock = document.getElementById('realClock');
  if (realClock) realClock.textContent = now.toLocaleTimeString('en-US', { hour12: false });
}, 1000);

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('a, button').forEach(el => {
    el.addEventListener('mouseenter', playClickSound);
  });
  
  // 3. LOADING SCREEN: After DOMContentLoaded, wait 2.5s then add 'hidden'
  setTimeout(() => {
    const loader = document.querySelector('.loading-overlay');
    if (loader) {
      loader.classList.add('hidden');
    }
  }, 2500);
});

// ------------------------------------------------------------
// Connection & Toasts Status Helpers
// ------------------------------------------------------------
function setConnStatus(online) {
  const badge = document.getElementById('connectionBadge');
  const text = document.getElementById('connText');
  if(!badge || !text) return;
  if(online) {
    badge.className = 'conn-badge online';
    text.textContent = 'SYSTEM ONLINE';
  } else {
    badge.className = 'conn-badge offline';
    text.textContent = 'CONNECTION LOST';
  }
}

function showToast(message, level) {
  const container = document.getElementById('toastContainer');
  if(!container) return;
  const toast = document.createElement('div');
  toast.className = `toast-msg ${level}`;
  
  // Icon based on level
  let icon = '⚠️';
  if (level === 'danger') icon = '🚨';
  if (level === 'info') icon = 'ℹ️';
  
  toast.innerHTML = `<span style="font-size:1.2rem;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  
  // Remove after 5 seconds (matches the CSS animation)
  setTimeout(() => {
    if(toast.parentElement) toast.remove();
  }, 5000);
}

// ------------------------------------------------------------
// WebSocket Connection
// ------------------------------------------------------------
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = protocol + '//' + window.location.host + '/ws/live';
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setConnStatus(true);
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateLive(data);
  };

  ws.onclose = () => {
    setConnStatus(false);
    console.log("WebSocket disconnected. Retrying in 2 seconds...");
    setTimeout(initWebSocket, 2000);
  };
}

// ------------------------------------------------------------
// Initialize
// ------------------------------------------------------------
if (MOCK_MODE) {
  console.log("Running in MOCK_MODE");
  setConnStatus(true);
  initChart();
  
  // Start with some history and footfall
  const mockHist = generateMockHistory();
  chart.data.labels = mockHist.labels;
  chart.data.datasets[0].data = mockHist.gen;
  chart.data.datasets[1].data = mockHist.con;
  chart.update();
  
  const strip = document.getElementById('footfallStrip');
  mockHist.foot.forEach(v => {
    const bar = document.createElement('div');
    bar.className = 'bar';
    bar.style.height = Math.max(4, (v / 45) * 50) + 'px';
    strip.appendChild(bar);
  });
  
  setInterval(generateAndDispatchMockData, 1500);
} else {
  initChart();
  initWebSocket();
  refreshHistory();
  setInterval(refreshHistory, 4000);
}

// ------------------------------------------------------------
// Mock Data Generator
// ------------------------------------------------------------
let mockSimTime = 0;
let mockDay = 1;
let mockUptime = 3600;

function generateMockData() {
  mockSimTime += 0.2;
  if (mockSimTime >= 24) { mockSimTime = 0; mockDay++; }
  const hour = Math.floor(mockSimTime);
  const min = Math.floor((mockSimTime - hour) * 60);
  const timeStr = `${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;

  const noonDist = Math.abs(12 - mockSimTime);
  const generation_w = Math.max(0, 500 - (noonDist * noonDist * 5)) + Math.random() * 20;
  const consumption_w = generation_w * (0.4 + Math.random() * 0.2); 
  const storage_soc_pct = 50 + Math.sin(mockSimTime / 24 * Math.PI) * 30 + Math.random() * 2;
  const footfall = 5 + Math.random() * 40;

  const tiles = Array.from({length: 16}, (_, i) => ({
    id: i + 1,
    stepped_on: Math.random() > 0.8,
    efficiency_pct: i === 4 ? 72 + Math.random() * 2 : 95 + Math.random() * 4 // Tile 5 low efficiency
  }));

  const alerts = [];
  if (Math.random() > 0.9) {
    alerts.push({ level: 'warning', text: 'Anomaly detected in load pattern.' });
  }

  mockUptime += 1.5;

  const cumulative_gen_wh = 1234.5 + mockSimTime * 10;

  const data = {
    day: `اليوم ${mockDay}`,
    sim_time: timeStr,
    generation_w,
    forecast_w: generation_w * 1.1,
    cumulative_gen_wh,
    cumulative_con_wh: 800 + mockSimTime * 5,
    consumption_w,
    self_sufficiency_pct: Math.min(100, (generation_w / (consumption_w || 1)) * 100),
    storage_soc_pct,
    power_source: generation_w > consumption_w ? 'harvested' : 'grid',
    footfall,
    loads: {
      load1: { name: 'Lighting', state: 'ON (Active)' },
      load2: { name: 'HVAC', state: 'Standby' },
      load3: { name: 'Servers', state: 'ON (Active)' }
    },
    alerts,
    tiles,
    voltage_v: 11.5 + Math.random() * 1.3,
    current_a: 0.5 + Math.random() * 2,
    system_uptime: Math.floor(mockUptime),
    ai_status: { forecast_model: 'Online', anomaly_model: 'Online' },
    cost_saved: cumulative_gen_wh * 0.15,
    co2_saved_grams: cumulative_gen_wh * 0.4,
    exported_wh: 100 + mockSimTime * 2,
    battery_temperature: 28 + Math.random() * 10
  };

  updateLive(data);
}

function initMockHistory() {
  if (!chart) return;
  const t = [];
  const gen_wh = [];
  const con_wh = [];
  const footfall = [];
  for (let i = 0; i < 24; i++) {
    t.push(i);
    const noonDist = Math.abs(12 - i);
    const gen = Math.max(0, 500 - (noonDist * noonDist * 5)) + Math.random() * 20;
    gen_wh.push(gen);
    con_wh.push(gen * (0.4 + Math.random() * 0.2));
    footfall.push(5 + Math.random() * 40);
  }
  chart.data.labels = t.map(h => {
    const hh = Math.floor(h);
    const mm = Math.round((h - hh) * 60);
    return `${hh}:${mm.toString().padStart(2, '0')}`;
  });
  chart.data.datasets[0].data = gen_wh;
  chart.data.datasets[1].data = con_wh;
  chart.update();

  const strip = document.getElementById('footfallStrip');
  if (strip) {
    strip.innerHTML = '';
    const recent = footfall.slice(-40);
    const max = Math.max(...recent, 1);
    recent.forEach(v => {
      const bar = document.createElement('div');
      bar.className = 'bar';
      bar.style.height = Math.max(4, (v / max) * 50) + 'px';
      strip.appendChild(bar);
    });
  }
}

// ------------------------------------------------------------
// Initialize
// ------------------------------------------------------------
initChart();

if (MOCK_MODE) {
  initMockHistory();
  setInterval(generateMockData, 1500);
} else {
  initWebSocket();
  refreshHistory();
  setInterval(refreshHistory, 4000);
}

// ============================================================
// PowerStep Grid — Dashboard JavaScript
// ============================================================

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
  document.getElementById(id).style.setProperty('--pct', Math.min(pct, 100));
  document.getElementById(valEl).textContent = val;
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
// Update Live Data (called on each WebSocket message)
// ------------------------------------------------------------
function updateLive(d) {
  try {
    // Day & Time
    document.getElementById('dayNum').textContent = d.day;
    document.getElementById('simTime').textContent = d.sim_time;

    // Gauges
    setGauge('gaugeGen', d.generation_w * 10, 'genVal', d.generation_w.toFixed(1));
    if (d.forecast_w !== undefined) {
      document.getElementById('forecastVal').textContent = d.forecast_w.toFixed(1);
    }

    // CO2 Savings
    if (d.cumulative_gen_wh !== undefined) {
      const co2Grams = d.cumulative_gen_wh * 0.4;
      document.getElementById('co2SavedVal').textContent = co2Grams.toFixed(2);

      // Energy counter banner
      document.getElementById('totalGenWh').textContent = d.cumulative_gen_wh.toFixed(4);
      document.getElementById('totalSavedCO2').textContent = co2Grams.toFixed(2);
    }
    if (d.cumulative_con_wh !== undefined) {
      document.getElementById('totalConWh').textContent = d.cumulative_con_wh.toFixed(4);
    }

    setGauge('gaugeCon', d.consumption_w * 10, 'conVal', d.consumption_w.toFixed(1));
    setGauge('gaugeSelf', d.self_sufficiency_pct, 'selfVal', Math.round(d.self_sufficiency_pct));

    // Battery
    document.getElementById('battFill').style.width = d.storage_soc_pct + '%';
    document.getElementById('battVal').textContent = Math.round(d.storage_soc_pct);

    // Power Source
    const sourceTag = document.getElementById('sourceTag');
    const sourceLabel = document.getElementById('sourceLabel');
    if (d.power_source === 'harvested') {
      sourceTag.classList.remove('grid');
      sourceLabel.textContent = 'طاقة نظيفة (Harvested)';
    } else {
      sourceTag.classList.add('grid');
      sourceLabel.textContent = 'شبكة الطوارئ (Grid)';
    }

    // Footfall
    document.getElementById('footfallNow').textContent = Math.round(d.footfall);

    // Loads
    const loadsList = document.getElementById('loadsList');
    loadsList.innerHTML = '';
    Object.values(d.loads).forEach(l => {
      const row = document.createElement('div');
      row.className = 'row';
      row.innerHTML = `<span>${l.name}</span><span class="badge ${loadBadgeClass(l.state)}">${l.state}</span>`;
      loadsList.appendChild(row);
    });

    // Alerts
    const alertsList = document.getElementById('alertsList');
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
      // Play sound if new alerts appeared
      if (window.lastAlertCount === undefined) window.lastAlertCount = 0;
      if (d.alerts.length > window.lastAlertCount) {
        playAlertSound();
      }
      window.lastAlertCount = d.alerts.length;
    }

    // Tiles Heatmap
    const tilesGrid = document.getElementById('tilesGrid');
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
    strip.innerHTML = '';
    const recent = d.footfall.slice(-40);
    const max = Math.max(...recent, 1);
    recent.forEach(v => {
      const bar = document.createElement('div');
      bar.className = 'bar';
      bar.style.height = Math.max(4, (v / max) * 50) + 'px';
      strip.appendChild(bar);
    });
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
// Real Clock
// ------------------------------------------------------------
setInterval(() => {
  const now = new Date();
  document.getElementById('realClock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
}, 1000);

// ------------------------------------------------------------
// Hover Sound Effects
// ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('a, button').forEach(el => {
    el.addEventListener('mouseenter', playClickSound);
  });
});

// ------------------------------------------------------------
// WebSocket Connection
// ------------------------------------------------------------
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = protocol + '//' + window.location.host + '/ws/live';
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateLive(data);
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected. Retrying in 2 seconds...");
    setTimeout(initWebSocket, 2000);
  };
}

// ------------------------------------------------------------
// Initialize
// ------------------------------------------------------------
initChart();
initWebSocket();
refreshHistory();
setInterval(refreshHistory, 4000);

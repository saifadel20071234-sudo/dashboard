// ============================================================
// PowerStep Grid — Dashboard JavaScript
// ============================================================

const API = 'http://' + window.location.hostname + ':8000';

const _csvLink = document.getElementById('csvLink');
if (_csvLink) _csvLink.href = API + '/api/export/csv';

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
    window.lastLiveData = d;
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
      const soc = Math.round(d.storage_soc_pct);
      if (battFill) {
        battFill.style.width = soc + '%';
        const battLimit = (window.userSettings && window.userSettings.batteryLow) ? window.userSettings.batteryLow : 20;
        if (soc <= battLimit) {
          battFill.style.background = 'var(--red)';
          battFill.style.boxShadow = '0 0 10px var(--red)';
        } else {
          battFill.style.background = 'var(--green)';
          battFill.style.boxShadow = '0 0 10px var(--green)';
        }
      }
      if (battVal) battVal.textContent = soc;
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

    // Corridor Heatmap (16 tiles → two rows around a central wall)
    const rowTop = document.getElementById('corridorRowTop');
    const rowBottom = document.getElementById('corridorRowBottom');
    const corridor = document.getElementById('corridor');
    if (corridor && d.tiles) {
      const tileCount = d.tiles.length;
      const half = Math.ceil(tileCount / 2);
      // top row = tiles 1..half, bottom row = remaining tiles
      const top = d.tiles.slice(0, half);
      const bottom = d.tiles.slice(half, tileCount);

      rowTop.innerHTML = '';
      rowBottom.innerHTML = '';
      top.forEach(t => {
        const chip = document.createElement('div');
        chip.className = 'corridor-tile';
        if (t.stepped_on) chip.classList.add('stepped');
        const effLimit = (window.userSettings && window.userSettings.efficiency) ? window.userSettings.efficiency : 80;
        if (t.efficiency_pct < effLimit) chip.classList.add('faulty');
        chip.innerHTML = `<span class="ct-num">${t.id}</span><span class="ct-eff">${Math.round(t.efficiency_pct)}%</span>`;
        rowTop.appendChild(chip);
      });
      bottom.forEach(t => {
        const chip = document.createElement('div');
        chip.className = 'corridor-tile';
        if (t.stepped_on) chip.classList.add('stepped');
        const effLimit = (window.userSettings && window.userSettings.efficiency) ? window.userSettings.efficiency : 80;
        if (t.efficiency_pct < effLimit) chip.classList.add('faulty');
        chip.innerHTML = `<span class="ct-num">${t.id}</span><span class="ct-eff">${Math.round(t.efficiency_pct)}%</span>`;
        rowBottom.appendChild(chip);
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
  if (!window.userSettings || !window.userSettings.soundEnabled) return;
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
  if (!window.userSettings || !window.userSettings.soundEnabled) return;
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
  if (level === 'success') icon = '✅';
  
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
  const wsUrl = 'ws://' + window.location.hostname + ':8000/ws/live';
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
// Theme & Settings Management
// ------------------------------------------------------------
window.userSettings = { efficiency: 80, batteryLow: 20, soundEnabled: true };

function loadSettings() {
  let saved = null;
  try { saved = localStorage.getItem('powerstep_settings'); } catch(e) { /* ignore */ }
  if (saved) { try { window.userSettings = { ...window.userSettings, ...JSON.parse(saved) }; } catch(e) { /* ignore */ } }
  
  const effInput = document.getElementById('effThreshold');
  const battInput = document.getElementById('battThreshold');
  const soundInput = document.getElementById('soundToggle');
  if(effInput) { effInput.value = window.userSettings.efficiency; document.getElementById('effValDisp').textContent = window.userSettings.efficiency; }
  if(battInput) { battInput.value = window.userSettings.batteryLow; document.getElementById('battValDisp').textContent = window.userSettings.batteryLow; }
  if(soundInput) { soundInput.checked = window.userSettings.soundEnabled; }
}

function saveSettings() {
  const effInput = document.getElementById('effThreshold');
  const battInput = document.getElementById('battThreshold');
  const soundInput = document.getElementById('soundToggle');
  if(effInput && battInput && soundInput) {
    window.userSettings.efficiency = parseInt(effInput.value);
    window.userSettings.batteryLow = parseInt(battInput.value);
    window.userSettings.soundEnabled = soundInput.checked;
    try { localStorage.setItem('powerstep_settings', JSON.stringify(window.userSettings)); } catch(e) { /* ignore */ }
    hideSettingsModal();
    showToast("تم حفظ الإعدادات بنجاح", "success");
    if (window.lastLiveData) updateLive(window.lastLiveData);
  }
}

function resetSettings() {
  window.userSettings = { efficiency: 80, batteryLow: 20, soundEnabled: true };
  try { localStorage.setItem('powerstep_settings', JSON.stringify(window.userSettings)); } catch(e) { /* ignore */ }
  loadSettings();
  showToast("تمت استعادة الإعدادات الافتراضية", "info");
}

function showSettingsModal() { 
  const modal = document.getElementById('settingsModal');
  if(modal) modal.classList.remove('hidden'); 
}
function hideSettingsModal() { 
  const modal = document.getElementById('settingsModal');
  if(modal) modal.classList.add('hidden'); 
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('powerstep_theme', theme); } catch(e) { /* ignore */ }
  const themeBtns = document.querySelectorAll('.theme-toggle-btn');
  themeBtns.forEach(btn => {
    if(btn.id === 'themeToggleBtn') btn.textContent = theme === 'light' ? '☀️' : '🌙';
  });
  
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = theme === 'light' ? '#1e293b' : '#94a3b8';
    Chart.defaults.borderColor = theme === 'light' ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
    [chart, window.energyChart, window.battChart, window.footChart].forEach(c => {
      if (c && c instanceof Chart) c.update();
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Init Theme
  let savedTheme = 'dark';
  try { savedTheme = localStorage.getItem('powerstep_theme') || 'dark'; } catch(e) { /* ignore */ }
  applyTheme(savedTheme);
  
  const themeBtn = document.getElementById('themeToggleBtn');
  if(themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.dataset.theme;
      applyTheme(current === 'light' ? 'dark' : 'light');
    });
  }
  // Init Settings
  loadSettings();

  // Close settings modal when clicking outside it or pressing Escape
  const settingsModal = document.getElementById('settingsModal');
  if(settingsModal) {
    settingsModal.addEventListener('click', (e) => {
      if(e.target === settingsModal) hideSettingsModal();
    });
  }
  document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape') hideSettingsModal();
  });
});

// ------------------------------------------------------------
// Initialize
// ------------------------------------------------------------
initChart();
initWebSocket();
refreshHistory();
setInterval(refreshHistory, 4000);


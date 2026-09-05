// Theme Management
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('powerstep_theme', theme); } catch(e) {}
  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) themeBtn.textContent = theme === 'light' ? '☀️' : '🌙';
}

document.addEventListener('DOMContentLoaded', () => {
  let savedTheme = 'dark';
  try { savedTheme = localStorage.getItem('powerstep_theme') || 'dark'; } catch(e) {}
  applyTheme(savedTheme);

  const themeBtn = document.getElementById('themeToggleBtn');
  if(themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.dataset.theme;
      applyTheme(current === 'light' ? 'dark' : 'light');
    });
  }

  // Modal close handlers
  const deviceModal = document.getElementById('deviceModal');
  if(deviceModal) {
    deviceModal.addEventListener('click', (e) => {
      if(e.target === deviceModal) hideAddDeviceModal();
    });
  }
  document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape') hideAddDeviceModal();
  });

  renderDevices();
});

// Device Management CRUD
let devices = [];
try {
  devices = JSON.parse(localStorage.getItem('powerstep_devices') || '[]');
} catch(e) { /* ignore */ }

if(devices.length === 0) {
  devices = [
    { id: 'node-001', name: 'المبنى الرئيسي', location: 'الفرع الأول', status: 'online', tiles_count: 16, generation_w: 5.2, battery_pct: 78 }
  ];
  saveDevicesLocally();
}

function saveDevicesLocally() {
  try { localStorage.setItem('powerstep_devices', JSON.stringify(devices)); } catch(e) {}
  renderDevices();
}

function renderDevices() {
  const container = document.getElementById('devicesContainer');
  if (!container) return;
  container.innerHTML = '';
  
  if(devices.length === 0) {
    container.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding: 40px; color:var(--muted); background:var(--card); border:1px solid var(--line); border-radius:12px;">لا توجد أجهزة مضافة حالياً. انقر على إضافة جهاز جديد.</div>';
    return;
  }

  devices.forEach(dev => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.position = 'relative';
    card.style.transition = 'transform 0.3s ease';
    card.onmouseover = () => card.style.transform = 'translateY(-3px)';
    card.onmouseout = () => card.style.transform = 'translateY(0)';
    
    const statusColor = dev.status === 'online' ? 'var(--green)' : 'var(--red)';
    const statusText = dev.status === 'online' ? 'متصل' : 'مفصول';
    
    card.innerHTML = `
      <div style="position:absolute; top:18px; left:18px; display:flex; align-items:center; gap:5px; font-size:0.7rem; color:var(--muted);">
        <div style="width:8px; height:8px; border-radius:50%; background:${statusColor}; box-shadow:0 0 8px ${statusColor};"></div>
        ${statusText}
      </div>
      <h3 style="margin-top:0; margin-bottom:5px; color:var(--ink); font-size:1.1rem;">${dev.name}</h3>
      <p style="margin:0 0 15px 0; font-size:0.8rem; color:var(--muted);">📍 ${dev.location}</p>
      
      <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:0.9rem; padding:8px; background:rgba(0,0,0,0.1); border-radius:6px;">
        <span style="color:var(--muted);">عدد البلاطات:</span>
        <span style="color:var(--blue); font-weight:bold;">${dev.tiles_count}</span>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:0.9rem; padding:8px; background:rgba(0,0,0,0.1); border-radius:6px;">
        <span style="color:var(--muted);">توليد الطاقة:</span>
        <span style="color:var(--orange); font-weight:bold;">${dev.generation_w} W</span>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:20px; font-size:0.9rem; padding:8px; background:rgba(0,0,0,0.1); border-radius:6px;">
        <span style="color:var(--muted);">البطارية:</span>
        <span style="color:var(--green); font-weight:bold;">${dev.battery_pct}%</span>
      </div>
      
      <button onclick="deleteDevice('${dev.id}')" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--danger); background:transparent; color:var(--red); cursor:pointer; font-weight:bold; transition:all 0.3s;" onmouseover="this.style.background='var(--danger)'; this.style.color='#fff'" onmouseout="this.style.background='transparent'; this.style.color='var(--red)'">🗑️ حذف الجهاز</button>
    `;
    container.appendChild(card);
  });
}

function showAddDeviceModal() { document.getElementById('deviceModal').classList.remove('hidden'); }
function hideAddDeviceModal() { document.getElementById('deviceModal').classList.add('hidden'); }

function saveNewDevice() {
  const name = document.getElementById('devName').value.trim();
  const loc = document.getElementById('devLocation').value.trim();
  const tiles = parseInt(document.getElementById('devTiles').value);
  
  if(!name || !loc) {
    alert("يرجى إدخال اسم المبنى والموقع!");
    return;
  }
  
  const newDev = {
    id: 'node-' + Math.random().toString(36).substr(2, 9),
    name: name,
    location: loc,
    status: 'online',
    tiles_count: tiles || 16,
    generation_w: 0,
    battery_pct: 0
  };
  
  devices.push(newDev);
  saveDevicesLocally();
  hideAddDeviceModal();
  
  document.getElementById('devName').value = '';
  document.getElementById('devLocation').value = '';
  document.getElementById('devTiles').value = '16';
}

function deleteDevice(id) {
  if(confirm('هل أنت متأكد من حذف هذا الجهاز من الشبكة؟')) {
    devices = devices.filter(d => d.id !== id);
    saveDevicesLocally();
  }
}

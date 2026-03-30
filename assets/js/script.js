/**
 * script.js — Lógica del Panel Administrativo de RenovaBot.
 * SPA con 6 secciones: Dashboard, Players, Misiones, Mensajes, Marketing, Eventos.
 */

/* ══════════════════════════════════════════════════════════
   AUTENTICACIÓN
══════════════════════════════════════════════════════════ */
firebase.auth().onAuthStateChanged(user => {
  if (!user) {
    window.location.href = '/';
    return;
  }
  document.getElementById('admin-email-display').textContent = user.displayName || user.email;
  initAdminPanel();
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  await firebase.auth().signOut();
  window.location.href = '/';
});

/* ══════════════════════════════════════════════════════════
   RELOJ
══════════════════════════════════════════════════════════ */
function updateClock() {
  const el = document.getElementById('topbar-time');
  if (el) {
    el.textContent = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
}
setInterval(updateClock, 1000);
updateClock();

/* ══════════════════════════════════════════════════════════
   NAVEGACIÓN
══════════════════════════════════════════════════════════ */
const SECTIONS = ['dashboard', 'players', 'misiones', 'mensajes', 'marketing', 'eventos'];
const SECTION_TITLES = {
  dashboard: '📊 Dashboard General',
  players:   '👥 Players',
  misiones:  '🎯 Misiones',
  mensajes:  '💬 Mensajes',
  marketing: '📣 Marketing',
  eventos:   '📋 Historial de Eventos',
};

function loadSection(name) {
  SECTIONS.forEach(s => {
    const sec = document.getElementById(`section-${s}`);
    const nav = document.getElementById(`nav-${s}`);
    if (s === name) {
      sec.classList.remove('hidden');
      sec.classList.add('active');
      nav.classList.add('active');
    } else {
      sec.classList.add('hidden');
      sec.classList.remove('active');
      nav.classList.remove('active');
    }
  });
  document.getElementById('topbar-title').textContent = SECTION_TITLES[name] || name;

  if (name === 'dashboard') loadDashboard();
  if (name === 'players')   loadPlayers();
  if (name === 'misiones')  loadMissions();
  if (name === 'mensajes')  loadMensajes();
  if (name === 'marketing') loadMarketing();
  if (name === 'eventos')   loadEvents();
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    loadSection(item.dataset.section);
  });
});

document.getElementById('sidebar-toggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});

/* ══════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════ */
function initAdminPanel() {
  loadDashboard();
}

/* ══════════════════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════════════════ */
async function loadDashboard() {
  try {
    const [statsRes, usersRes, eventsRes] = await Promise.all([
      fetchApi('/api/stats'),
      fetchApi('/api/users'),
      fetchApi('/api/events?limit=8')
    ]);

    if (statsRes.ok) {
      const d = statsRes.data;
      document.getElementById('kpi-total-val').textContent      = d.total_usuarios;
      document.getElementById('kpi-activos-val').textContent    = d.activos;
      document.getElementById('kpi-completados-val').textContent= d.completados;
      document.getElementById('kpi-pausados-val').textContent   = d.pausados;
      document.getElementById('kpi-racha-val').textContent      = d.racha_maxima;
      document.getElementById('kpi-xp-val').textContent         = d.xp_promedio || '—';
    }
    if (usersRes.ok) {
      const sorted = usersRes.data.sort((a, b) => new Date(b.creado_el || 0) - new Date(a.creado_el || 0));
      renderRecentUsers(sorted.slice(0, 5));
    }
    if (eventsRes.ok) {
      renderEventsDashboard(eventsRes.data);
    }
  } catch (err) {
    console.error('Error cargando dashboard:', err);
  }
}

function renderRecentUsers(users) {
  const container = document.getElementById('recent-users-list');
  if (!users.length) {
    container.innerHTML = '<p class="text-muted">Sin usuarios aún.</p>';
    return;
  }
  container.innerHTML = users.map(u => `
    <div class="user-row-item" onclick="openUserModal('${u.telegram_id || u._key}')">
      <span class="user-avatar">👤</span>
      <div class="user-info">
        <div class="user-name">${u.nombre || 'Sin nombre'}</div>
        <div class="user-meta">@${u.username || '—'} · ${u.vicio || 'sin vicio'}</div>
      </div>
      <span class="${badgeClass(u.estado_plan)} badge">${u.estado_plan || '—'}</span>
    </div>
  `).join('');
}

function renderEventsDashboard(events) {
  const container = document.getElementById('recent-events-dashboard');
  if (!events.length) {
    container.innerHTML = '<p class="text-muted">Sin eventos recientes.</p>';
    return;
  }
  container.innerHTML = events.map(ev => `
    <div class="timeline-item">
      <div class="timeline-dot">${eventIcon(ev.tipo)}</div>
      <div class="timeline-content">
        <div class="timeline-title">${ev.tipo || '—'}</div>
        <div class="timeline-desc">${ev.descripcion || ''}</div>
        <div class="timeline-time">${formatDate(ev.timestamp)}</div>
      </div>
    </div>
  `).join('');
}

/* ══════════════════════════════════════════════════════════
   PLAYERS (tabla extendida)
══════════════════════════════════════════════════════════ */
let _allPlayers = [];

async function loadPlayers() {
  const tbody = document.getElementById('players-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="loading-row">Cargando players...</td></tr>';
  try {
    const res = await fetchApi('/api/users');
    if (!res.ok) throw new Error('Error al cargar players');
    _allPlayers = res.data;
    renderPlayersTable(_allPlayers);
    setupPlayerFilters();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-row">Error: ${err.message}</td></tr>`;
  }
}

function renderPlayersTable(players) {
  const tbody = document.getElementById('players-tbody');
  if (!players.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="loading-row">Sin players que coincidan.</td></tr>';
    return;
  }
  tbody.innerHTML = players.map(u => {
    const pct = u.progreso_pct || 0;
    const ayudantes = u.ayudantes ? Object.keys(u.ayudantes).length : 0;
    return `
      <tr onclick="openUserModal('${u.telegram_id || u._key}')">
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:20px">👤</span>
            <div>
              <div style="font-weight:600">${u.nombre || 'Sin nombre'}</div>
              <div style="font-size:11px;color:#64748b">@${u.username || '—'} · ID: ${u.telegram_id || u._key}</div>
            </div>
          </div>
        </td>
        <td>${u.vicio || '—'}</td>
        <td><span class="badge ${badgeClass(u.estado_plan)}">${u.estado_plan || '—'}</span></td>
        <td>
          <div style="display:flex;align-items:center;gap:8px">
            <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:999px;height:6px;min-width:70px">
              <div style="width:${pct}%;height:100%;border-radius:999px;background:linear-gradient(90deg,#6366f1,#22d3ee);transition:width 0.3s"></div>
            </div>
            <span style="font-size:12px;color:#94a3b8;white-space:nowrap">${pct}%</span>
          </div>
        </td>
        <td><span style="color:#f59e0b;font-weight:700">🔥 ${u.racha_dias || 0}</span></td>
        <td>
          <div style="font-size:12px">
            <div style="color:#a855f7;font-weight:700">⭐ ${u.xp || 0}</div>
            <div style="color:#64748b">Nv. ${u.nivel_info ? u.nivel_info.nombre : '—'}</div>
          </div>
        </td>
        <td>
          <span style="font-size:13px">${ayudantes > 0 ? `🤝 ${ayudantes}` : '—'}</span>
        </td>
        <td style="font-size:11px;color:#64748b">
          <div>${formatDate(u.fecha_inicio)}</div>
          <div style="color:#22d3ee">${formatDate(u.fecha_fin_estimada)}</div>
        </td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();openUserModal('${u.telegram_id || u._key}')">Ver</button>
            <button class="btn btn-sm" onclick="event.stopPropagation();quickMessage('${u.telegram_id || u._key}','${(u.nombre||'').replace(/'/g,"'")}')" title="Enviar mensaje">📤</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function setupPlayerFilters() {
  const searchInput = document.getElementById('search-players');
  const estadoFilter = document.getElementById('filter-estado-players');
  const sortBy = document.getElementById('sort-by-players');

  function applyFilters() {
    const q = searchInput.value.toLowerCase();
    const estado = estadoFilter.value;
    const sort = sortBy.value;

    let filtered = _allPlayers.filter(u => {
      const matchQ = !q || (u.nombre || '').toLowerCase().includes(q) ||
                     (u.username || '').toLowerCase().includes(q) ||
                     (u.vicio || '').toLowerCase().includes(q) ||
                     (u.telegram_id || '').includes(q);
      const matchEstado = !estado || u.estado_plan === estado;
      return matchQ && matchEstado;
    });

    if (sort === 'racha_dias')   filtered.sort((a, b) => (b.racha_dias || 0) - (a.racha_dias || 0));
    else if (sort === 'xp')      filtered.sort((a, b) => (b.xp || 0) - (a.xp || 0));
    else if (sort === 'progreso_pct') filtered.sort((a, b) => (b.progreso_pct || 0) - (a.progreso_pct || 0));
    else filtered.sort((a, b) => new Date(b.creado_el || 0) - new Date(a.creado_el || 0));

    renderPlayersTable(filtered);
  }

  searchInput.addEventListener('input', applyFilters);
  estadoFilter.addEventListener('change', applyFilters);
  sortBy.addEventListener('change', applyFilters);
}

function quickMessage(telegramId, nombre) {
  loadSection('mensajes');
  setTimeout(() => {
    document.getElementById('msg-telegram-id').value = telegramId;
    document.getElementById('msg-individual').focus();
  }, 300);
}

/* ══════════════════════════════════════════════════════════
   MISIONES (CRUD)
══════════════════════════════════════════════════════════ */
let _allMissions = [];

async function loadMissions() {
  const grid = document.getElementById('missions-grid');
  grid.innerHTML = '<div class="skeleton-list"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    const res = await fetchApi('/api/missions');
    if (!res.ok) throw new Error('Error al cargar misiones');
    _allMissions = res.data;
    renderMissionsGrid(_allMissions);
    setupMissionFilters();
  } catch (err) {
    grid.innerHTML = `<p class="text-muted">Error: ${err.message}</p>`;
  }
}

function renderMissionsGrid(missions) {
  const grid = document.getElementById('missions-grid');
  if (!missions.length) {
    grid.innerHTML = '<p class="text-muted">Sin misiones que coincidan.</p>';
    return;
  }
  grid.innerHTML = missions.map(m => `
    <div class="mission-card ${m.activa ? '' : 'mission-inactive'}">
      <div class="mission-card-header">
        <div>
          <div class="mission-card-title">${m.nombre || m.id}</div>
          <div class="mission-card-meta">
            <span class="badge-categoria">${m.categoria || 'general'}</span>
            ${m.horario_programado ? `<span class="badge-horario">⏰ ${m.horario_programado.hora}:${String(m.horario_programado.minuto).padStart(2,'0')}</span>` : ''}
          </div>
        </div>
        <div class="mission-card-pts">+${m.puntos_recompensa || 0} pts</div>
      </div>
      <p class="mission-card-desc">${m.descripcion || ''}</p>
      <div class="mission-card-actions">
        <span class="badge ${m.activa ? 'badge-activo' : 'badge-pausado'}">${m.activa ? 'Activa' : 'Inactiva'}</span>
        <div style="display:flex;gap:8px">
          <button class="btn btn-sm" onclick="editMission('${m.id}')">✏️ Editar</button>
          <button class="btn btn-sm btn-danger-outline" onclick="toggleMission('${m.id}', ${!m.activa})">${m.activa ? '⏸ Desactivar' : '▶ Activar'}</button>
          <button class="btn btn-sm btn-danger-outline" onclick="deleteMission('${m.id}')">🗑️</button>
        </div>
      </div>
    </div>
  `).join('');
}

function setupMissionFilters() {
  const searchInput = document.getElementById('search-missions');
  const catFilter   = document.getElementById('filter-categoria');
  const actFilter   = document.getElementById('filter-activa');

  function applyFilters() {
    const q   = searchInput.value.toLowerCase();
    const cat = catFilter.value;
    const act = actFilter.value;

    let filtered = _allMissions.filter(m => {
      const matchQ   = !q   || (m.nombre || '').toLowerCase().includes(q) || (m.descripcion || '').toLowerCase().includes(q);
      const matchCat = !cat || m.categoria === cat;
      const matchAct = !act || String(m.activa) === act;
      return matchQ && matchCat && matchAct;
    });
    renderMissionsGrid(filtered);
  }

  searchInput.addEventListener('input', applyFilters);
  catFilter.addEventListener('change', applyFilters);
  actFilter.addEventListener('change', applyFilters);
}

// ── Modal de misiones ────────────────────────────────────
function openMissionModal(mission = null) {
  document.getElementById('mission-modal-overlay').classList.remove('hidden');
  document.getElementById('m-id').value = '';
  document.getElementById('m-nombre').value = '';
  document.getElementById('m-descripcion').value = '';
  document.getElementById('m-categoria').value = 'general';
  document.getElementById('m-puntos').value = 10;
  document.getElementById('m-tiene-horario').checked = false;
  document.getElementById('m-horario-fields').classList.add('hidden');
  document.getElementById('m-hora').value = '';
  document.getElementById('m-minuto').value = '';
  document.getElementById('m-activa').checked = true;
  document.getElementById('mission-modal-feedback').classList.add('hidden');

  if (mission) {
    document.getElementById('mission-modal-title').textContent = '✏️ Editar Misión';
    document.getElementById('m-id').value          = mission.id;
    document.getElementById('m-nombre').value      = mission.nombre || '';
    document.getElementById('m-descripcion').value = mission.descripcion || '';
    document.getElementById('m-categoria').value   = mission.categoria || 'general';
    document.getElementById('m-puntos').value      = mission.puntos_recompensa || 10;
    document.getElementById('m-activa').checked    = !!mission.activa;
    if (mission.horario_programado) {
      document.getElementById('m-tiene-horario').checked = true;
      document.getElementById('m-horario-fields').classList.remove('hidden');
      document.getElementById('m-hora').value   = mission.horario_programado.hora;
      document.getElementById('m-minuto').value = mission.horario_programado.minuto;
    }
  } else {
    document.getElementById('mission-modal-title').textContent = '➕ Nueva Misión';
  }
}

function closeMissionModal() {
  document.getElementById('mission-modal-overlay').classList.add('hidden');
}

document.getElementById('mission-modal-close').addEventListener('click', closeMissionModal);
document.getElementById('mission-modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('mission-modal-overlay')) closeMissionModal();
});

document.getElementById('m-tiene-horario').addEventListener('change', e => {
  document.getElementById('m-horario-fields').classList.toggle('hidden', !e.target.checked);
});

document.getElementById('btn-save-mission').addEventListener('click', async () => {
  const id     = document.getElementById('m-id').value;
  const nombre = document.getElementById('m-nombre').value.trim();
  if (!nombre) {
    showMissionFeedback('error', 'El nombre es requerido.');
    return;
  }

  const payload = {
    nombre,
    descripcion:      document.getElementById('m-descripcion').value.trim(),
    categoria:        document.getElementById('m-categoria').value,
    puntos_recompensa: parseInt(document.getElementById('m-puntos').value) || 10,
    activa:           document.getElementById('m-activa').checked,
  };

  if (document.getElementById('m-tiene-horario').checked) {
    payload.horario_programado = {
      hora:   parseInt(document.getElementById('m-hora').value) || 0,
      minuto: parseInt(document.getElementById('m-minuto').value) || 0,
    };
  }

  let res;
  if (id) {
    res = await fetchApi(`/api/missions/${id}`, 'PATCH', payload);
  } else {
    res = await fetchApi('/api/missions', 'POST', payload);
  }

  if (res.ok) {
    closeMissionModal();
    loadMissions();
  } else {
    showMissionFeedback('error', res.error || 'Error al guardar.');
  }
});

function showMissionFeedback(type, text) {
  const el = document.getElementById('mission-modal-feedback');
  el.className = `alert alert-${type}`;
  el.textContent = text;
  el.classList.remove('hidden');
}

async function editMission(missionId) {
  const mission = _allMissions.find(m => m.id === missionId);
  if (mission) openMissionModal(mission);
}

async function toggleMission(missionId, newActive) {
  await fetchApi(`/api/missions/${missionId}`, 'PATCH', { activa: newActive });
  loadMissions();
}

async function deleteMission(missionId) {
  if (!confirm('¿Eliminar/desactivar esta misión?')) return;
  const res = await fetchApi(`/api/missions/${missionId}`, 'DELETE');
  if (res.ok) loadMissions();
}

/* ══════════════════════════════════════════════════════════
   MENSAJES
══════════════════════════════════════════════════════════ */
async function loadMensajes() {
  // Contar activos para el broadcast
  try {
    const res = await fetchApi('/api/stats');
    if (res.ok) {
      const activos = (res.data.activos || 0) + (res.data.pausados || 0);
      document.getElementById('broadcast-count').textContent =
        `${res.data.activos || 0} usuarios activos`;
    }
  } catch {}
}

document.getElementById('btn-send-individual').addEventListener('click', async () => {
  const telegramId = document.getElementById('msg-telegram-id').value.trim();
  const mensaje    = document.getElementById('msg-individual').value.trim();
  const feedback   = document.getElementById('msg-individual-feedback');

  if (!telegramId || !mensaje) {
    showFeedback(feedback, 'error', '⚠️ Completa el ID de Telegram y el mensaje.');
    return;
  }

  const res = await fetchApi(`/api/users/${telegramId}/notify`, 'POST', { mensaje });
  if (res.ok) {
    showFeedback(feedback, 'success', '✅ Mensaje encolado para enviar.');
    document.getElementById('msg-individual').value = '';
  } else {
    showFeedback(feedback, 'error', `❌ Error: ${res.error || 'Usuario no encontrado.'}`);
  }
});

document.getElementById('btn-send-broadcast').addEventListener('click', async () => {
  const mensaje  = document.getElementById('msg-broadcast').value.trim();
  const feedback = document.getElementById('msg-broadcast-feedback');

  if (!mensaje) {
    showFeedback(feedback, 'error', '⚠️ Escribe un mensaje.');
    return;
  }

  if (!confirm('¿Enviar este mensaje a TODOS los usuarios activos?')) return;

  const res = await fetchApi('/api/broadcast', 'POST', { mensaje, tipo: 'broadcast' });
  if (res.ok) {
    showFeedback(feedback, 'success', `✅ Mensaje enviado a ${res.enviados} usuarios.`);
    document.getElementById('msg-broadcast').value = '';
  } else {
    showFeedback(feedback, 'error', `❌ Error: ${res.error}`);
  }
});

/* ══════════════════════════════════════════════════════════
   MARKETING
══════════════════════════════════════════════════════════ */
async function loadMarketing() {
  loadBroadcastsHistory();
}

document.getElementById('btn-preview-marketing').addEventListener('click', () => {
  const titulo   = document.getElementById('mkt-titulo').value.trim();
  const contenido= document.getElementById('mkt-contenido').value.trim();
  const preview  = document.getElementById('mkt-preview');
  if (!contenido) { preview.classList.add('hidden'); return; }
  preview.textContent = titulo ? `📌 ${titulo}\n\n${contenido}` : contenido;
  preview.classList.remove('hidden');
});

document.getElementById('btn-send-marketing').addEventListener('click', async () => {
  const titulo   = document.getElementById('mkt-titulo').value.trim();
  const contenido= document.getElementById('mkt-contenido').value.trim();
  const feedback = document.getElementById('mkt-feedback');

  if (!contenido) {
    showFeedback(feedback, 'error', '⚠️ Escribe el contenido de la campaña.');
    return;
  }

  const mensaje = titulo ? `📌 *${titulo}*\n\n${contenido}` : contenido;

  if (!confirm('¿Enviar esta campaña a TODOS los usuarios activos?')) return;

  const res = await fetchApi('/api/broadcast', 'POST', { mensaje, tipo: 'marketing' });
  if (res.ok) {
    showFeedback(feedback, 'success', `🚀 Campaña enviada a ${res.enviados} usuarios.`);
    document.getElementById('mkt-titulo').value = '';
    document.getElementById('mkt-contenido').value = '';
    document.getElementById('mkt-preview').classList.add('hidden');
    loadBroadcastsHistory();
  } else {
    showFeedback(feedback, 'error', `❌ Error: ${res.error}`);
  }
});

async function loadBroadcastsHistory() {
  const container = document.getElementById('broadcasts-history');
  try {
    const res = await fetchApi('/api/broadcasts');
    if (!res.ok || !res.data.length) {
      container.innerHTML = '<p class="text-muted">Sin campañas enviadas aún.</p>';
      return;
    }
    container.innerHTML = res.data.slice(0, 10).map(b => `
      <div class="broadcast-item">
        <div class="broadcast-meta">
          <span class="badge ${b.tipo === 'marketing' ? 'badge-completado' : 'badge-activo'}">${b.tipo || 'broadcast'}</span>
          <span style="font-size:11px;color:#64748b">${formatDate(b.fecha)}</span>
          <span style="font-size:11px;color:#64748b">→ ${b.total_destinatarios || 0} destinatarios</span>
        </div>
        <p class="broadcast-contenido">${(b.contenido || '').substring(0, 120)}${(b.contenido || '').length > 120 ? '…' : ''}</p>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p class="text-muted">Error: ${err.message}</p>`;
  }
}

/* ══════════════════════════════════════════════════════════
   EVENTOS / TIMELINE
══════════════════════════════════════════════════════════ */
async function loadEvents() {
  const timeline = document.getElementById('events-timeline');
  timeline.innerHTML = '<div class="skeleton-list"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    const res = await fetchApi('/api/events?limit=50');
    if (!res.ok) throw new Error('Error al cargar eventos');
    if (!res.data.length) {
      timeline.innerHTML = '<p class="text-muted">Sin eventos registrados.</p>';
      return;
    }
    timeline.innerHTML = res.data.map(ev => `
      <div class="timeline-item">
        <div class="timeline-dot">${eventIcon(ev.tipo)}</div>
        <div class="timeline-content">
          <div class="timeline-title"><strong>${ev.usuario_id || '—'}</strong> · ${ev.tipo || '—'}</div>
          <div class="timeline-desc">${ev.descripcion || ''}</div>
          <div class="timeline-time">${formatDate(ev.timestamp)}</div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    timeline.innerHTML = `<p class="text-muted">Error: ${err.message}</p>`;
  }
}

/* ══════════════════════════════════════════════════════════
   MODAL DE USUARIO
══════════════════════════════════════════════════════════ */
let _currentUserId = null;
const modalOverlay = document.getElementById('user-modal-overlay');

document.getElementById('modal-close').addEventListener('click', closeModal);
modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal(); });

function closeModal() {
  modalOverlay.classList.add('hidden');
  _currentUserId = null;
}

async function openUserModal(telegramId) {
  _currentUserId = telegramId;
  modalOverlay.classList.remove('hidden');

  ['info-telegram-id','info-vicio','info-estado','info-duracion','info-fecha-inicio',
   'info-fecha-fin','info-compromiso','info-progreso-pct','modal-nombre','modal-username']
  .forEach(id => { const el = document.getElementById(id); if(el) el.textContent = '—'; });
  document.getElementById('action-feedback').classList.add('hidden');

  // Resetear tabs
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
  document.querySelector('.tab-btn[data-tab="info"]').classList.add('active');
  document.getElementById('tab-info').classList.remove('hidden');

  try {
    const res = await fetchApi(`/api/users/${telegramId}`);
    if (!res.ok) throw new Error('Usuario no encontrado');
    const u = res.data;

    document.getElementById('modal-nombre').textContent = u.nombre || 'Sin nombre';
    document.getElementById('modal-username').textContent = `@${u.username || '—'} · TG: ${u.telegram_id}`;
    document.getElementById('info-telegram-id').textContent  = u.telegram_id;
    document.getElementById('info-vicio').textContent        = u.vicio || '—';
    document.getElementById('info-estado').innerHTML         = `<span class="badge ${badgeClass(u.estado_plan)}">${u.estado_plan || '—'}</span>`;
    document.getElementById('info-duracion').textContent     = u.duracion_meses ? `${u.duracion_meses} meses` : '—';
    document.getElementById('info-fecha-inicio').textContent = formatDate(u.fecha_inicio);
    document.getElementById('info-fecha-fin').textContent    = formatDate(u.fecha_fin_estimada);
    document.getElementById('info-progreso-pct').textContent = `${u.progreso_pct || 0}%`;
    const comp = u.retencion_compromiso || {};
    document.getElementById('info-compromiso').textContent = comp.estado || '—';

    // Edit fields
    document.getElementById('edit-nombre').value = u.nombre || '';
    document.getElementById('edit-xp').value    = u.xp || 0;
    document.getElementById('edit-racha').value = u.racha_dias || 0;
    document.getElementById('edit-estado').value = u.estado_plan || 'activo';

    // Progreso
    const nivel = u.nivel_info || {};
    document.getElementById('prog-racha').textContent = `🔥 ${u.racha_dias || 0} días`;
    document.getElementById('prog-xp').textContent    = `⭐ ${u.xp || 0}`;
    document.getElementById('prog-nivel').textContent = `${u.nivel || 1} — ${nivel.nombre || '—'}`;

    // Barra de plan
    const pct = u.progreso_pct || 0;
    document.getElementById('prog-plan-bar').style.width  = `${pct}%`;
    document.getElementById('prog-plan-text').textContent = `${pct}% del plan completado`;

    // Barra XP
    const xpBar = document.getElementById('prog-xp-bar');
    xpBar.style.width = `${Math.min(((u.xp || 0) % 500) / 5, 100)}%`;
    document.getElementById('prog-xp-text').textContent = `${(u.xp || 0) % 500} / 500 XP al siguiente nivel`;

    // Misiones
    const misionsList = document.getElementById('missions-list');
    misionsList.innerHTML = (u.misiones_log || []).slice(0, 5).map(m => `
      <div class="mission-item">
        <span class="mission-name">${m.mision_id || '—'}</span>
        <span class="mission-xp">+${m.xp_ganada || 0} XP · ${formatDate(m.timestamp)}</span>
      </div>
    `).join('') || '<p class="text-muted">Sin misiones registradas.</p>';

    // Ayudantes
    const helpersList = document.getElementById('helpers-list');
    helpersList.innerHTML = (u.ayudantes_list || []).map(h => `
      <div class="helper-card">
        <div class="helper-name">👤 ${h.nombre || '—'}</div>
        <div class="helper-role">${h.rol || '—'} · @${h.username || '—'} · ID: ${h.telegram_id}</div>
      </div>
    `).join('') || '<p class="text-muted">Sin ayudantes registrados.</p>';

    // Recaídas
    const relapsesList = document.getElementById('relapses-list');
    relapsesList.innerHTML = (u.recaidas || []).map(r => `
      <div class="relapse-card">
        <div class="relapse-date">${formatDate(r.timestamp)}</div>
        <div>Racha previa: ${r.racha_previa} días · ${r.detalles || 'Sin detalles'}</div>
      </div>
    `).join('') || '<p class="text-muted">Sin recaídas registradas. ¡Excelente!</p>';

  } catch (err) {
    document.getElementById('modal-nombre').textContent = 'Error al cargar usuario';
  }
}

// Tabs del modal
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
  });
});

// Guardar cambios
document.getElementById('save-user-btn').addEventListener('click', async () => {
  if (!_currentUserId) return;
  const payload = {
    nombre:     document.getElementById('edit-nombre').value,
    xp:         parseInt(document.getElementById('edit-xp').value) || 0,
    racha_dias: parseInt(document.getElementById('edit-racha').value) || 0,
    estado_plan: document.getElementById('edit-estado').value,
  };
  const res = await fetchApi(`/api/users/${_currentUserId}`, 'PATCH', payload);
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? '✅ Cambios guardados.' : '❌ Error al guardar.');
  if (res.ok) loadDashboard();
});

// Botones de acción del modal
document.getElementById('btn-resume').addEventListener('click', () => userAction('resume'));
document.getElementById('btn-pause').addEventListener('click',  () => userAction('pause'));
document.getElementById('btn-finish').addEventListener('click', () => userAction('finish'));
document.getElementById('btn-send-message').addEventListener('click', async () => {
  const mensaje = document.getElementById('custom-message').value.trim();
  if (!mensaje || !_currentUserId) return;
  const res = await fetchApi(`/api/users/${_currentUserId}/notify`, 'POST', { mensaje });
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? '✅ Mensaje encolado.' : '❌ Error al enviar.');
  if (res.ok) document.getElementById('custom-message').value = '';
});

async function userAction(action) {
  if (!_currentUserId) return;
  const res = await fetchApi(`/api/users/${_currentUserId}/${action}`, 'POST');
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? `✅ Acción '${action}' aplicada.` : '❌ Error.');
  if (res.ok) openUserModal(_currentUserId);
}

function showActionFeedback(type, text) {
  const el = document.getElementById('action-feedback');
  el.className = `alert alert-${type}`;
  el.textContent = text;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4000);
}

/* ══════════════════════════════════════════════════════════
   UTILIDADES
══════════════════════════════════════════════════════════ */
async function fetchApi(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    return await res.json();
  } catch (err) {
    console.error(`fetchApi error [${path}]:`, err);
    return { ok: false, error: err.message };
  }
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}

function badgeClass(estado) {
  const map = {
    activo: 'badge-activo', pausado: 'badge-pausado',
    completado: 'badge-completado', recuperacion: 'badge-recuperacion',
    abandonado: 'badge-abandonado', configurando: 'badge-configurando',
  };
  return map[estado] || 'badge-configurando';
}

function eventIcon(tipo) {
  const icons = {
    recaida: '❗', mision_completada: '✅', xp_ganada: '⭐',
    ayudante_registrado: '🤝', plan_pausado: '⏸️', recuperacion_iniciada: '🔄',
    admin_edicion: '✏️', admin_notificacion: '📤', deteccion_riesgo: '⚠️',
    chequeo_ayudante: '👀', escrow_iniciado: '💰', pastilla_tomada: '💊',
    plan_reintento: '🔄', xp_penalizada: '📉',
  };
  return icons[tipo] || '📌';
}

function showFeedback(el, type, text) {
  el.className = `alert alert-${type}`;
  el.textContent = text;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 5000);
}
/**
 * script.js — Lógica del Panel Administrativo de RenovaBot.
 * Maneja navegación, carga de datos desde la API Flask / Firebase,
 * filtros, tabla de usuarios, modal y acciones admin.
 */

/* ══════════════════════════════════════════════════════════
   AUTENTICACIÓN
══════════════════════════════════════════════════════════ */
firebase.auth().onAuthStateChanged(user => {
  if (!user) {
    window.location.href = '/';
    return;
  }
  document.getElementById('admin-email-display').textContent = user.email;
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
    const now = new Date();
    el.textContent = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
}
setInterval(updateClock, 1000);
updateClock();

/* ══════════════════════════════════════════════════════════
   NAVEGACIÓN ENTRE SECCIONES
══════════════════════════════════════════════════════════ */
const sections = ['dashboard', 'usuarios', 'eventos'];
const sectionTitles = {
  dashboard: '📊 Dashboard',
  usuarios: '👥 Gestión de Usuarios',
  eventos: '📋 Historial de Eventos'
};

function loadSection(name) {
  sections.forEach(s => {
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
  document.getElementById('topbar-title').textContent = sectionTitles[name] || name;

  if (name === 'usuarios') loadUsers();
  if (name === 'eventos') loadEvents();
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    loadSection(item.dataset.section);
  });
});

// Sidebar toggle mobile
document.getElementById('sidebar-toggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});

/* ══════════════════════════════════════════════════════════
   INICIALIZACIÓN
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

    // KPIs
    if (statsRes.ok) {
      const d = statsRes.data;
      document.getElementById('kpi-total-val').textContent = d.total_usuarios;
      document.getElementById('kpi-activos-val').textContent = d.activos;
      document.getElementById('kpi-completados-val').textContent = d.completados;
      document.getElementById('kpi-pausados-val').textContent = d.pausados;
      document.getElementById('kpi-racha-val').textContent = d.racha_maxima;
    }

    // Usuarios recientes
    if (usersRes.ok) {
      const sorted = usersRes.data.sort((a, b) => new Date(b.creado_el || 0) - new Date(a.creado_el || 0));
      renderRecentUsers(sorted.slice(0, 5));
    }

    // Eventos recientes
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
   TABLA DE USUARIOS
══════════════════════════════════════════════════════════ */
let _allUsers = [];

async function loadUsers() {
  const tbody = document.getElementById('users-tbody');
  tbody.innerHTML = '<tr><td colspan="8" class="loading-row">Cargando...</td></tr>';
  try {
    const res = await fetchApi('/api/users');
    if (!res.ok) throw new Error('Error al cargar usuarios');
    _allUsers = res.data;
    renderUsersTable(_allUsers);
    setupUserFilters();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="loading-row">Error: ${err.message}</td></tr>`;
  }
}

function renderUsersTable(users) {
  const tbody = document.getElementById('users-tbody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">Sin usuarios que coincidan.</td></tr>';
    return;
  }
  tbody.innerHTML = users.map(u => `
    <tr onclick="openUserModal('${u.telegram_id || u._key}')">
      <td>
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:22px">👤</span>
          <div>
            <div style="font-weight:600">${u.nombre || 'Sin nombre'}</div>
            <div style="font-size:11px;color:#64748b">@${u.username || '—'}</div>
          </div>
        </div>
      </td>
      <td>${u.vicio || '—'}</td>
      <td><span class="badge ${badgeClass(u.estado_plan)}">${u.estado_plan || '—'}</span></td>
      <td><span style="color:#f59e0b;font-weight:700">🔥 ${u.racha_dias || 0}</span></td>
      <td><span style="color:#a855f7;font-weight:700">⭐ ${u.xp || 0}</span></td>
      <td>${u.nivel_info ? u.nivel_info.nombre : u.nivel || 1}</td>
      <td style="font-size:12px;color:#64748b">${formatDate(u.fecha_inicio)}</td>
      <td>
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();openUserModal('${u.telegram_id || u._key}')">Ver</button>
      </td>
    </tr>
  `).join('');
}

function setupUserFilters() {
  const searchInput = document.getElementById('search-users');
  const estadoFilter = document.getElementById('filter-estado');
  const sortBy = document.getElementById('sort-by');

  function applyFilters() {
    const q = searchInput.value.toLowerCase();
    const estado = estadoFilter.value;
    const sort = sortBy.value;

    let filtered = _allUsers.filter(u => {
      const matchQ = !q || (u.nombre || '').toLowerCase().includes(q) ||
                     (u.username || '').toLowerCase().includes(q) ||
                     (u.vicio || '').toLowerCase().includes(q);
      const matchEstado = !estado || u.estado_plan === estado;
      return matchQ && matchEstado;
    });

    if (sort === 'racha_dias') filtered.sort((a, b) => (b.racha_dias || 0) - (a.racha_dias || 0));
    else if (sort === 'xp') filtered.sort((a, b) => (b.xp || 0) - (a.xp || 0));
    else filtered.sort((a, b) => new Date(b.creado_el || 0) - new Date(a.creado_el || 0));

    renderUsersTable(filtered);
  }

  searchInput.addEventListener('input', applyFilters);
  estadoFilter.addEventListener('change', applyFilters);
  sortBy.addEventListener('change', applyFilters);
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

  // Reset
  ['info-telegram-id','info-vicio','info-estado','info-duracion','info-fecha-inicio','info-compromiso',
   'modal-nombre','modal-username'].forEach(id => { const el = document.getElementById(id); if(el) el.textContent = '—'; });
  document.getElementById('action-feedback').classList.add('hidden');

  try {
    const res = await fetchApi(`/api/users/${telegramId}`);
    if (!res.ok) throw new Error('Usuario no encontrado');
    const u = res.data;

    document.getElementById('modal-nombre').textContent = u.nombre || 'Sin nombre';
    document.getElementById('modal-username').textContent = `@${u.username || '—'} · TG: ${u.telegram_id}`;
    document.getElementById('info-telegram-id').textContent = u.telegram_id;
    document.getElementById('info-vicio').textContent = u.vicio || '—';
    document.getElementById('info-estado').innerHTML = `<span class="badge ${badgeClass(u.estado_plan)}">${u.estado_plan || '—'}</span>`;
    document.getElementById('info-duracion').textContent = u.duracion_meses ? `${u.duracion_meses} meses` : '—';
    document.getElementById('info-fecha-inicio').textContent = formatDate(u.fecha_inicio);
    const comp = u.retencion_compromiso || {};
    document.getElementById('info-compromiso').textContent = comp.estado || '—';

    // Edit fields
    document.getElementById('edit-nombre').value = u.nombre || '';
    document.getElementById('edit-xp').value = u.xp || 0;
    document.getElementById('edit-racha').value = u.racha_dias || 0;
    document.getElementById('edit-estado').value = u.estado_plan || 'activo';

    // Progreso
    const nivel = u.nivel_info || {};
    document.getElementById('prog-racha').textContent = `🔥 ${u.racha_dias || 0}`;
    document.getElementById('prog-xp').textContent = `⭐ ${u.xp || 0}`;
    document.getElementById('prog-nivel').textContent = `${u.nivel || 1} — ${nivel.nombre || '—'}`;

    // XP bar (simple estimation)
    const xpBar = document.getElementById('prog-xp-bar');
    xpBar.style.width = `${Math.min(((u.xp || 0) % 500) / 5, 100)}%`;
    document.getElementById('prog-xp-text').textContent = `${(u.xp || 0) % 500} / 500 XP hasta el próximo nivel`;

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
        <div class="helper-role">${h.rol || '—'} · @${h.username || '—'}</div>
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
    const tabId = `tab-${btn.dataset.tab}`;
    document.getElementById(tabId).classList.remove('hidden');
  });
});

// Guardar cambios
document.getElementById('save-user-btn').addEventListener('click', async () => {
  if (!_currentUserId) return;
  const payload = {
    nombre: document.getElementById('edit-nombre').value,
    xp: parseInt(document.getElementById('edit-xp').value) || 0,
    racha_dias: parseInt(document.getElementById('edit-racha').value) || 0,
    estado_plan: document.getElementById('edit-estado').value,
  };
  const res = await fetchApi(`/api/users/${_currentUserId}`, 'PATCH', payload);
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? '✅ Cambios guardados.' : '❌ Error al guardar.');
  if (res.ok) loadDashboard();
});

// Botones de acción
document.getElementById('btn-resume').addEventListener('click', () => userAction('resume'));
document.getElementById('btn-pause').addEventListener('click', () => userAction('pause'));
document.getElementById('btn-finish').addEventListener('click', () => userAction('finish'));
document.getElementById('btn-send-message').addEventListener('click', async () => {
  const msg = document.getElementById('custom-message').value.trim();
  if (!msg || !_currentUserId) return;
  const res = await fetchApi(`/api/users/${_currentUserId}/notify`, 'POST', { mensaje: msg });
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? '✅ Mensaje encolado para enviar.' : '❌ Error al enviar.');
  if (res.ok) document.getElementById('custom-message').value = '';
});

async function userAction(action) {
  if (!_currentUserId) return;
  const res = await fetchApi(`/api/users/${_currentUserId}/${action}`, 'POST');
  showActionFeedback(res.ok ? 'success' : 'error', res.ok ? `✅ Acción '${action}' aplicada.` : '❌ Error.');
  if (res.ok) openUserModal(_currentUserId);
}

function showActionFeedback(type, msg) {
  const el = document.getElementById('action-feedback');
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4000);
}

/* ══════════════════════════════════════════════════════════
   UTILIDADES
══════════════════════════════════════════════════════════ */
async function fetchApi(path, method = 'GET', body = null) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
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
    activo: 'badge-activo',
    pausado: 'badge-pausado',
    completado: 'badge-completado',
    recuperacion: 'badge-recuperacion',
    abandonado: 'badge-abandonado',
    configurando: 'badge-configurando',
  };
  return map[estado] || 'badge-configurando';
}

function eventIcon(tipo) {
  const icons = {
    recaida: '❗',
    mision_completada: '✅',
    xp_ganada: '⭐',
    ayudante_registrado: '🤝',
    plan_pausado: '⏸️',
    recuperacion_iniciada: '🔄',
    admin_edicion: '✏️',
    admin_notificacion: '📤',
    deteccion_riesgo: '⚠️',
    chequeo_ayudante: '👀',
    escrow_iniciado: '💰',
  };
  return icons[tipo] || '📌';
}
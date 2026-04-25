const state = {
  functionId: null, functionName: '', functionDef: '', page: 1, pageSize: 12,
  categoryCode: '', subcategoryCode: '', controlId: '', search: '', status: '', sortBy: 'control_id', sortDir: 'asc', total: 0,
  canManage: false, isProductManager: false, canDashboard: false, selected: new Set(),
};

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, credentials: 'include', ...opts });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

const showView = (id) => ['homeView', 'controlView', 'dashboardView'].forEach((v) => (document.getElementById(v).hidden = v !== id));

function statusBadge(status) {
  const map = { released: 'Released / Visible', hidden: 'Hidden', soft_deleted: 'Soft Deleted', deprecated: 'Deprecated' };
  return `<span class="badge badge-${status}">${map[status] || status}</span>`;
}

function pmStatusPill(status) {
  const s = status || 'open';
  return `<span class="badge badge-pm-${s}">${s.replace('_', ' ')}</span>`;
}

function configureRoleUI() {
  document.querySelectorAll('.col-select, .col-status').forEach((el) => (el.style.display = state.canManage ? '' : 'none'));
  document.getElementById('managePanel').hidden = !state.canManage;
  document.getElementById('selectHead').hidden = !state.canManage;
  document.getElementById('statusHead').hidden = !state.canManage;
  document.getElementById('statusFilter').hidden = !state.canManage;

  document.querySelectorAll('.col-pm-status, .col-pm-comment').forEach((el) => (el.style.display = state.isProductManager ? '' : 'none'));
  document.getElementById('pmStatusHead').hidden = !state.isProductManager;
  document.getElementById('pmCommentHead').hidden = !state.isProductManager;

  document.getElementById('dashboardBtn').hidden = !state.canDashboard;
}

function renderFunctionCards(functions) {
  const grid = document.getElementById('functionGrid');
  grid.innerHTML = '';
  functions.forEach((fn) => {
    const card = document.createElement('button');
    card.className = 'function-card';
    card.innerHTML = `<div class="function-code">${fn.name.toUpperCase()} (${fn.code})</div><div class="function-def">${fn.definition}</div>`;
    card.onclick = () => {
      state.functionId = fn.id;
      state.functionName = `${fn.name} (${fn.code})`;
      state.functionDef = fn.definition;
      state.page = 1;
      state.categoryCode = state.subcategoryCode = state.controlId = state.search = state.status = '';
      state.selected.clear();
      ['categoryFilter', 'subcategoryFilter', 'controlIdFilter', 'search', 'statusFilter'].forEach((id) => { const el = document.getElementById(id); if (el) el.value = ''; });
      document.getElementById('selectionTitle').textContent = state.functionName;
      document.getElementById('selectionDef').textContent = state.functionDef;
      showView('controlView');
      loadControls();
    };
    grid.appendChild(card);
  });
}

function fillSelectOptions(selectEl, options, valueKey, labelBuilder, placeholder) {
  const curr = selectEl.value;
  selectEl.innerHTML = `<option value="">${placeholder}</option>`;
  options.forEach((o) => {
    const opt = document.createElement('option');
    opt.value = o[valueKey];
    opt.textContent = labelBuilder(o);
    selectEl.appendChild(opt);
  });
  if ([...selectEl.options].some((o) => o.value === curr)) selectEl.value = curr;
}

function defCell(text) {
  if (!text) return '';
  const lim = 170;
  return text.length <= lim ? `<div class="definition-text">${text}</div>` : `<div class="definition-text">${text.slice(0, lim)}…</div><span class="muted">(use search to inspect full text)</span>`;
}

async function updateMyStatus(controlId) {
  const select = document.getElementById(`pm-stat-${controlId}`);
  const comment = document.getElementById(`pm-com-${controlId}`);
  await api('/api/pm/status', { method: 'POST', body: JSON.stringify({ control_id: controlId, status: select.value, status_comment: comment.value }) });
  await loadControls();
}

async function loadControls() {
  const q = new URLSearchParams({ function_id: state.functionId, page: state.page, page_size: state.pageSize, category_code: state.categoryCode, subcategory_code: state.subcategoryCode, control_id: state.controlId, search: state.search, status: state.status, sort_by: state.sortBy, sort_dir: state.sortDir });
  const data = await api(`/api/controls?${q.toString()}`);
  state.total = data.total;
  fillSelectOptions(document.getElementById('categoryFilter'), data.filter_options.categories, 'code', (c) => `${c.code} — ${c.name}`, 'All Categories');
  fillSelectOptions(document.getElementById('subcategoryFilter'), data.filter_options.subcategories, 'code', (s) => s.code, 'All Subcategories');

  const tbody = document.getElementById('rows');
  tbody.innerHTML = '';
  data.items.forEach((i) => {
    const tr = document.createElement('tr');
    const checkTd = state.canManage ? `<td><input type="checkbox" data-id="${i.control_id}" ${state.selected.has(i.control_id) ? 'checked' : ''}></td>` : '';
    const statusTd = state.canManage ? `<td>${statusBadge(i.status)}</td>` : '';
    const pmStatusTd = state.isProductManager
      ? `<td><select id="pm-stat-${i.control_id}"><option value="open" ${(!i.pm_status || i.pm_status === 'open') ? 'selected' : ''}>Open</option><option value="in_progress" ${i.pm_status === 'in_progress' ? 'selected' : ''}>In Progress</option><option value="closed" ${i.pm_status === 'closed' ? 'selected' : ''}>Closed</option></select></td>`
      : '';
    const pmCommentTd = state.isProductManager
      ? `<td><input id="pm-com-${i.control_id}" value="${i.pm_status_comment || ''}" placeholder="comment"/><div class="muted small">${i.pm_last_updated_at || 'Never updated'}</div><button class="link-btn" data-save-pm="${i.control_id}">Save</button></td>`
      : '';

    tr.innerHTML = `${checkTd}<td><div class="cell-code">${i.function_code}</div><div class="cell-name">${i.function_name}</div></td><td><div class="cell-code">${i.category_code}</div><div class="cell-name">${i.category_name}</div></td><td><div class="cell-code">${i.subcategory_code}</div></td><td><div class="control-id">${i.control_id}</div></td><td>${defCell(i.control_text)}</td>${pmStatusTd}${pmCommentTd}${statusTd}`;
    tbody.appendChild(tr);
  });

  if (state.canManage) {
    tbody.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.onchange = (e) => {
        const id = e.target.getAttribute('data-id');
        if (e.target.checked) state.selected.add(id); else state.selected.delete(id);
      };
    });
  }
  if (state.isProductManager) {
    tbody.querySelectorAll('button[data-save-pm]').forEach((btn) => {
      btn.onclick = () => updateMyStatus(btn.getAttribute('data-save-pm'));
    });
  }

  const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
  document.getElementById('pageMeta').textContent = `Page ${state.page}/${maxPage} • ${state.total} rows`;
}

async function runBulk(path) {
  if (!state.canManage) return;
  if (!state.selected.size) return alert('Select controls first.');
  await api(path, { method: 'POST', body: JSON.stringify({ control_ids: Array.from(state.selected), comment: document.getElementById('actionComment').value.trim() }) });
  state.selected.clear();
  await loadControls();
}

async function loadDashboard() {
  const q = new URLSearchParams({
    pm_username: document.getElementById('dashPm').value.trim(),
    function_id: document.getElementById('dashFunction').value,
    category_code: document.getElementById('dashCategory').value,
    subcategory_code: document.getElementById('dashSubcategory').value,
    status: document.getElementById('dashStatus').value,
  });
  const data = await api(`/api/dashboard?${q.toString()}`);

  document.getElementById('summaryCards').innerHTML = `
    <div class='sum-card'><b>Total</b><span>${data.summary.total_rows}</span></div>
    <div class='sum-card'><b>Open</b><span>${data.summary.overall_open}</span></div>
    <div class='sum-card'><b>In Progress</b><span>${data.summary.overall_in_progress}</span></div>
    <div class='sum-card'><b>Closed</b><span>${data.summary.overall_closed}</span></div>`;
  const total = Math.max(1, data.summary.total_rows);
  document.getElementById('miniChart').innerHTML = `
    <div class='bar b-open' style='width:${(data.summary.overall_open/total)*100}%'>Open ${data.summary.overall_open}</div>
    <div class='bar b-ip' style='width:${(data.summary.overall_in_progress/total)*100}%'>In Progress ${data.summary.overall_in_progress}</div>
    <div class='bar b-closed' style='width:${(data.summary.overall_closed/total)*100}%'>Closed ${data.summary.overall_closed}</div>`;

  const rows = document.getElementById('dashRows');
  rows.innerHTML = '';
  data.per_manager.forEach((m) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${m.product_manager}</td><td>${m.total}</td><td>${m.open}</td><td>${m.in_progress}</td><td>${m.closed}</td><td>${m.completion_pct}%</td><td>${m.overdue_or_stale}</td>`;
    rows.appendChild(tr);
  });
}

async function bootstrap() {
  const data = await api('/api/bootstrap');
  document.getElementById('loginCard').hidden = true;
  document.getElementById('main').hidden = false;
  document.getElementById('logoutBtn').hidden = false;
  state.canManage = data.can_manage === true && ['compliance_officer', 'risk_officer'].includes(data.me.role_name);
  state.isProductManager = data.is_product_manager === true;
  state.canDashboard = data.can_dashboard === true && state.canManage;
  configureRoleUI();
  document.getElementById('profile').textContent = `${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;
  renderFunctionCards(data.functions);

  fillSelectOptions(document.getElementById('dashFunction'), data.functions, 'id', (f) => `${f.code} — ${f.name}`, 'All Functions');
  showView('homeView');
}

async function login() {
  try {
    await api('/api/login', { method: 'POST', body: JSON.stringify({ username: document.getElementById('username').value.trim(), password: document.getElementById('password').value }) });
    await bootstrap();
  } catch (e) {
    document.getElementById('loginErr').textContent = e.message;
  }
}

// bindings

document.getElementById('loginBtn').onclick = login;
document.getElementById('logoutBtn').onclick = async () => { await api('/api/logout', { method: 'POST' }); location.reload(); };
document.getElementById('backBtn').onclick = () => showView('homeView');
document.getElementById('dashboardBtn').onclick = async () => { showView('dashboardView'); await loadDashboard(); };
document.getElementById('dashBackBtn').onclick = () => showView('homeView');
document.getElementById('dashApply').onclick = loadDashboard;

document.getElementById('categoryFilter').onchange = (e) => { state.categoryCode = e.target.value; state.page = 1; loadControls(); };
document.getElementById('subcategoryFilter').onchange = (e) => { state.subcategoryCode = e.target.value; state.page = 1; loadControls(); };
document.getElementById('controlIdFilter').oninput = (e) => { state.controlId = e.target.value.trim(); state.page = 1; loadControls(); };
document.getElementById('search').oninput = (e) => { state.search = e.target.value; state.page = 1; loadControls(); };
document.getElementById('statusFilter').onchange = (e) => { state.status = e.target.value; state.page = 1; loadControls(); };
document.getElementById('sortBy').onchange = (e) => { state.sortBy = e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = (e) => { state.sortDir = e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if (state.page > 1) { state.page -= 1; loadControls(); } };
document.getElementById('next').onclick = () => { const max = Math.max(1, Math.ceil(state.total / state.pageSize)); if (state.page < max) { state.page += 1; loadControls(); } };

document.getElementById('releaseBtn').onclick = () => runBulk('/api/controls/bulk-release');
document.getElementById('hideBtn').onclick = () => runBulk('/api/controls/bulk-hide');
document.getElementById('deleteBtn').onclick = () => runBulk('/api/controls/soft-delete');
document.getElementById('restoreBtn').onclick = () => runBulk('/api/controls/restore');
document.getElementById('deprecateBtn').onclick = () => runBulk('/api/controls/deprecate');

configureRoleUI();
api('/api/bootstrap').then(bootstrap).catch(() => {});

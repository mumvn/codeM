const state = {
  functionId: null,
  functionName: '',
  functionDef: '',
  page: 1,
  pageSize: 12,
  categoryCode: '',
  subcategoryCode: '',
  controlId: '',
  search: '',
  status: '',
  sortBy: 'control_id',
  sortDir: 'asc',
  total: 0,
  canManage: false,
  selected: new Set(),
};

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, credentials: 'include', ...opts });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

const showHomeView = () => { document.getElementById('homeView').hidden = false; document.getElementById('controlView').hidden = true; };
const showControlView = () => { document.getElementById('homeView').hidden = true; document.getElementById('controlView').hidden = false; };

function statusBadge(status) {
  const map = {
    released: 'Released / Visible to Users',
    hidden: 'Hidden / Compliance & Risk Only',
    soft_deleted: 'Soft Deleted',
    deprecated: 'Deprecated',
  };
  return `<span class="badge badge-${status}">${map[status] || status}</span>`;
}

function configureRoleUI() {
  const managePanel = document.getElementById('managePanel');
  const selectHead = document.getElementById('selectHead');
  const statusHead = document.getElementById('statusHead');
  const statusFilter = document.getElementById('statusFilter');
  managePanel.hidden = !state.canManage;
  selectHead.hidden = !state.canManage;
  statusHead.hidden = !state.canManage;
  statusFilter.hidden = !state.canManage;

  // Hard-hide manager-only columns and controls for read-only users
  document.querySelectorAll('.col-select, .col-status').forEach((el) => {
    el.style.display = state.canManage ? '' : 'none';
  });
  if (!state.canManage) {
    document.getElementById('actionComment').value = '';
    state.selected.clear();
  }
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
      state.categoryCode = '';
      state.subcategoryCode = '';
      state.controlId = '';
      state.search = '';
      state.status = '';
      state.selected.clear();
      ['categoryFilter', 'subcategoryFilter', 'controlIdFilter', 'search', 'statusFilter'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      document.getElementById('selectionTitle').textContent = state.functionName;
      document.getElementById('selectionDef').textContent = state.functionDef;
      showControlView();
      loadControls();
    };
    grid.appendChild(card);
  });
}


function defCell(text, id) {
  const limit = 170;
  const safe = text || '';
  if (safe.length <= limit) return `<div class="definition-text">${safe}</div>`;
  const short = safe.slice(0, limit) + '…';
  return `<div class="definition-text" id="def-${id}" data-full="${safe.replace('"','&quot;')}" data-short="${short.replace('"','&quot;')}">${short}</div><button class="link-btn" data-def-toggle="def-${id}">Show more</button>`;
}

function fillSelectOptions(selectEl, options, valueKey, labelBuilder, placeholder) {
  const current = selectEl.value;
  selectEl.innerHTML = `<option value="">${placeholder}</option>`;
  options.forEach((opt) => {
    const o = document.createElement('option');
    o.value = opt[valueKey];
    o.textContent = labelBuilder(opt);
    selectEl.appendChild(o);
  });
  if ([...selectEl.options].some((o) => o.value === current)) selectEl.value = current;
}

async function loadControls() {
  const q = new URLSearchParams({
    function_id: state.functionId,
    page: state.page,
    page_size: state.pageSize,
    category_code: state.categoryCode,
    subcategory_code: state.subcategoryCode,
    control_id: state.controlId,
    search: state.search,
    status: state.status,
    sort_by: state.sortBy,
    sort_dir: state.sortDir,
  });
  const data = await api(`/api/controls?${q.toString()}`);
  state.total = data.total;

  fillSelectOptions(document.getElementById('categoryFilter'), data.filter_options.categories, 'code', (c) => `${c.code} — ${c.name}`, 'All Categories');
  fillSelectOptions(document.getElementById('subcategoryFilter'), data.filter_options.subcategories, 'code', (s) => s.code, 'All Subcategories');

  const tbody = document.getElementById('rows');
  tbody.innerHTML = '';
  data.items.forEach((i) => {
    const tr = document.createElement('tr');
    const checkTd = state.canManage
      ? `<td><input type="checkbox" data-id="${i.control_id}" ${state.selected.has(i.control_id) ? 'checked' : ''}></td>`
      : '';
    const statusTd = state.canManage ? `<td>${statusBadge(i.status)}</td>` : '';
    tr.innerHTML = `${checkTd}
      <td><div class="cell-code">${i.function_code}</div><div class="cell-name">${i.function_name}</div></td>
      <td><div class="cell-code">${i.category_code}</div><div class="cell-name">${i.category_name}</div></td>
      <td><div class="cell-code">${i.subcategory_code}</div></td>
      <td><div class="control-id">${i.control_id}</div></td>
      <td>${defCell(i.control_text, i.id)}</td>
      ${statusTd}`;
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

  tbody.querySelectorAll('button[data-def-toggle]').forEach((btn) => {
    btn.onclick = () => {
      const id = btn.getAttribute('data-def-toggle');
      const el = document.getElementById(id);
      if (!el) return;
      const expanded = btn.getAttribute('data-expanded') === '1';
      if (expanded) {
        el.textContent = el.getAttribute('data-short');
        btn.textContent = 'Show more';
        btn.setAttribute('data-expanded', '0');
      } else {
        el.textContent = el.getAttribute('data-full');
        btn.textContent = 'Show less';
        btn.setAttribute('data-expanded', '1');
      }
    };
  });

  const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
  document.getElementById('pageMeta').textContent = `Page ${state.page}/${maxPage} • ${state.total} rows`;
}

async function runBulk(path) {
  if (!state.canManage) return;
  if (!state.selected.size) return alert('Select at least one control.');
  await api(path, {
    method: 'POST',
    body: JSON.stringify({ control_ids: Array.from(state.selected), comment: document.getElementById('actionComment').value.trim() }),
  });
  state.selected.clear();
  await loadControls();
}

async function bootstrap() {
  const data = await api('/api/bootstrap');
  document.getElementById('loginCard').hidden = true;
  document.getElementById('main').hidden = false;
  document.getElementById('logoutBtn').hidden = false;
  state.canManage = data.can_manage === true && ["compliance_officer", "risk_officer"].includes(data.me.role_name);
  configureRoleUI();
  document.getElementById('profile').textContent = `${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;
  renderFunctionCards(data.functions);
  showHomeView();
}

async function login() {
  try {
    await api('/api/login', { method: 'POST', body: JSON.stringify({ username: document.getElementById('username').value.trim(), password: document.getElementById('password').value }) });
    await bootstrap();
  } catch (e) {
    document.getElementById('loginErr').textContent = e.message;
  }
}

document.getElementById('loginBtn').onclick = login;
document.getElementById('logoutBtn').onclick = async () => { await api('/api/logout', { method: 'POST' }); location.reload(); };
document.getElementById('backBtn').onclick = showHomeView;
document.getElementById('categoryFilter').onchange = (e) => { state.categoryCode = e.target.value; state.page = 1; loadControls(); };
document.getElementById('subcategoryFilter').onchange = (e) => { state.subcategoryCode = e.target.value; state.page = 1; loadControls(); };
document.getElementById('controlIdFilter').oninput = (e) => { state.controlId = e.target.value.trim(); state.page = 1; loadControls(); };
document.getElementById('search').oninput = (e) => { state.search = e.target.value; state.page = 1; loadControls(); };
document.getElementById('statusFilter').onchange = (e) => { state.status = e.target.value; state.page = 1; loadControls(); };
document.getElementById('sortBy').onchange = (e) => { state.sortBy = e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = (e) => { state.sortDir = e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if (state.page > 1) { state.page -= 1; loadControls(); } };
document.getElementById('next').onclick = () => { const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize)); if (state.page < maxPage) { state.page += 1; loadControls(); } };

document.getElementById('releaseBtn').onclick = () => runBulk('/api/controls/bulk-release');
document.getElementById('hideBtn').onclick = () => runBulk('/api/controls/bulk-hide');
document.getElementById('deleteBtn').onclick = () => runBulk('/api/controls/soft-delete');
document.getElementById('restoreBtn').onclick = () => runBulk('/api/controls/restore');
document.getElementById('deprecateBtn').onclick = () => runBulk('/api/controls/deprecate');

configureRoleUI();
api('/api/bootstrap').then(bootstrap).catch(() => {});

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
  sortBy: 'subcategory_code',
  sortDir: 'asc',
  total: 0,
};

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, credentials: 'include', ...opts });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showHomeView() {
  document.getElementById('homeView').hidden = false;
  document.getElementById('controlView').hidden = true;
}

function showControlView() {
  document.getElementById('homeView').hidden = true;
  document.getElementById('controlView').hidden = false;
}

function setSelection() {
  document.getElementById('selectionTitle').textContent = `${state.functionName} (${state.functionId ? '' : ''})`.replace(' ()','');
  document.getElementById('selectionDef').textContent = state.functionDef;
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
      document.getElementById('categoryFilter').value = '';
      document.getElementById('subcategoryFilter').value = '';
      document.getElementById('controlIdFilter').value = '';
      document.getElementById('search').value = '';
      setSelection();
      showControlView();
      loadControls();
    };
    grid.appendChild(card);
  });
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
    tr.innerHTML = `<td>${i.function_code} — ${i.function_name}</td><td>${i.category_code} — ${i.category_name}</td><td><b>${i.subcategory_code}</b></td><td>${i.subcategory_definition}</td><td>${i.control_code} (${i.control_source})</td>`;
    tbody.appendChild(tr);
  });

  const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
  document.getElementById('pageMeta').textContent = `Page ${state.page}/${maxPage} • ${state.total} rows`;
}

async function bootstrap() {
  const data = await api('/api/bootstrap');
  document.getElementById('loginCard').hidden = true;
  document.getElementById('main').hidden = false;
  document.getElementById('logoutBtn').hidden = false;
  document.getElementById('profile').textContent = `${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;
  renderFunctionCards(data.functions);
  showHomeView();
}

async function login() {
  try {
    await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username: document.getElementById('username').value.trim(), password: document.getElementById('password').value }),
    });
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
document.getElementById('sortBy').onchange = (e) => { state.sortBy = e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = (e) => { state.sortDir = e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if (state.page > 1) { state.page -= 1; loadControls(); } };
document.getElementById('next').onclick = () => { const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize)); if (state.page < maxPage) { state.page += 1; loadControls(); } };

api('/api/bootstrap').then(bootstrap).catch(() => {});

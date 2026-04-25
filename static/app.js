const state = { functionId: null, categoryId: null, page: 1, pageSize: 12, search: '', sortBy: 'subcategory_code', sortDir: 'asc', total: 0 };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, credentials: 'include', ...opts });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showTreeView() {
  document.getElementById('treeView').hidden = false;
  document.getElementById('controlView').hidden = true;
}

function showControlView() {
  document.getElementById('treeView').hidden = true;
  document.getElementById('controlView').hidden = false;
}

function setSelection(title, definition) {
  document.getElementById('selectionTitle').textContent = title;
  document.getElementById('selectionDef').textContent = definition || '';
}

function createExpandNode(title, definition) {
  const node = document.createElement('div');
  node.className = 'tree-node';
  const head = document.createElement('div');
  head.className = 'tree-head';
  head.innerHTML = `<b>${title}</b><span>▾</span>`;
  const def = document.createElement('div');
  def.className = 'def muted';
  def.textContent = definition;
  const children = document.createElement('div');
  children.className = 'children';
  node.append(head, def, children);

  let open = true;
  head.onclick = () => {
    open = !open;
    children.hidden = !open;
    def.hidden = !open;
    head.querySelector('span').textContent = open ? '▾' : '▸';
  };
  return { node, children };
}

function renderTree(tree) {
  const treeRoot = document.getElementById('tree');
  treeRoot.innerHTML = '';

  tree.forEach((fn) => {
    const fnNode = createExpandNode(`${fn.name.toUpperCase()} (${fn.code})`, fn.definition);

    const fnBtn = document.createElement('button');
    fnBtn.textContent = 'Open Function Controls';
    fnBtn.onclick = () => {
      state.functionId = fn.id;
      state.categoryId = null;
      state.page = 1;
      setSelection(`${fn.name} (${fn.code})`, fn.definition);
      showControlView();
      loadControls();
    };
    fnNode.children.appendChild(fnBtn);

    fn.categories.forEach((cat) => {
      const catNode = document.createElement('div');
      catNode.className = 'cat';
      catNode.innerHTML = `<div><b>${cat.name} (${cat.code})</b></div><div class='muted'>${cat.definition}</div>`;

      const catBtn = document.createElement('button');
      catBtn.textContent = 'Open Category Controls';
      catBtn.onclick = () => {
        state.functionId = fn.id;
        state.categoryId = cat.id;
        state.page = 1;
        setSelection(`${cat.name} (${cat.code})`, cat.definition);
        showControlView();
        loadControls();
      };
      catNode.appendChild(catBtn);

      cat.subcategories.forEach((s) => {
        const sub = document.createElement('div');
        sub.className = 'sub';
        sub.textContent = `${s.code}: ${s.definition}`;
        catNode.appendChild(sub);
      });

      fnNode.children.appendChild(catNode);
    });

    treeRoot.appendChild(fnNode.node);
  });
}

async function loadControls() {
  const q = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    search: state.search,
    sort_by: state.sortBy,
    sort_dir: state.sortDir,
  });
  if (state.functionId) q.append('function_id', state.functionId);
  if (state.categoryId) q.append('category_id', state.categoryId);

  const data = await api(`/api/controls?${q.toString()}`);
  state.total = data.total;
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
  renderTree(data.tree);
  showTreeView();
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
document.getElementById('backBtn').onclick = showTreeView;
document.getElementById('search').oninput = (e) => { state.search = e.target.value; state.page = 1; loadControls(); };
document.getElementById('sortBy').onchange = (e) => { state.sortBy = e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = (e) => { state.sortDir = e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if (state.page > 1) { state.page -= 1; loadControls(); } };
document.getElementById('next').onclick = () => { const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize)); if (state.page < maxPage) { state.page += 1; loadControls(); } };

api('/api/bootstrap').then(bootstrap).catch(() => {});

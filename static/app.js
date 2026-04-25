const state = {
  functionId: null,
  categoryId: null,
  page: 1,
  pageSize: 10,
  search: '',
  sortBy: 'subcategory_code',
  sortDir: 'asc',
  total: 0,
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function setSelection(title, definition) {
  document.getElementById('selectionTitle').textContent = title;
  document.getElementById('selectionDef').textContent = definition || '';
}

function makeToggle(headText, definition) {
  const box = document.createElement('div');
  box.className = 'tree-node';
  const head = document.createElement('div');
  head.className = 'tree-head';
  head.innerHTML = `<strong>${headText}</strong><span>▾</span>`;
  const def = document.createElement('div');
  def.className = 'tree-def';
  def.textContent = definition;
  box.append(head, def);
  const child = document.createElement('div');
  child.className = 'children';
  box.appendChild(child);

  let open = true;
  head.onclick = () => {
    open = !open;
    child.style.display = open ? 'block' : 'none';
    def.style.display = open ? 'block' : 'none';
    head.querySelector('span').textContent = open ? '▾' : '▸';
  };
  return { box, child };
}

function renderTree(tree) {
  const root = document.getElementById('tree');
  root.innerHTML = '';

  tree.forEach((fn) => {
    const fnNode = makeToggle(`${fn.name.toUpperCase()} (${fn.code})`, fn.definition);
    fnNode.box.onclick = () => {};
    fnNode.child.addEventListener('click', (e) => e.stopPropagation());

    const fnSelect = document.createElement('button');
    fnSelect.textContent = 'Show Function Controls';
    fnSelect.onclick = (e) => {
      e.stopPropagation();
      state.functionId = fn.id;
      state.categoryId = null;
      state.page = 1;
      setSelection(`${fn.name} (${fn.code})`, fn.definition);
      loadControls();
    };
    fnNode.child.appendChild(fnSelect);

    fn.categories.forEach((cat) => {
      const catEl = document.createElement('div');
      catEl.className = 'cat-node';
      catEl.innerHTML = `<div><b>${cat.name} (${cat.code})</b></div><div class="tree-def">${cat.definition}</div>`;
      const catBtn = document.createElement('button');
      catBtn.textContent = 'Show Category Controls';
      catBtn.onclick = (e) => {
        e.stopPropagation();
        state.functionId = fn.id;
        state.categoryId = cat.id;
        state.page = 1;
        setSelection(`${cat.name} (${cat.code})`, cat.definition);
        loadControls();
      };
      catEl.appendChild(catBtn);

      const subWrap = document.createElement('div');
      cat.subcategories.forEach((s) => {
        const se = document.createElement('div');
        se.className = 'subcat';
        se.textContent = `${s.code}: ${s.definition}`;
        subWrap.appendChild(se);
      });
      catEl.appendChild(subWrap);
      fnNode.child.appendChild(catEl);
    });

    root.appendChild(fnNode.box);
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

  data.items.forEach((item) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.function_code} — ${item.function_name}</td>
      <td>${item.category_code} — ${item.category_name}</td>
      <td><b>${item.subcategory_code}</b></td>
      <td>${item.subcategory_definition}</td>
      <td>${item.control_code} (${item.control_type})</td>
    `;
    tbody.appendChild(tr);
  });

  const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
  document.getElementById('pageMeta').textContent = `Page ${state.page}/${maxPage} • ${state.total} controls`;
}

async function bootstrap() {
  const data = await api('/api/bootstrap');
  document.getElementById('loginCard').hidden = true;
  document.getElementById('main').hidden = false;
  document.getElementById('logoutBtn').hidden = false;

  document.getElementById('profile').textContent = `${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;
  renderTree(data.tree);
}

async function login() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  try {
    await api('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) });
    await bootstrap();
  } catch (e) {
    document.getElementById('loginErr').textContent = e.message;
  }
}

document.getElementById('loginBtn').onclick = login;
document.getElementById('search').oninput = (e) => { state.search = e.target.value; state.page = 1; loadControls(); };
document.getElementById('sortBy').onchange = (e) => { state.sortBy = e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = (e) => { state.sortDir = e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if (state.page > 1) { state.page -= 1; loadControls(); } };
document.getElementById('next').onclick = () => {
  const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
  if (state.page < maxPage) { state.page += 1; loadControls(); }
};
document.getElementById('logoutBtn').onclick = async () => { await api('/api/logout', { method: 'POST' }); location.reload(); };

api('/api/bootstrap').then(bootstrap).catch(() => {});

const state = { categoryId:null, page:1, pageSize:10, search:'', sortBy:'code', sortDir:'asc', total:0 };

async function api(path, opts={}) {
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, credentials:'include', ...opts});
  const data = await res.json();
  if(!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

async function login(){
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  try { await api('/api/login',{method:'POST',body:JSON.stringify({username,password})}); await bootstrap(); }
  catch(e){ document.getElementById('loginErr').textContent = e.message; }
}

async function bootstrap(){
  const data = await api('/api/bootstrap');
  document.getElementById('loginCard').hidden = true;
  document.getElementById('main').hidden = false;
  document.getElementById('logoutBtn').hidden = false;
  document.getElementById('profile').textContent = `${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;

  const tree = document.getElementById('tree'); tree.innerHTML='';
  data.functions.forEach(fn => {
    const fnEl = document.createElement('div'); fnEl.className='tree-fn'; fnEl.textContent=`${fn.code} — ${fn.name}`; tree.appendChild(fnEl);
    data.categories.filter(c => c.function_code===fn.code).forEach(cat => {
      const c = document.createElement('div'); c.className='cat'; c.textContent=`${cat.code} ${cat.name}`;
      c.onclick = () => { state.categoryId = cat.id; state.page=1; document.querySelectorAll('.cat').forEach(x=>x.classList.remove('active')); c.classList.add('active'); loadControls(); };
      tree.appendChild(c);
    });
  });
}

async function loadControls(){
  if(!state.categoryId) return;
  const q = new URLSearchParams({category_id:state.categoryId, page:state.page, page_size:state.pageSize, search:state.search, sort_by:state.sortBy, sort_dir:state.sortDir});
  const data = await api(`/api/controls?${q.toString()}`);
  state.total = data.total;
  const tbody = document.getElementById('rows'); tbody.innerHTML='';
  data.items.forEach(i => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><b>${i.code}</b></td><td>${i.statement}</td>`;
    tbody.appendChild(tr);
  });
  const maxPage = Math.max(1, Math.ceil(state.total/state.pageSize));
  document.getElementById('pageMeta').textContent = `Page ${state.page}/${maxPage} • ${state.total} controls`;
}

document.getElementById('loginBtn').onclick = login;
document.getElementById('search').oninput = e => { state.search=e.target.value; state.page=1; loadControls(); };
document.getElementById('sortBy').onchange = e => { state.sortBy=e.target.value; loadControls(); };
document.getElementById('sortDir').onchange = e => { state.sortDir=e.target.value; loadControls(); };
document.getElementById('prev').onclick = () => { if(state.page>1){state.page--; loadControls();} };
document.getElementById('next').onclick = () => { const maxPage=Math.max(1,Math.ceil(state.total/state.pageSize)); if(state.page<maxPage){state.page++; loadControls();} };
document.getElementById('logoutBtn').onclick = async () => { await api('/api/logout',{method:'POST'}); location.reload(); };

api('/api/bootstrap').then(bootstrap).catch(()=>{});

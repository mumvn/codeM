const state = { functionId:null,functionName:'',functionDef:'',page:1,pageSize:12,categoryCode:'',subcategoryCode:'',controlId:'',search:'',status:'',sortBy:'control_id',sortDir:'asc',total:0,canManage:false,isProductManager:false,canDashboard:false,selected:new Set() };
const charts = { pie:null, bar:null, trend:null };

async function api(path, opts={}) { const r=await fetch(path,{headers:{'Content-Type':'application/json'},credentials:'include',...opts}); const d=await r.json(); if(!r.ok) throw new Error(d.error||'Request failed'); return d; }
const showView=id=>['homeView','controlView','dashboardView','regulationView'].forEach(v=>document.getElementById(v).hidden=v!==id);

function statusBadge(s){const m={released:'Released / Visible',hidden:'Hidden',soft_deleted:'Soft Deleted',deprecated:'Deprecated'};return `<span class="badge badge-${s}">${m[s]||s}</span>`}
function configureRoleUI(){
  document.querySelectorAll('.col-select, .col-status').forEach(el=>el.style.display=state.canManage?'':'none');
  document.getElementById('managePanel').hidden=!state.canManage;
  document.getElementById('selectHead').hidden=!state.canManage;
  document.getElementById('statusHead').hidden=!state.canManage;
  document.getElementById('statusFilter').hidden=!state.canManage;
  document.querySelectorAll('.col-pm-status, .col-pm-comment').forEach(el=>el.style.display=state.isProductManager?'':'none');
  document.getElementById('pmStatusHead').hidden=!state.isProductManager;
  document.getElementById('pmCommentHead').hidden=!state.isProductManager;
  document.getElementById('dashboardBtn').hidden=!state.canDashboard;
  document.getElementById('regulationBtn').hidden=!state.canManage;
}

function fillSelectOptions(el, options, key, label, placeholder){const curr=el.value; el.innerHTML=`<option value="">${placeholder}</option>`; options.forEach(o=>{const op=document.createElement('option'); op.value=o[key]; op.textContent=label(o); el.appendChild(op)}); if([...el.options].some(o=>o.value===curr)) el.value=curr;}

function renderFunctionCards(functions){const g=document.getElementById('functionGrid'); g.innerHTML=''; functions.forEach(fn=>{const b=document.createElement('button'); b.className='function-card'; b.innerHTML=`<div class="function-code">${fn.name.toUpperCase()} (${fn.code})</div><div class="function-def">${fn.definition}</div>`; b.onclick=()=>{state.functionId=fn.id; state.functionName=`${fn.name} (${fn.code})`; state.functionDef=fn.definition; state.page=1; state.categoryCode=state.subcategoryCode=state.controlId=state.search=state.status=''; state.selected.clear(); ['categoryFilter','subcategoryFilter','controlIdFilter','search','statusFilter'].forEach(id=>{const el=document.getElementById(id); if(el) el.value='';}); document.getElementById('selectionTitle').textContent=state.functionName; document.getElementById('selectionDef').textContent=state.functionDef; showView('controlView'); loadControls();}; g.appendChild(b);});}

function defCell(t){if(!t) return ''; const lim=170; return t.length<=lim?`<div class="definition-text">${t}</div>`:`<div class="definition-text">${t.slice(0,lim)}…</div><span class="muted">(use search to inspect full text)</span>`;}

async function updateMyStatus(cid){const sel=document.getElementById(`pm-stat-${cid}`); const com=document.getElementById(`pm-com-${cid}`); await api('/api/pm/status',{method:'POST',body:JSON.stringify({control_id:cid,status:sel.value,status_comment:com.value})}); await loadControls();}

async function loadControls(){
  const q=new URLSearchParams({function_id:state.functionId,page:state.page,page_size:state.pageSize,category_code:state.categoryCode,subcategory_code:state.subcategoryCode,control_id:state.controlId,search:state.search,status:state.status,sort_by:state.sortBy,sort_dir:state.sortDir});
  const data=await api(`/api/controls?${q.toString()}`); state.total=data.total;
  fillSelectOptions(document.getElementById('categoryFilter'), data.filter_options.categories,'code',c=>`${c.code} — ${c.name}`,'All Categories');
  fillSelectOptions(document.getElementById('subcategoryFilter'), data.filter_options.subcategories,'code',s=>s.code,'All Subcategories');
  const body=document.getElementById('rows'); body.innerHTML='';
  data.items.forEach(i=>{const tr=document.createElement('tr'); const check=state.canManage?`<td><input type="checkbox" data-id="${i.control_id}" ${state.selected.has(i.control_id)?'checked':''}></td>`:''; const stat=state.canManage?`<td>${statusBadge(i.status)}</td>`:''; const pmSt=state.isProductManager?`<td><select id="pm-stat-${i.control_id}"><option value="open" ${(!i.pm_status||i.pm_status==='open')?'selected':''}>Open</option><option value="in_progress" ${i.pm_status==='in_progress'?'selected':''}>In Progress</option><option value="closed" ${i.pm_status==='closed'?'selected':''}>Closed</option></select></td>`:''; const pmCom=state.isProductManager?`<td><input id="pm-com-${i.control_id}" value="${i.pm_status_comment||''}" placeholder="comment"/><div class="muted small">${i.pm_last_updated_at||'Never updated'}</div><button class="link-btn" data-save-pm="${i.control_id}">Save</button></td>`:''; tr.innerHTML=`${check}<td><div class="cell-code">${i.function_code}</div><div class="cell-name">${i.function_name}</div></td><td><div class="cell-code">${i.category_code}</div><div class="cell-name">${i.category_name}</div></td><td><div class="cell-code">${i.subcategory_code}</div></td><td><div class="control-id">${i.control_id}</div></td><td>${defCell(i.control_text)}</td>${pmSt}${pmCom}${stat}`; body.appendChild(tr);});
  if(state.canManage){body.querySelectorAll('input[type="checkbox"]').forEach(cb=>cb.onchange=e=>{const id=e.target.getAttribute('data-id'); e.target.checked?state.selected.add(id):state.selected.delete(id);});}
  if(state.isProductManager){body.querySelectorAll('button[data-save-pm]').forEach(btn=>btn.onclick=()=>updateMyStatus(btn.getAttribute('data-save-pm')));}
  const max=Math.max(1,Math.ceil(state.total/state.pageSize)); document.getElementById('pageMeta').textContent=`Page ${state.page}/${max} • ${state.total} rows`;
}

async function runBulk(path){ if(!state.canManage) return; if(!state.selected.size) return alert('Select controls first.'); await api(path,{method:'POST',body:JSON.stringify({control_ids:Array.from(state.selected),comment:document.getElementById('actionComment').value.trim()})}); state.selected.clear(); await loadControls(); }

function destroyCharts(){ Object.keys(charts).forEach(k=>{if(charts[k]) {charts[k].destroy(); charts[k]=null;}}); }

function renderTimeline(rows){
  const wrap=document.getElementById('timelineRows'); wrap.innerHTML='';
  rows.forEach(r=>{const row=document.createElement('div'); row.className='timeline-row'; row.innerHTML=`<div class='tl-name'>${r.product_manager}</div><div class='tl-bar'><span style='width:${r.completion_pct}%;'></span></div><div class='tl-meta'>${r.completion_pct}% · stale ${r.overdue_or_stale}</div>`; wrap.appendChild(row);});
}

async function loadDashboard(){
  const q=new URLSearchParams({pm_username:document.getElementById('dashPm').value.trim(),function_id:document.getElementById('dashFunction').value,category_code:document.getElementById('dashCategory').value,subcategory_code:document.getElementById('dashSubcategory').value,status:document.getElementById('dashStatus').value,start_date:document.getElementById('dashStart').value,end_date:document.getElementById('dashEnd').value});
  const data=await api(`/api/dashboard?${q.toString()}`);

  fillSelectOptions(document.getElementById('dashCategory'), data.filter_options.categories, 'code', c=>`${c.code} — ${c.name}`, 'All Categories');
  fillSelectOptions(document.getElementById('dashSubcategory'), data.filter_options.subcategories, 'code', s=>s.code, 'All Subcategories');

  const s=data.summary;
  document.getElementById('summaryCards').innerHTML=`
    <button class='sum-card' data-kpi='total_controls'><b>Total controls</b><span>${s.total_controls}</span></button>
    <button class='sum-card' data-kpi='total_pm'><b>Total PMs</b><span>${s.total_product_managers}</span></button>
    <button class='sum-card' data-kpi='open'><b>Open</b><span>${s.overall_open}</span></button>
    <button class='sum-card' data-kpi='in_progress'><b>In Progress</b><span>${s.overall_in_progress}</span></button>
    <button class='sum-card' data-kpi='closed'><b>Closed</b><span>${s.overall_closed}</span></button>
    <button class='sum-card' data-kpi='completion'><b>Completion %</b><span>${s.overall_completion_pct}%</span></button>
    <button class='sum-card' data-kpi='stale'><b>Not updated recently</b><span>${s.stale_controls}</span></button>`;

  destroyCharts();
  const pieCtx=document.getElementById('statusPie');
  charts.pie=new Chart(pieCtx,{type:'doughnut',data:{labels:['Open','In Progress','Closed'],datasets:[{data:[s.overall_open,s.overall_in_progress,s.overall_closed],backgroundColor:['#f59e0b','#3b82f6','#22c55e']}]},options:{plugins:{legend:{position:'bottom'}},onClick:(_,els)=>{if(!els.length)return;const lbl=['open','in_progress','closed'][els[0].index];document.getElementById('dashStatus').value=lbl;loadDashboard();}}});

  const pmLabels=data.per_manager.map(r=>r.product_manager);
  charts.bar=new Chart(document.getElementById('pmBar'),{type:'bar',data:{labels:pmLabels,datasets:[{label:'Open',data:data.per_manager.map(r=>r.open),backgroundColor:'#f59e0b'},{label:'In Progress',data:data.per_manager.map(r=>r.in_progress),backgroundColor:'#3b82f6'},{label:'Closed',data:data.per_manager.map(r=>r.closed),backgroundColor:'#22c55e'}]},options:{responsive:true,scales:{x:{stacked:true},y:{stacked:true}},onClick:(_,els)=>{if(!els.length)return;document.getElementById('dashPm').value=pmLabels[els[0].index];loadDashboard();}}});

  charts.trend=new Chart(document.getElementById('trendLine'),{type:'line',data:{labels:data.trend.map(t=>t.date),datasets:[{label:'Open',data:data.trend.map(t=>t.open),borderColor:'#f59e0b'},{label:'In Progress',data:data.trend.map(t=>t.in_progress),borderColor:'#3b82f6'},{label:'Closed',data:data.trend.map(t=>t.closed),borderColor:'#22c55e'}]},options:{plugins:{legend:{position:'bottom'}}}});

  renderTimeline(data.per_manager);
  const rows=document.getElementById('dashRows'); rows.innerHTML=''; data.per_manager.forEach(m=>{const tr=document.createElement('tr'); tr.innerHTML=`<td>${m.product_manager}</td><td>${m.total}</td><td>${m.open}</td><td>${m.in_progress}</td><td>${m.closed}</td><td>${m.completion_pct}%</td><td>${m.overdue_or_stale}</td>`; rows.appendChild(tr);});

  document.querySelectorAll('.sum-card').forEach(card=>{card.onclick=()=>{const k=card.getAttribute('data-kpi'); if(['open','in_progress','closed'].includes(k)){document.getElementById('dashStatus').value=k; loadDashboard();}}});
}

function resetDashboardFilters(){ ['dashPm','dashFunction','dashCategory','dashSubcategory','dashStatus','dashStart','dashEnd'].forEach(id=>document.getElementById(id).value=''); loadDashboard(); }

async function loadRegulation(){
  const q=new URLSearchParams({search:document.getElementById('regSearch').value.trim(),article:document.getElementById('regArticle').value,domain:document.getElementById('regDomain').value,status:document.getElementById('regStatus').value,responsible_party:document.getElementById('regResponsible').value.trim(),risk_impact:document.getElementById('regRisk').value});
  const data=await api(`/api/regulations/ai-dora?${q.toString()}`);
  document.getElementById('regMeta').innerHTML=`${data.regulation_name} · <a href="${data.source_url}" target="_blank">Source</a>`;
  fillSelectOptions(document.getElementById('regArticle'), data.filter_options.articles.map(a=>({v:a})), 'v', x=>x.v, 'All Articles');
  fillSelectOptions(document.getElementById('regDomain'), data.filter_options.domains.map(d=>({v:d})), 'v', x=>x.v, 'All Domains');
  const s=data.summary;
  document.getElementById('regSummary').innerHTML=`<div class='sum-card'><b>Total requirements</b><span>${s.total_requirements}</span></div>
  <div class='sum-card'><b>Open</b><span>${s.by_status.open}</span></div><div class='sum-card'><b>In Progress</b><span>${s.by_status.in_progress}</span></div><div class='sum-card'><b>Closed</b><span>${s.by_status.closed}</span></div>`;
  const rows=document.getElementById('regRows'); rows.innerHTML='';
  data.items.forEach(r=>{const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.requirement_id}</td><td>${r.article_reference}</td><td>${r.control_domain}</td><td><b>${r.requirement_title}</b><div class='muted small'>${r.requirement_summary}</div><div class='muted small'>${r.source_excerpt}</div></td><td>${r.responsible_party||''}</td><td>${r.risk_impact||''}</td><td><select data-rid="${r.requirement_id}" data-comments-id="c-${r.requirement_id}"><option value="open" ${r.status==='open'?'selected':''}>Open</option><option value="in_progress" ${r.status==='in_progress'?'selected':''}>In Progress</option><option value="closed" ${r.status==='closed'?'selected':''}>Closed</option></select></td><td>${r.evidence_required||''}<textarea id="c-${r.requirement_id}" placeholder="comments">${r.comments||''}</textarea><button class="link-btn" data-save-reg="${r.requirement_id}">Save</button></td>`; rows.appendChild(tr);});
  rows.querySelectorAll('button[data-save-reg]').forEach(btn=>btn.onclick=async()=>{const rid=btn.getAttribute('data-save-reg');const sel=rows.querySelector(`select[data-rid="${rid}"]`);const comments=document.getElementById(`c-${rid}`).value;await api('/api/regulations/ai-dora/status',{method:'POST',body:JSON.stringify({requirement_id:rid,status:sel.value,comments})});await loadRegulation();});
}

async function bootstrap(){
  const data=await api('/api/bootstrap');
  document.getElementById('loginCard').hidden=true; document.getElementById('main').hidden=false; document.getElementById('logoutBtn').hidden=false;
  state.canManage=data.can_manage===true && ['compliance_officer','risk_officer'].includes(data.me.role_name);
  state.isProductManager=data.is_product_manager===true;
  state.canDashboard=data.can_dashboard===true && state.canManage;
  configureRoleUI();
  document.getElementById('profile').textContent=`${data.me.username} | ${data.me.role_name} | ${data.me.functional_group} | access L${data.me.access_level}`;
  renderFunctionCards(data.functions);
  fillSelectOptions(document.getElementById('dashFunction'), data.functions, 'id', f=>`${f.code} — ${f.name}`, 'All Functions');
  if (location.pathname.includes('ai-dora-regulation') || location.pathname.includes('/regulations/eu-ai-dora')) {
    showView('regulationView'); loadRegulation();
  } else {
    showView('homeView');
  }
}

async function login(){ try{ await api('/api/login',{method:'POST',body:JSON.stringify({username:document.getElementById('username').value.trim(),password:document.getElementById('password').value})}); await bootstrap(); }catch(e){ document.getElementById('loginErr').textContent=e.message; } }

// bindings

document.getElementById('loginBtn').onclick=login;
document.getElementById('logoutBtn').onclick=async()=>{await api('/api/logout',{method:'POST'});location.reload();};
document.getElementById('backBtn').onclick=()=>showView('homeView');
document.getElementById('dashboardBtn').onclick=async()=>{showView('dashboardView');await loadDashboard();};
document.getElementById('dashBackBtn').onclick=()=>showView('homeView');
document.getElementById('dashApply').onclick=loadDashboard;
document.getElementById('dashReset').onclick=resetDashboardFilters;
document.getElementById('regulationBtn').onclick=async()=>{showView('regulationView');await loadRegulation();};
document.getElementById('regBackBtn').onclick=()=>showView('homeView');
document.getElementById('regApply').onclick=loadRegulation;

document.getElementById('categoryFilter').onchange=e=>{state.categoryCode=e.target.value;state.page=1;loadControls();};
document.getElementById('subcategoryFilter').onchange=e=>{state.subcategoryCode=e.target.value;state.page=1;loadControls();};
document.getElementById('controlIdFilter').oninput=e=>{state.controlId=e.target.value.trim();state.page=1;loadControls();};
document.getElementById('search').oninput=e=>{state.search=e.target.value;state.page=1;loadControls();};
document.getElementById('statusFilter').onchange=e=>{state.status=e.target.value;state.page=1;loadControls();};
document.getElementById('sortBy').onchange=e=>{state.sortBy=e.target.value;loadControls();};
document.getElementById('sortDir').onchange=e=>{state.sortDir=e.target.value;loadControls();};
document.getElementById('prev').onclick=()=>{if(state.page>1){state.page-=1;loadControls();}};
document.getElementById('next').onclick=()=>{const max=Math.max(1,Math.ceil(state.total/state.pageSize));if(state.page<max){state.page+=1;loadControls();}};

document.getElementById('releaseBtn').onclick=()=>runBulk('/api/controls/bulk-release');
document.getElementById('hideBtn').onclick=()=>runBulk('/api/controls/bulk-hide');
document.getElementById('deleteBtn').onclick=()=>runBulk('/api/controls/soft-delete');
document.getElementById('restoreBtn').onclick=()=>runBulk('/api/controls/restore');
document.getElementById('deprecateBtn').onclick=()=>runBulk('/api/controls/deprecate');

configureRoleUI();
api('/api/bootstrap').then(bootstrap).catch(()=>{});

const state = { functionId:null,functionName:'',functionDef:'',page:1,pageSize:12,categoryCode:'',subcategoryCode:'',controlId:'',search:'',status:'',sortBy:'control_id',sortDir:'asc',total:0,canManage:false,isProductManager:false,canDashboard:false,selected:new Set(),regPage:1,regPageSize:25,regSelected:new Set(),regTotal:0,regArticleId:'' };
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
  document.getElementById('regulationBtn').hidden=false;
  document.getElementById('regSelectHead').hidden=!state.canManage;
  document.getElementById('regSelectAll').hidden=!state.canManage;
  document.getElementById('regReleaseSelected').hidden=!state.canManage;
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
  const overview = await api('/api/regulation-overview');
  const q=new URLSearchParams({search:document.getElementById('regSearch').value.trim(),domain:document.getElementById('regDomain').value,page:state.regPage,page_size:state.regPageSize});
  const data=await api(`/api/regulation-articles?${q.toString()}`);
  state.regTotal=data.total;
  document.getElementById('regMeta').innerHTML=`${overview.regulation_name} · <a href="${overview.source_url}" target="_blank">EUR-Lex Source</a>`;
  const s=overview.summary;
  document.getElementById('regOverviewCards').innerHTML=`<div class='sum-card'><b>Total chapters</b><span>${s.total_chapters}</span></div><div class='sum-card'><b>Total articles</b><span>${s.total_articles}</span></div><div class='sum-card'><b>Total obligations</b><span>${s.total_obligations}</span></div><div class='sum-card'><b>High-risk obligations</b><span>${s.high_risk_obligations}</span></div><div class='sum-card'><b>Published requirements</b><span>${s.published_requirements}</span></div><div class='sum-card'><b>Pending review</b><span>${s.pending_review}</span></div><div class='sum-card'><b>Evidence pending</b><span>${s.evidence_pending}</span></div><div class='sum-card'><b>Evidence completed</b><span>${s.evidence_completed}</span></div>`;
  document.getElementById('regChapterNav').innerHTML=overview.chapters.map(c=>`<span class='badge'>Chapter ${c.chapter_number}: ${c.chapter_title} (${c.article_count})</span>`).join(' ');
  fillSelectOptions(document.getElementById('regDomain'), data.filter_options.domains.map(d=>({v:d})), 'v', x=>x.v, 'All Domains');
  const rows=document.getElementById('regRows'); rows.innerHTML='';
  data.items.forEach(r=>{const selectCell=state.canManage?`<td><input type="checkbox" data-aid="${r.article_id}" ${state.regSelected.has(r.article_id)?'checked':''}></td>`:''; const tr=document.createElement('tr'); tr.innerHTML=`${selectCell}<td><button class="link-btn" data-open-article="${r.article_id}">${r.article_reference}</button></td><td>${r.title}</td><td>${r.control_domain||''}</td>`; rows.appendChild(tr);});
  rows.querySelectorAll('input[type="checkbox"]').forEach(cb=>cb.onchange=e=>{const id=e.target.getAttribute('data-aid'); e.target.checked?state.regSelected.add(id):state.regSelected.delete(id);});
  rows.querySelectorAll('button[data-open-article]').forEach(btn=>btn.onclick=()=>openRegArticle(btn.getAttribute('data-open-article')));
  const max=Math.max(1,Math.ceil(state.regTotal/state.regPageSize)); document.getElementById('regMetaPage').textContent=`Page ${state.regPage}/${max} • ${state.regTotal} articles`;
}

async function openRegArticle(articleId){
  state.regArticleId=articleId;
  const d=await api(`/api/regulation-article-detail?article_id=${encodeURIComponent(articleId)}`);
  const a=d.article;
  document.getElementById('regArticleDetail').innerHTML=`<h4>${a.article_reference} — ${a.title}</h4><p>${a.summary}</p><p><b>Why it matters:</b> ${a.why_it_matters}</p><p><b>Who is affected:</b> ${a.affected_roles}</p><p><b>Required organizational actions:</b> ${a.required_org_actions}</p><p><b>Required technical actions:</b> ${a.required_technical_actions}</p><p><b>Required evidence:</b> ${a.required_evidence}</p><p><b>Review frequency:</b> ${a.review_frequency}</p><p><b>Risk if not implemented:</b> ${a.risk_if_not_implemented}</p>`;
  const optsManager = `<option value='draft'>Draft</option><option value='under_review'>Under Review</option><option value='approved'>Approved</option><option value='released_visible'>Released / Visible</option><option value='evidence_pending'>Evidence Pending</option><option value='evidence_provided'>Evidence Provided</option><option value='deprecated'>Deprecated</option>`;
  const optsPm = `<option value='reviewed_by_product_manager'>Reviewed by Product Manager</option><option value='committed'>Committed</option>`;
  document.getElementById('regObligations').innerHTML=d.obligations.map(o=>{const editable=(state.canManage||state.isProductManager);const opts=state.canManage?optsManager:optsPm;const ctl=editable?`<select id='st-${o.obligation_id}'>${opts}</select><input id='cm-${o.obligation_id}' placeholder='comments' value='${o.comments||''}'/><button class='link-btn' data-save-ob='${o.obligation_id}'>Save Workflow</button>`:`<p class='muted'>Read-only</p>`;return `<div class='card'><b>${o.obligation_id}</b> · ${o.source_reference}<p>${o.obligation_summary}</p><p><b>Mandatory action:</b> ${o.mandatory_action}</p><p><b>Responsible:</b> ${o.responsible_party}</p><p><b>Evidence:</b> ${o.evidence_required}</p><p><b>Guidance:</b> ${o.implementation_guidance}</p><p><b>Risk:</b> ${o.risk_level}</p><p><b>Status:</b> ${o.status}</p>${ctl}</div>`;}).join('');
  d.obligations.forEach(o=>{const el=document.getElementById(`st-${o.obligation_id}`); if(el){ if([...(el.options||[])].some(x=>x.value===o.status)) el.value=o.status; else el.selectedIndex=0; }});
  document.querySelectorAll('button[data-save-ob]').forEach(btn=>btn.onclick=async()=>{const oid=btn.getAttribute('data-save-ob');await api('/api/regulation-obligations/status',{method:'POST',body:JSON.stringify({obligation_id:oid,status:document.getElementById(`st-${oid}`).value,comments:document.getElementById(`cm-${oid}`).value})});openRegArticle(articleId);loadRegulation();});
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
document.getElementById('regSelectAll').onclick=async()=>{const d=await api('/api/regulation-articles?page=1&page_size=200'); d.items.forEach(x=>state.regSelected.add(x.article_id)); loadRegulation();};
document.getElementById('regReleaseSelected').onclick=async()=>{if(!state.regSelected.size) return; await api('/api/regulation-articles/bulk-release',{method:'POST',body:JSON.stringify({article_ids:Array.from(state.regSelected)})}); state.regSelected.clear(); loadRegulation();};
document.getElementById('regPrev').onclick=()=>{if(state.regPage>1){state.regPage--;loadRegulation();}};
document.getElementById('regNext').onclick=()=>{const max=Math.max(1,Math.ceil(state.regTotal/state.regPageSize));if(state.regPage<max){state.regPage++;loadRegulation();}};

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

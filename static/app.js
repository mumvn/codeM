async function api(path, method='GET', body){const res=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,credentials:'include'}); return res.json();}
async function load(){const d=await api('/api/bootstrap'); const open=d.issues.filter(i=>!['CLOSED'].includes(i.status)).length; document.getElementById('dash').textContent=JSON.stringify({properties:d.properties.length,totalIssues:d.issues.length,openIssues:open,vendors:d.vendors.length,documents:d.documents.length,costRecords:d.costs.length},null,2)}
document.getElementById('login').onclick=async()=>{await api('/api/login','POST',{email:email.value,password:password.value}); await load();};
document.getElementById('addProperty').onclick=async()=>{await api('/api/properties','POST',{name:pname.value}); await load();};
document.getElementById('addIssue').onclick=async()=>{await api('/api/issues','POST',{title:ititle.value}); await load();};
document.getElementById('addDoc').onclick=async()=>{await api('/api/documents','POST',{name:dname.value,document_type:'invoice'}); await load();};
document.getElementById('addCost').onclick=async()=>{await api('/api/costs','POST',{amount:Number(camt.value),category:'maintenance expense',tax_relevant:true}); await load();};
load();

import * as THREE from 'three';

const PLANETS = [
  ['Mercury', 1.2, '#b2a59c', 'Mercury is closest to the Sun.'],
  ['Venus', 1.8, '#e1bd7a', 'Venus is very hot.'],
  ['Earth', 2.0, '#3b8fff', 'Earth is our home.'],
  ['Mars', 1.5, '#d66b47', 'Mars is the red planet.'],
  ['Jupiter', 3.8, '#d9b48c', 'Jupiter is the biggest planet.'],
  ['Saturn', 3.4, '#ddc78f', 'Saturn has beautiful rings.'],
  ['Uranus', 2.6, '#73d6d5', 'Uranus is blue-green.'],
  ['Neptune', 2.5, '#4a7bff', 'Neptune is very far away.'],
];

const canvas = document.getElementById('game');
const overlay = document.getElementById('overlay');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(innerWidth, innerHeight);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 2000);
camera.position.set(0, 5, 24);
scene.add(new THREE.AmbientLight(0xffffff, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.1); sun.position.set(20, 20, 20); scene.add(sun);
const sunMesh = new THREE.Mesh(new THREE.SphereGeometry(5, 24, 24), new THREE.MeshStandardMaterial({ color:'#ffd94d', emissive:'#ffb300', emissiveIntensity:0.6 }));
sunMesh.position.set(0, 0, 0);
scene.add(sunMesh);

const starGeo = new THREE.BufferGeometry();
const starPos = new Float32Array(1200 * 3);
for (let i = 0; i < 1200; i++) { starPos[i*3]=(Math.random()-0.5)*500; starPos[i*3+1]=(Math.random()-0.5)*300; starPos[i*3+2]=(Math.random()-0.5)*500; }
starGeo.setAttribute('position', new THREE.BufferAttribute(starPos,3));
const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: '#fff', size: 0.8 }));
stars.visible = false; scene.add(stars);

function createRocket() {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.8,0.9,4,16), new THREE.MeshStandardMaterial({color:'#f4f4f4'})));
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.8,1.3,16), new THREE.MeshStandardMaterial({color:'#ff5f7f'})); nose.position.y = 2.6; g.add(nose);
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.2,12,12), new THREE.MeshStandardMaterial({color:'#222'})); face.position.set(0.25,0.8,0.85); g.add(face);
  return g;
}
function createPlane(color){ const g=new THREE.Group(); g.add(new THREE.Mesh(new THREE.BoxGeometry(2.2,.5,.5),new THREE.MeshStandardMaterial({color}))); const wing=new THREE.Mesh(new THREE.BoxGeometry(1,.1,3),new THREE.MeshStandardMaterial({color:'#fff'})); wing.position.y=-0.1; g.add(wing); return g; }

const rocket = createRocket(); rocket.position.set(0,2,0); scene.add(rocket);
const pad = new THREE.Mesh(new THREE.CylinderGeometry(4,4,0.5,24), new THREE.MeshStandardMaterial({color:'#48b05a'})); pad.position.set(0,0,0); scene.add(pad);
const airplanes = [createPlane('#ff9f43'), createPlane('#5bd0ff'), createPlane('#ff7af3')]; airplanes.forEach((p,i)=>{p.position.set(-35+i*15,18+i*3,-30-i*20); scene.add(p);});

const planets = PLANETS.map((p,i)=>{
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(p[1],24,24), new THREE.MeshStandardMaterial({color:p[2]}));
  mesh.position.set((i+1)*20, 5 + Math.sin(i)*2, -20 - i*10); scene.add(mesh);
  if (p[0] === 'Saturn') { const ring = new THREE.Mesh(new THREE.TorusGeometry(p[1]+1.1,.2,12,36), new THREE.MeshStandardMaterial({color:'#f0dfaa'})); ring.rotation.x=1.2; mesh.add(ring); }
  if (p[0] === 'Earth') { const land = new THREE.Mesh(new THREE.SphereGeometry(p[1]*1.01,24,24), new THREE.MeshStandardMaterial({color:'#35cc6b', wireframe:true})); mesh.add(land); }
  return { name:p[0], fact:p[3], mesh };
});

let state = 'welcome', countdown = 10, lastTick = 0, phaseTime = 0, planetIndex = 0, landingMsg = '', speedState='Good';
let landingX = 0, landingY = 16;
let orbitAngle = 0, orbitPlanetIndex = 0, orbitPaused = false, orbitSpeed = 1, orbitRadius = 6;
const key = {};
addEventListener('keydown', e=> key[e.key] = true);
addEventListener('keyup', e=> key[e.key] = false);

function ui(html){ overlay.innerHTML = html; }
function welcome(){ ui(`<div class="panel"><h1 class="big">Little Rocket Explorer 🚀</h1><p class="small">Let's explore space!</p><button id="startBtn">Start Adventure</button></div>`); document.getElementById('startBtn').onclick=()=>{state='countdown'; lastTick=performance.now();}; }
welcome();

function landingControls(){
  return `<div class="controls"><button data-k="ArrowLeft">⬅️</button><button data-k="ArrowUp">Slow ⬆️</button><button data-k="ArrowRight">➡️</button><div></div><button data-k="ArrowDown">Down ⬇️</button><div></div></div>`;
}

overlay.addEventListener('pointerdown',e=>{ const k=e.target.dataset.k; if(k) key[k]=true; });
overlay.addEventListener('pointerup',e=>{ const k=e.target.dataset.k; if(k) key[k]=false; });
overlay.addEventListener('pointercancel',()=>{ Object.keys(key).forEach(k=> key[k]=false); });

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function spaceControls(){
  return `<div class="hud"><div class="badge">Planet: ${planets[orbitPlanetIndex].name}</div><div class="badge">${planets[orbitPlanetIndex].fact}</div></div>
  <div class="controls" style="grid-template-columns:repeat(3,minmax(96px,130px));">
    <button id="pauseBtn">${orbitPaused ? 'Resume' : 'Pause'}</button>
    <button id="slowBtn">Slower</button>
    <button id="fastBtn">Faster</button>
  </div>
  <div class="top-message">Tap a planet to orbit it! ☀️ Sun stays in view.</div>`;
}

function bindSpaceButtons(){
  const p=document.getElementById('pauseBtn'); const sl=document.getElementById('slowBtn'); const f=document.getElementById('fastBtn');
  if(p) p.onclick=()=>{ orbitPaused=!orbitPaused; };
  if(sl) sl.onclick=()=>{ orbitSpeed=Math.max(0.4, orbitSpeed-0.2); };
  if(f) f.onclick=()=>{ orbitSpeed=Math.min(3, orbitSpeed+0.2); };
}

canvas.addEventListener('pointerdown', (event)=>{
  if(state!=='space') return;
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(planets.map(p=>p.mesh));
  if(hits.length){
    const mesh = hits[0].object;
    const idx = planets.findIndex(p=>p.mesh===mesh);
    if(idx>=0){ orbitPlanetIndex = idx; orbitAngle = 0; }
  }
});


function animate(t){
  requestAnimationFrame(animate);
  phaseTime += 0.016;

  airplanes.forEach((p,i)=>{ p.position.x = ((phaseTime*7 + i*20)%90)-45; });
  planets.forEach((p,i)=> p.mesh.rotation.y += 0.003 + i*0.0002);

  if(state==='countdown'){
    if (t - lastTick > 1000) { countdown--; lastTick = t; if (countdown < 0) { state='launch'; phaseTime=0; ui(''); } }
    ui(`<div class="panel"><div class="big">${countdown>=1?countdown:'Blast Off!'}</div><p class="small">Get ready, little astronaut!</p></div>`);
  }

  if(state==='launch'){
    const boost = Math.min(phaseTime/5,1);
    rocket.position.y += 0.05 + boost*0.14;
    camera.position.y = rocket.position.y + 4;
    camera.lookAt(rocket.position.x, rocket.position.y, rocket.position.z);
    ui(`<div class="top-message">Great launch! ✨</div>`);
    if (rocket.position.y > 65) { state='space'; stars.visible = true; scene.background = new THREE.Color('#03051a'); phaseTime=0; ui(''); }
  }

  if(state==='space'){
    // Continuous smooth orbit loop around the selected planet.
    if(!orbitPaused) orbitAngle += 0.02 * orbitSpeed;
    const current = planets[orbitPlanetIndex];
    const center = current.mesh.position;
    const ellipseX = orbitRadius + Math.sin(phaseTime * 0.5) * 0.8;
    const ellipseZ = orbitRadius * 0.7;
    rocket.position.set(
      center.x + Math.cos(orbitAngle) * ellipseX,
      center.y + 2 + Math.sin(orbitAngle * 0.6) * 1.2,
      center.z + Math.sin(orbitAngle) * ellipseZ,
    );
    rocket.lookAt(center);

    // Keep Sun visible by locking the camera to always look at Sun center.
    camera.position.lerp(new THREE.Vector3(35, 22, 55), 0.04);
    camera.lookAt(sunMesh.position);

    // Auto-cycle planets in a loop so rocket never stops at Mercury.
    if(!orbitPaused && Math.abs(Math.sin(orbitAngle)) < 0.015){
      orbitPlanetIndex = (orbitPlanetIndex + 1) % planets.length;
    }

    ui(spaceControls());
    bindSpaceButtons();
  }

  if(state==='return'){
    const earth = planets[2].mesh.position;
    rocket.position.lerp(new THREE.Vector3(earth.x+2, earth.y+2, earth.z+8), 0.02);
    camera.position.lerp(new THREE.Vector3(rocket.position.x + 7, rocket.position.y + 4, rocket.position.z + 12), 0.03);
    camera.lookAt(rocket.position);
    ui(`<div class="top-message">Time to land safely!</div>`);
    if(rocket.position.distanceTo(earth)<8){ state='landing'; scene.background = new THREE.Color('#80d4ff'); stars.visible=false; landingX=0; landingY=16; rocket.position.set(landingX, landingY, 0); camera.position.set(0,9,20); }
  }

  if(state==='landing'){
    if(key.ArrowLeft) landingX -= 0.12; if(key.ArrowRight) landingX += 0.12;
    let fall = 0.06; if(key.ArrowUp) fall = 0.025; if(key.ArrowDown) fall = 0.09;
    landingY -= fall; speedState = fall < 0.04 ? 'Slow' : fall < 0.075 ? 'Good' : 'Too Fast';
    rocket.position.set(landingX, landingY, 0);
    camera.lookAt(rocket.position);
    if(landingY <= 2.8){
      if(Math.abs(landingX) < 2.4){ state='success'; }
      else { landingY = 8; landingMsg = 'Try again! Use the arrows to land on the pad.'; }
    }
    ui(`<div class="hud"><div class="badge">Use ← and → to move. Press ↑ to slow down. Land on the green pad.</div><div class="badge">Speed: ${speedState}</div></div>${landingMsg?`<div class="top-message">${landingMsg}</div>`:''}${landingControls()}`);
  }

  if(state==='success'){
    ui(`<div class="panel"><h2 class="big">Great landing, astronaut! 🎉</h2><p class="small">You visited the planets and came home safely!</p><p class="small">You are a space explorer!</p><button id="againBtn">Play Again</button></div>`);
    const b=document.getElementById('againBtn'); if(b) b.onclick=()=>location.reload();
  }

  renderer.render(scene,camera);
}
animate(0);

addEventListener('resize',()=>{ camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });

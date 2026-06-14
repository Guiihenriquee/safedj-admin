import os
"""
SafeDJ Admin Server
Roda localmente e expõe via túnel público para acesso pelo iPhone
"""
import sys, subprocess, os, hashlib, json
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, render_template_string

# ── CONFIG ────────────────────────────────────────────────────────────────────
FIREBASE_URL = "https://safedj-download-default-rtdb.firebaseio.com"
SECRET_KEY   = "safedj-secret-dj-guii-2024"

app = Flask(__name__)

# ── FIREBASE HELPERS ───────────────────────────────────────────────────────────
import requests as req

def fb_get(path):
    r = req.get(f"{FIREBASE_URL}/{path}.json", timeout=10)
    return r.json() if r.text.strip() != "null" else None

def fb_put(path, data):
    r = req.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
    return r.json()

def fb_patch(path, data):
    r = req.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
    return r.json()

def fb_delete(path):
    req.delete(f"{FIREBASE_URL}/{path}.json", timeout=10)

def email_key(email):
    return email.strip().lower().replace(".", "_").replace("@", "_")

def hash_pass(password):
    return hashlib.sha256(f"{password}{SECRET_KEY}".encode()).hexdigest()

# ── API ROUTES ─────────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    try:
        user = fb_get(f"users/{email_key(email)}")
        if not user:
            return jsonify({"ok": False, "error": "Conta não encontrada."})
        if user.get("password") != hash_pass(password):
            return jsonify({"ok": False, "error": "Senha incorreta."})
        if not user.get("is_master"):
            return jsonify({"ok": False, "error": "Acesso negado. Apenas conta Master."})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Erro Firebase: {str(e)}"})

@app.route("/api/clients", methods=["GET"])
def get_clients():
    try:
        data = fb_get("users")
        if not data:
            return jsonify({"ok": True, "clients": []})
        clients = [v for v in data.values() if isinstance(v, dict)]
        clients.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jsonify({"ok": True, "clients": clients})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/clients", methods=["POST"])
def add_client():
    data = request.json
    email   = data.get("email", "").strip().lower()
    password = data.get("password", "")
    days    = int(data.get("days", 30))
    try:
        key = email_key(email)
        if fb_get(f"users/{key}"):
            return jsonify({"ok": False, "error": "E-mail já cadastrado."})
        now = datetime.utcnow().isoformat()
        exp = (datetime.utcnow() + timedelta(days=days)).isoformat()
        fb_put(f"users/{key}", {
            "email": email,
            "password": hash_pass(password),
            "is_master": False,
            "created_at": now,
            "expires_at": exp
        })
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/clients/<path:email>", methods=["DELETE"])
def delete_client(email):
    try:
        fb_delete(f"users/{email_key(email)}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/clients/<path:email>/days", methods=["PATCH"])
def adjust_days(email):
    delta = int(request.json.get("delta", 0))
    try:
        key  = email_key(email)
        user = fb_get(f"users/{key}")
        if not user:
            return jsonify({"ok": False, "error": "Usuário não encontrado."})
        exp = datetime.fromisoformat(user["expires_at"]) if user.get("expires_at") else datetime.utcnow()
        if exp < datetime.utcnow():
            exp = datetime.utcnow()
        exp = exp + timedelta(days=delta)
        if exp < datetime.utcnow():
            exp = datetime.utcnow()
        fb_patch(f"users/{key}", {"expires_at": exp.isoformat()})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ── FRONTEND ───────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="SafeDJ Admin">
<meta name="theme-color" content="#06060f">
<title>SafeDJ Admin</title>
<style>
:root{--bg:#06060f;--surface:#0e0e1c;--border:#1e1e38;--accent:#00aaff;--gold:#f0c040;--danger:#ff4466;--success:#00dd88;--text:#e0e0f0;--dim:#6060a0;--mono:'Courier New',monospace}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--text);font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;min-height:100dvh}
.screen{display:none;flex-direction:column;min-height:100dvh}
.screen.active{display:flex}
input{width:100%;background:var(--bg);border:1.5px solid var(--border);border-radius:10px;padding:13px 14px;color:var(--text);font-size:15px;outline:none;-webkit-appearance:none}
input:focus{border-color:var(--accent)}
.field{margin-bottom:14px}
.field label{display:block;font-size:10px;letter-spacing:2px;color:var(--dim);margin-bottom:5px;text-transform:uppercase}
.btn{width:100%;padding:14px;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;border:none;-webkit-appearance:none;transition:opacity .15s}
.btn:active{opacity:.7}
.btn-primary{background:var(--accent);color:#000}
.btn-sec{background:transparent;border:1.5px solid var(--border);color:var(--text)}
.btn-danger{background:transparent;border:1.5px solid var(--danger);color:var(--danger)}
.btn-sm{padding:8px 12px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid;-webkit-appearance:none}
.btn-sm:active{opacity:.65}
.btn-days-sm{background:rgba(0,170,255,.1);border-color:rgba(0,170,255,.3);color:var(--accent)}
.btn-del-sm{background:rgba(255,68,102,.08);border-color:rgba(255,68,102,.3);color:var(--danger)}
.err{color:#ff4466;font-size:12px;text-align:center;min-height:18px;padding:4px 0}
.header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 18px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}
.header h1{font-size:15px;font-weight:600;letter-spacing:3px;color:var(--accent)}
.header p{font-size:9px;color:var(--dim);letter-spacing:1px}
.back{background:none;border:none;color:var(--dim);font-size:13px;cursor:pointer;display:flex;align-items:center;gap:5px;padding:0;font-family:inherit}
.back:active{opacity:.6}
.content{padding:18px;flex:1;overflow-y:auto}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px}
.stat{background:var(--surface);border-radius:12px;padding:12px 8px;text-align:center}
.stat .n{font-size:24px;font-weight:600;line-height:1}
.stat .l{font-size:9px;color:var(--dim);margin-top:3px;letter-spacing:1px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px;margin-bottom:10px}
.card.master{border-color:var(--gold)}
.card.expired{opacity:.55}
.badge{font-size:9px;font-weight:700;padding:3px 7px;border-radius:20px;letter-spacing:.5px}
.badge.ok{background:rgba(0,221,136,.12);color:var(--success);border:1px solid rgba(0,221,136,.3)}
.badge.exp{background:rgba(255,68,102,.1);color:var(--danger);border:1px solid rgba(255,68,102,.3)}
.badge.master{background:rgba(240,192,64,.1);color:var(--gold);border:1px solid rgba(240,192,64,.3)}
.meta{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px;font-size:11px;color:var(--dim);margin:8px 0}
.meta span{color:var(--text)}
.search{width:100%;background:var(--surface);border:1.5px solid var(--border);border-radius:10px;padding:11px 14px;color:var(--text);font-size:14px;outline:none;-webkit-appearance:none;margin-bottom:12px}
.search:focus{border-color:var(--accent)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.chip{background:var(--surface);border:1.5px solid var(--border);color:var(--dim);border-radius:20px;padding:7px 14px;font-size:12px;cursor:pointer;-webkit-appearance:none;transition:all .15s}
.chip.on{border-color:var(--accent);background:rgba(0,170,255,.1);color:var(--accent);font-weight:600}
.chip:active{opacity:.6}
.vinyl-wrap{width:100px;height:100px;margin:0 auto 18px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(10px);background:var(--surface);border:1px solid var(--border);color:var(--text);font-size:13px;padding:10px 20px;border-radius:100px;opacity:0;transition:all .25s;pointer-events:none;white-space:nowrap;z-index:999}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.login-wrap{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px}
.login-card{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:24px;width:100%;max-width:350px}
.login-card h2{font-size:16px;font-weight:600;margin-bottom:3px}
.login-card p{font-size:12px;color:var(--dim);margin-bottom:18px}
.confirm-wrap{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;gap:14px}
.confirm-card{background:var(--surface);border:1px solid var(--danger);border-radius:14px;padding:22px;width:100%;max-width:350px;text-align:center}
.confirm-card .ico{font-size:32px;margin-bottom:10px}
.confirm-card h3{font-size:16px;font-weight:600;margin-bottom:6px}
.confirm-card p{font-size:12px;color:var(--dim);word-break:break-all}
.confirm-btns{display:flex;gap:10px;width:100%;max-width:350px}
.empty{text-align:center;padding:40px 0;color:var(--dim);font-size:13px}
.spin{width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;display:inline-block;vertical-align:middle;margin-right:6px}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="scr-login" class="screen active">
  <div class="login-wrap">
    <div class="vinyl-wrap"><canvas id="vc" width="100" height="100"></canvas></div>
    <div style="text-align:center;margin-bottom:28px">
      <div style="font-size:22px;font-weight:600;letter-spacing:6px;color:var(--accent)">SafeDJ</div>
      <div style="font-size:10px;letter-spacing:3px;color:var(--dim);margin-top:2px">ADMIN PANEL</div>
    </div>
    <div class="login-card">
      <h2>Acesso Restrito</h2>
      <p>Apenas conta Master pode entrar.</p>
      <div class="field"><label>E-mail</label><input id="l-email" type="email" placeholder="seu@email.com" autocomplete="email"></div>
      <div class="field"><label>Senha</label><input id="l-pass" type="password" placeholder="••••••" autocomplete="current-password"></div>
      <button class="btn btn-primary" id="btn-login" onclick="doLogin()">Entrar</button>
      <p class="err" id="login-err"></p>
    </div>
  </div>
</div>

<!-- LISTA -->
<div id="scr-list" class="screen">
  <div class="header">
    <div><h1>SafeDJ</h1><p>Admin Panel</p></div>
    <button class="btn btn-sec" style="width:auto;padding:7px 13px;font-size:12px" onclick="goto('login')">Sair</button>
  </div>
  <div class="content">
    <div class="stats">
      <div class="stat"><div class="n" id="s-total" style="color:var(--accent)">—</div><div class="l">Total</div></div>
      <div class="stat"><div class="n" id="s-active" style="color:var(--success)">—</div><div class="l">Ativos</div></div>
      <div class="stat"><div class="n" id="s-expired" style="color:var(--danger)">—</div><div class="l">Expirados</div></div>
    </div>
    <button class="btn btn-sec" style="margin-bottom:12px;border-style:dashed" onclick="goto('add')">+ Adicionar cliente</button>
    <input class="search" type="search" placeholder="Buscar por e-mail..." id="search" oninput="filterList()" autocomplete="off" autocorrect="off" autocapitalize="off">
    <div id="clients-list"><div class="empty"><span class="spin"></span>Carregando...</div></div>
  </div>
</div>

<!-- ADICIONAR -->
<div id="scr-add" class="screen">
  <div class="header">
    <button class="back" onclick="goto('list')">← Voltar</button>
    <div style="text-align:right"><div style="font-size:14px;font-weight:600">Novo cliente</div></div>
    <div style="width:60px"></div>
  </div>
  <div class="content">
    <div class="field"><label>E-mail</label><input id="n-email" type="email" placeholder="cliente@email.com" autocomplete="off"></div>
    <div class="field"><label>Senha de acesso</label><input id="n-pass" type="text" placeholder="Senha para o cliente" autocomplete="off"></div>
    <div class="field">
      <label>Dias de acesso</label>
      <div class="chips" id="add-chips">
        <button class="chip" onclick="pickDays(1)">1 dia</button>
        <button class="chip" onclick="pickDays(7)">7 dias</button>
        <button class="chip on" onclick="pickDays(30)">30 dias</button>
        <button class="chip" onclick="pickDays(60)">60 dias</button>
        <button class="chip" onclick="pickDays(90)">90 dias</button>
        <button class="chip" onclick="pickDays(365)">1 ano</button>
      </div>
      <input id="n-days" type="number" placeholder="Ou digitar número de dias..." min="1" oninput="clearAddChips()">
    </div>
    <p class="err" id="add-err"></p>
    <button class="btn btn-primary" id="btn-add" onclick="doAdd()">Adicionar cliente</button>
  </div>
</div>

<!-- DIAS -->
<div id="scr-days" class="screen">
  <div class="header">
    <button class="back" onclick="goto('list')">← Voltar</button>
    <div style="text-align:right"><div style="font-size:14px;font-weight:600">Ajustar dias</div></div>
    <div style="width:60px"></div>
  </div>
  <div class="content">
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:10px;color:var(--dim);margin-bottom:3px;letter-spacing:1px">CLIENTE</div>
      <div id="days-email" style="font-family:var(--mono);font-size:13px"></div>
    </div>
    <div class="field">
      <label>Adicionar / remover dias</label>
      <div class="chips" id="days-chips">
        <button class="chip" onclick="pickDaysEdit(-30)">−30</button>
        <button class="chip" onclick="pickDaysEdit(-7)">−7</button>
        <button class="chip" onclick="pickDaysEdit(7)">+7</button>
        <button class="chip on" onclick="pickDaysEdit(30)">+30</button>
        <button class="chip" onclick="pickDaysEdit(60)">+60</button>
        <button class="chip" onclick="pickDaysEdit(90)">+90</button>
      </div>
      <input id="edit-days" type="number" placeholder="Ou digitar (negativo para remover)..." oninput="clearDaysChips()">
    </div>
    <button class="btn btn-primary" id="btn-days" onclick="doDays()">Confirmar</button>
  </div>
</div>

<!-- CONFIRMAR DELETE -->
<div id="scr-confirm" class="screen">
  <div class="header">
    <button class="back" onclick="goto('list')">← Voltar</button>
    <div style="font-size:14px;font-weight:600">Confirmar exclusão</div>
    <div style="width:60px"></div>
  </div>
  <div class="confirm-wrap">
    <div class="confirm-card">
      <div class="ico">⚠️</div>
      <h3>Excluir cliente?</h3>
      <p id="del-email-txt"></p>
    </div>
    <p style="font-size:11px;color:var(--dim);text-align:center">Esta ação não pode ser desfeita.</p>
    <div class="confirm-btns">
      <button class="btn btn-sec" onclick="goto('list')" style="flex:1">Cancelar</button>
      <button class="btn btn-danger" id="btn-del" onclick="doDel()" style="flex:1">Sim, excluir</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let clients=[], selDays=30, selDaysEdit=30, pendingEmail='';

function goto(s){
  document.querySelectorAll('.screen').forEach(e=>e.classList.remove('active'));
  document.getElementById('scr-'+s).classList.add('active');
  window.scrollTo(0,0);
}

function toast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2600);
}

function fmtDate(iso){
  if(!iso)return'—';
  return new Date(iso).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'});
}
function daysLeft(exp){
  if(!exp)return null;
  return Math.floor((new Date(exp)-new Date())/86400000);
}

// ── ANIMAÇÃO DO DISCO ─────────────────────────────────────────────────────────
(function(){
  const c=document.getElementById('vc'),ctx=c.getContext('2d');
  let a=0,p=0;
  function f(){
    const s=100,cx=s/2,cy=s/2,r=s/2-2;
    ctx.clearRect(0,0,s,s);
    ctx.save();ctx.translate(cx,cy);ctx.rotate(a*Math.PI/180);
    ctx.fillStyle='#0a0a0a';ctx.beginPath();ctx.arc(0,0,r,0,Math.PI*2);ctx.fill();
    for(let ri=Math.floor(r*.38);ri<r*.94;ri+=4){
      ctx.strokeStyle='#1c1c1c';ctx.lineWidth=.8;
      ctx.beginPath();ctx.arc(0,0,ri,0,Math.PI*2);ctx.stroke();
    }
    const lr=r*.36*(1+Math.sin(p)*.07);
    const g=ctx.createRadialGradient(0,0,0,0,0,lr);
    const br=170+Math.sin(p)*40;
    g.addColorStop(0,`rgb(0,${Math.floor(br*.5+40)},${Math.floor(br*.8+50)})`);
    g.addColorStop(1,'#001166');
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(0,0,lr,0,Math.PI*2);ctx.fill();
    ctx.save();ctx.rotate(-a*Math.PI/180);
    const tb=Math.floor(170+Math.sin(p+.5)*85);
    ctx.fillStyle=`rgb(0,${tb},255)`;
    ctx.font=`bold ${Math.max(5,Math.floor(lr*.26))}px Courier New`;
    ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillText('SafeDJ',0,-lr*.1);
    ctx.fillStyle='#5588aa';
    ctx.font=`${Math.max(4,Math.floor(lr*.16))}px Courier New`;
    ctx.fillText('PRO',0,lr*.35);
    ctx.restore();
    ctx.fillStyle='#000';ctx.beginPath();ctx.arc(0,0,r*.04,0,Math.PI*2);ctx.fill();
    ctx.restore();
    ctx.strokeStyle=`rgba(0,${Math.floor(100+Math.sin(p)*30)},170,1)`;ctx.lineWidth=1;
    ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();
    a=(a+1.2)%360;p=(p+.05)%(Math.PI*2);
    requestAnimationFrame(f);
  }
  f();
})();

// ── LOGIN ─────────────────────────────────────────────────────────────────────
document.getElementById('l-pass').addEventListener('keydown',e=>{if(e.key==='Enter')doLogin()});

async function doLogin(){
  const email=document.getElementById('l-email').value;
  const pass=document.getElementById('l-pass').value;
  const errEl=document.getElementById('login-err');
  const btn=document.getElementById('btn-login');
  if(!email||!pass){errEl.textContent='Preencha os campos.';return;}
  btn.innerHTML='<span class="spin"></span>Verificando...';btn.disabled=true;errEl.textContent='';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass})});
    const d=await r.json();
    if(!d.ok){errEl.textContent=d.error;return;}
    goto('list');loadClients();
  }catch(e){errEl.textContent='Erro de conexão com o servidor.';}
  finally{btn.innerHTML='Entrar';btn.disabled=false;}
}

// ── CLIENTES ──────────────────────────────────────────────────────────────────
async function loadClients(){
  document.getElementById('clients-list').innerHTML='<div class="empty"><span class="spin"></span>Carregando...</div>';
  try{
    const r=await fetch('/api/clients');
    const d=await r.json();
    clients=d.clients||[];
    renderList(clients);
  }catch(e){document.getElementById('clients-list').innerHTML='<div class="empty">Erro ao carregar clientes.</div>';}
}

function renderList(list){
  const nm=list.filter(u=>!u.is_master);
  const act=nm.filter(u=>!u.expires_at||new Date(u.expires_at)>new Date()).length;
  document.getElementById('s-total').textContent=nm.length;
  document.getElementById('s-active').textContent=act;
  document.getElementById('s-expired').textContent=nm.length-act;
  if(!list.length){document.getElementById('clients-list').innerHTML='<div class="empty">Nenhum cliente encontrado.</div>';return;}
  document.getElementById('clients-list').innerHTML=list.map(u=>{
    const dl=daysLeft(u.expires_at);
    const isExp=!u.is_master&&dl!==null&&dl<=0;
    const badge=u.is_master?'<span class="badge master">MASTER</span>':isExp?'<span class="badge exp">Expirado</span>':'<span class="badge ok">Ativo</span>';
    const cls=u.is_master?'card master':isExp?'card expired':'card';
    const days=u.is_master?'Ilimitado':dl===null?'—':dl>0?`${dl} dias restantes`:'Expirado';
    return `<div class="${cls}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px">
        <span style="font-family:var(--mono);font-size:12px;word-break:break-all;flex:1">${u.email}</span>
        ${badge}
      </div>
      <div class="meta">
        <div>Criado: <span>${fmtDate(u.created_at)}</span></div>
        <div>Expira: <span>${fmtDate(u.expires_at)}</span></div>
        <div style="grid-column:span 2">Acesso: <span>${days}</span></div>
      </div>
      ${!u.is_master?`<div style="display:flex;gap:8px;margin-top:4px">
        <button class="btn-sm btn-days-sm" onclick="openDays('${u.email}')">+ / − Dias</button>
        <button class="btn-sm btn-del-sm" onclick="openConfirm('${u.email}')">Excluir</button>
      </div>`:''}
    </div>`;
  }).join('');
}

function filterList(){
  const q=document.getElementById('search').value.toLowerCase();
  renderList(clients.filter(u=>u.email&&u.email.toLowerCase().includes(q)));
}

// ── ADICIONAR ─────────────────────────────────────────────────────────────────
function pickDays(d){
  selDays=d;document.getElementById('n-days').value='';
  document.querySelectorAll('#add-chips .chip').forEach(c=>c.classList.toggle('on',c.textContent===d+' dia'||c.textContent===d+' dias'||(d===365&&c.textContent==='1 ano')));
}
function clearAddChips(){selDays=null;document.querySelectorAll('#add-chips .chip').forEach(c=>c.classList.remove('on'));}

async function doAdd(){
  const email=document.getElementById('n-email').value;
  const pass=document.getElementById('n-pass').value;
  const custom=document.getElementById('n-days').value;
  const days=custom?parseInt(custom):selDays;
  const errEl=document.getElementById('add-err');
  const btn=document.getElementById('btn-add');
  if(!email||!pass){errEl.textContent='Preencha todos os campos.';return;}
  if(!days||days<1){errEl.textContent='Informe os dias de acesso.';return;}
  btn.innerHTML='<span class="spin"></span>Adicionando...';btn.disabled=true;errEl.textContent='';
  try{
    const r=await fetch('/api/clients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass,days})});
    const d=await r.json();
    if(!d.ok){errEl.textContent=d.error;return;}
    goto('list');loadClients();toast('✅ Cliente adicionado!');
  }catch(e){errEl.textContent='Erro de conexão.';}
  finally{btn.innerHTML='Adicionar cliente';btn.disabled=false;}
}

// ── EXCLUIR ───────────────────────────────────────────────────────────────────
function openConfirm(email){
  pendingEmail=email;
  document.getElementById('del-email-txt').textContent=email;
  goto('confirm');
}
async function doDel(){
  const btn=document.getElementById('btn-del');
  btn.innerHTML='<span class="spin"></span>Excluindo...';btn.disabled=true;
  try{
    await fetch(`/api/clients/${encodeURIComponent(pendingEmail)}`,{method:'DELETE'});
    goto('list');loadClients();toast('🗑 Cliente excluído.');
  }catch(e){toast('Erro ao excluir.');}
  finally{btn.innerHTML='Sim, excluir';btn.disabled=false;}
}

// ── DIAS ──────────────────────────────────────────────────────────────────────
function openDays(email){
  pendingEmail=email;selDaysEdit=30;
  document.getElementById('days-email').textContent=email;
  document.getElementById('edit-days').value='';
  document.querySelectorAll('#days-chips .chip').forEach((c,i)=>c.classList.toggle('on',i===3));
  goto('days');
}
function pickDaysEdit(d){
  selDaysEdit=d;document.getElementById('edit-days').value='';
  document.querySelectorAll('#days-chips .chip').forEach(c=>{
    const t=c.textContent;
    c.classList.toggle('on',t===(d>0?'+'+d:'−'+Math.abs(d)));
  });
}
function clearDaysChips(){selDaysEdit=null;document.querySelectorAll('#days-chips .chip').forEach(c=>c.classList.remove('on'));}

async function doDays(){
  const custom=document.getElementById('edit-days').value;
  const delta=custom?parseInt(custom):selDaysEdit;
  if(!delta||delta===0){toast('Informe quantos dias.');return;}
  const btn=document.getElementById('btn-days');
  btn.innerHTML='<span class="spin"></span>Aplicando...';btn.disabled=true;
  try{
    await fetch(`/api/clients/${encodeURIComponent(pendingEmail)}/days`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta})});
    goto('list');loadClients();toast(`${delta>0?'+':''}${delta} dias aplicado!`);
  }catch(e){toast('Erro ao ajustar dias.');}
  finally{btn.innerHTML='Confirmar';btn.disabled=false;}
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

# ── INICIAR SERVIDOR + TÚNEL ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "═"*55)
    print("  SafeDJ Admin — Iniciando servidor...")
    print("═"*55)

    # Iniciar ngrok (token gratuito não necessário para uso básico)
    try:
        tunnel = ngrok.connect(5000, "http")
        public_url = tunnel.public_url
        print(f"\n  ✅ SERVIDOR ONLINE!")
        print(f"\n  📱 Abra no iPhone:")
        print(f"\n  👉  {public_url}")
        print(f"\n  (O link muda a cada vez que iniciar)")
        print("\n" + "═"*55)
        print("  Para parar: feche esta janela ou aperte Ctrl+C")
        print("═"*55 + "\n")
    except Exception as e:
        print(f"\n  ⚠️  Ngrok falhou: {e}")
        print(f"\n  Acesso LOCAL apenas: http://localhost:5000")
        print("═"*55 + "\n")

    app.run(port=5000, debug=False, use_reloader=False)

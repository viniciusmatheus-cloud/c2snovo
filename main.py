#!/usr/bin/env python3
"""
Contact2Sale Importador v5
- Login com usuario/senha fixos (sem banco de dados)
- Slug usa só primeira palavra da empresa principal
- Pronto para deploy no Railway / Render

Para rodar local:   python3 iniciar.py
Para mudar senha:   edite APP_USER e APP_PASS abaixo
"""
import http.server, json, urllib.request, urllib.error
import threading, webbrowser, sys, time, os, secrets, hashlib

# ─── CONFIGURAÇÃO DE ACESSO ──────────────────────────────────────────
APP_USER = "admin"
APP_PASS = "contato2024"   # ← mude aqui
# ────────────────────────────────────────────────────────────────────

PORT = int(os.environ.get("PORT", 8742))

# Sessões ativas: token_de_sessao -> True
SESSIONS: dict = {}

def check_session(cookie_header: str) -> bool:
    if not cookie_header:
        return False
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == "sid" and v.strip() in SESSIONS:
            return True
    return False

def new_session() -> str:
    sid = secrets.token_hex(32)
    SESSIONS[sid] = True
    return sid

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Contact2Sale — Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f5f4f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#fff;border:1px solid #e2e0d8;border-radius:14px;padding:2.5rem 2rem;
  width:360px;box-shadow:0 4px 24px rgba(0,0,0,.07)}
.logo{width:44px;height:44px;background:#2563eb;border-radius:11px;display:flex;
  align-items:center;justify-content:center;margin:0 auto 1.25rem}
.logo svg{width:22px;height:22px;fill:none;stroke:#fff;stroke-width:2}
h1{font-size:20px;font-weight:700;letter-spacing:-.03em;text-align:center;color:#1a1917}
p{font-size:13px;color:#6b6860;text-align:center;margin-top:4px;margin-bottom:1.5rem}
label{font-size:12px;font-weight:600;color:#6b6860;text-transform:uppercase;
  letter-spacing:.05em;display:block;margin-bottom:4px}
input{width:100%;height:42px;border:1px solid #ccc9be;border-radius:8px;padding:0 12px;
  font-size:14px;outline:none;margin-bottom:12px;transition:border-color .15s,box-shadow .15s}
input:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.12)}
button{width:100%;height:42px;background:#2563eb;border:none;border-radius:8px;color:#fff;
  font-size:14px;font-weight:600;cursor:pointer;margin-top:4px;transition:background .15s}
button:hover{background:#1d4ed8}
.err{background:#fef2f2;border:1px solid #fecaca;color:#dc2626;border-radius:8px;
  padding:8px 12px;font-size:13px;margin-bottom:12px;display:none}
</style></head>
<body>
<div class="box">
  <div class="logo"><svg viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg></div>
  <h1>Contact2Sale</h1>
  <p>Importador de vendedores</p>
  <div class="err" id="err">Usuário ou senha incorretos.</div>
  <label>Usuário</label>
  <input type="text" id="u" autocomplete="username" placeholder="usuario"/>
  <label>Senha</label>
  <input type="password" id="p" autocomplete="current-password" placeholder="••••••••"/>
  <button onclick="login()">Entrar</button>
</div>
<script>
async function login(){
  const u=document.getElementById('u').value.trim();
  const p=document.getElementById('p').value;
  const r=await fetch('/auth',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({u,p})});
  if(r.ok){location.href='/';}
  else{document.getElementById('err').style.display='block';}
}
document.addEventListener('keydown',e=>{if(e.key==='Enter')login();});
</script>
</body></html>"""

APP_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Contact2Sale — Importação</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f4f0;--surface:#fff;--s2:#f0efe9;
  --border:#e2e0d8;--border2:#ccc9be;
  --text:#1a1917;--text2:#6b6860;--text3:#9c9a93;
  --blue:#2563eb;--blue-bg:#eff4ff;--blue-b:#bfcffe;
  --green:#16a34a;--green-bg:#f0fdf4;--green-b:#bbf7d0;
  --red:#dc2626;--red-bg:#fef2f2;--red-b:#fecaca;
  --amber:#d97706;--amber-bg:#fffbeb;--amber-b:#fde68a;
  --r:10px;--rs:6px;
  --mono:'JetBrains Mono','Fira Code',monospace;
}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;line-height:1.6}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:0 2rem;height:52px;display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:100}
.tlogo{width:28px;height:28px;background:var(--blue);border-radius:7px;display:flex;align-items:center;justify-content:center}
.tlogo svg{width:16px;height:16px;fill:none;stroke:#fff;stroke-width:2}
.ttitle{font-size:14px;font-weight:600}.tsep{color:var(--border2);margin:0 4px}.tsub{font-size:13px;color:var(--text2)}
.tbadge{margin-left:auto;font-size:11px;padding:2px 8px;background:var(--green-bg);color:var(--green);border:1px solid var(--green-b);border-radius:20px;font-weight:500}
.tlogout{font-size:12px;padding:4px 12px;border:1px solid var(--border2);border-radius:6px;background:none;cursor:pointer;color:var(--text2);margin-left:8px}
.tlogout:hover{background:var(--s2)}
.main{max-width:900px;margin:0 auto;padding:2rem 1.5rem 4rem;display:flex;flex-direction:column;gap:16px}
h1{font-size:22px;font-weight:700;letter-spacing:-.03em}
.sub{font-size:13px;color:var(--text2);margin-top:3px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;transition:opacity .2s}
.card.disabled{opacity:.4;pointer-events:none}
.ch{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--border);background:var(--s2)}
.sn{width:22px;height:22px;border-radius:50%;border:1.5px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:var(--text2);flex-shrink:0;transition:all .2s}
.sn.active{background:var(--blue);border-color:var(--blue);color:#fff}
.sn.done{background:var(--green);border-color:var(--green);color:#fff}
.ct{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}
.cb{padding:18px}
.frow{display:flex;gap:8px;align-items:center}
input[type=text],input[type=password]{flex:1;height:38px;border:1px solid var(--border2);border-radius:var(--rs);padding:0 12px;font-size:13px;color:var(--text);background:var(--surface);outline:none;font-family:var(--mono);transition:border-color .15s,box-shadow .15s}
input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.btn{height:38px;padding:0 16px;border:1px solid var(--border2);border-radius:var(--rs);background:var(--surface);color:var(--text);font-size:13px;font-weight:500;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:all .15s;white-space:nowrap}
.btn:hover{background:var(--s2)}.btn:active{transform:scale(.98)}.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.bp{background:var(--blue);border-color:var(--blue);color:#fff}.bp:hover{background:#1d4ed8}
.bsm{height:30px;padding:0 12px;font-size:12px}
.bgreen{background:var(--green-bg);border-color:var(--green-b);color:var(--green)}.bgreen:hover{background:var(--green-b)}
.msg{margin-top:10px;font-size:13px;padding:8px 12px;border-radius:var(--rs);display:none}
.msg.ok{background:var(--green-bg);color:var(--green);border:1px solid var(--green-b);display:block}
.msg.err{background:var(--red-bg);color:var(--red);border:1px solid var(--red-b);display:block}
.msg.info{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-b);display:block}
.cobox{margin-top:12px;background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:12px 14px;display:none}
.coname{font-size:16px;font-weight:700;color:var(--text)}
.cometa{font-size:11px;font-family:var(--mono);color:var(--text3);margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font-size:12px;padding:3px 10px;background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-b);border-radius:20px;font-weight:500}
.dz{border:2px dashed var(--border2);border-radius:var(--rs);padding:2rem 1rem;text-align:center;cursor:pointer;transition:all .15s;color:var(--text3)}
.dz:hover,.dz.over{border-color:var(--blue);background:var(--blue-bg);color:var(--blue)}
.dz svg{width:32px;height:32px;margin-bottom:8px;opacity:.5}
.dz p{font-size:13px;margin-top:4px}
.dz small{font-size:12px;opacity:.7}
.fileok{display:none;align-items:center;gap:10px;padding:10px 14px;background:var(--green-bg);border:1px solid var(--green-b);border-radius:var(--rs);margin-top:10px}
.fileok .fn{font-size:13px;font-weight:600;color:var(--green);flex:1}
.editor-wrap{margin-top:16px;display:none}
.editor-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.editor-title{font-size:12px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.05em;flex:1}
.editor-hint{font-size:12px;padding:8px 12px;border-radius:var(--rs);margin-bottom:10px;border:1px solid transparent}
.grid-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--rs)}
table.grid{width:100%;border-collapse:collapse;font-size:13px}
table.grid thead tr{background:var(--s2)}
table.grid th{padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:var(--text2);border-bottom:1px solid var(--border);border-right:1px solid var(--border);text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
table.grid th:last-child{border-right:none}
table.grid td{padding:0;border-bottom:1px solid var(--border);border-right:1px solid var(--border)}
table.grid td:last-child{border-right:none}
table.grid tr:last-child td{border-bottom:none}
table.grid td input.cell{width:100%;height:34px;border:none;padding:0 8px;font-size:13px;font-family:inherit;color:var(--text);background:transparent;outline:none}
table.grid td input.cell:focus{background:var(--blue-bg);box-shadow:inset 0 0 0 2px var(--blue)}
table.grid td select.tsel{width:100%;height:34px;border:none;padding:0 8px;font-size:12px;color:var(--text);background:transparent;outline:none;cursor:pointer}
table.grid td select.tsel:focus{background:var(--blue-bg)}
table.grid td select.tsel.matched{color:var(--green);font-weight:500}
table.grid td select.tsel.unmatched{color:var(--amber)}
table.grid td.rdel{width:32px;text-align:center}
table.grid td.rdel button{background:none;border:none;color:var(--text3);cursor:pointer;font-size:16px;line-height:1;padding:4px}
table.grid td.rdel button:hover{color:var(--red)}
.ubox{background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:12px 14px;margin-bottom:14px;font-size:12px;color:var(--text2);line-height:1.9}
.ubox strong{color:var(--text)}
.ubox code{font-family:var(--mono);background:var(--border);padding:1px 5px;border-radius:3px;color:var(--blue);font-size:11px}
.ibar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.pbar{margin-top:14px;display:none}
.pmeta{display:flex;justify-content:space-between;font-size:12px;color:var(--text2);margin-bottom:6px}
.ptrack{height:6px;background:var(--s2);border-radius:3px;overflow:hidden;border:1px solid var(--border)}
.pfill{height:100%;background:var(--blue);border-radius:3px;transition:width .3s;width:0%}
.sgrid{display:none;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
.sc{background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:12px 14px}
.sc .v{font-size:26px;font-weight:700;letter-spacing:-.03em;color:var(--text);line-height:1}
.sc .l{font-size:11px;color:var(--text2);margin-top:4px;text-transform:uppercase;letter-spacing:.05em;font-weight:500}
.sc.ok .v{color:var(--green)}.sc.er .v{color:var(--red)}.sc.wa .v{color:var(--amber)}
.logsec{margin-top:14px;display:none}
.loghdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.logttl{font-size:11px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.06em}
.logbox{background:#0f1117;border-radius:var(--rs);padding:12px 14px;max-height:340px;overflow-y:auto;font-family:var(--mono);font-size:12px;line-height:1.7}
.ll{display:flex;gap:10px;align-items:flex-start}
.lt{color:#4b5563;flex-shrink:0;font-size:11px;margin-top:1px}
.lok{color:#4ade80}.ler{color:#f87171}.lwa{color:#fbbf24}.lin{color:#60a5fa}.ldm{color:#6b7280}
.spin{animation:sp 1s linear infinite;display:inline-block}
@keyframes sp{from{transform:rotate(0)}to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="topbar">
  <div class="tlogo"><svg viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg></div>
  <span class="ttitle">Contact2Sale</span><span class="tsep">/</span>
  <span class="tsub">Importação em massa</span>
  <span class="tbadge">🟢 Online</span>
  <button class="tlogout" onclick="logout()">Sair</button>
</div>

<div class="main">
  <div><h1>Importar vendedores</h1>
  <p class="sub">Token → planilha → editor → importação com log completo.</p></div>

  <!-- STEP 1 -->
  <div class="card" id="c1">
    <div class="ch"><div class="sn active" id="b1">1</div><span class="ct">Token de autenticação</span></div>
    <div class="cb">
      <div class="frow">
        <input type="password" id="tok" placeholder="Cole seu Bearer token..." autocomplete="off"/>
        <button class="btn bp" id="btnval" onclick="validateToken()">✔ Validar</button>
      </div>
      <div class="msg" id="tmsg"></div>
      <div class="cobox" id="cobox">
        <div class="coname" id="coname"></div>
        <div class="cometa" id="cometa"></div>
        <div id="sublabel" style="font-size:12px;font-weight:600;color:var(--text2);margin:10px 0 6px;text-transform:uppercase;letter-spacing:.04em;display:none">Equipes disponíveis:</div>
        <div class="chips" id="chips"></div>
      </div>
    </div>
  </div>

  <!-- STEP 2 -->
  <div class="card disabled" id="c2">
    <div class="ch"><div class="sn" id="b2">2</div><span class="ct">Planilha de usuários</span></div>
    <div class="cb">
      <div style="background:var(--amber-bg);border:1px solid var(--amber-b);border-radius:var(--rs);padding:10px 14px;font-size:13px;color:var(--amber);margin-bottom:14px">
        ⚠ Carregue qualquer planilha — edite no editor antes de importar. Colunas obrigatórias: <strong>name</strong>, <strong>email</strong>.
      </div>
      <div class="dz" id="dz" onclick="document.getElementById('fi').click()"
        ondragover="event.preventDefault();this.classList.add('over')"
        ondragleave="this.classList.remove('over')" ondrop="handleDrop(event)">
        <svg fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
        </svg>
        <p>Clique ou arraste o arquivo .xlsx / .csv</p>
        <small>Processado 100% no seu computador</small>
      </div>
      <input type="file" id="fi" accept=".xlsx,.xls,.csv" style="display:none" onchange="handleFile(this.files[0])"/>
      <div class="fileok" id="fok">
        ✅ <span class="fn" id="fn"></span>
        <span style="font-size:12px;color:var(--green)" id="fc"></span>
        <button class="btn bsm" onclick="document.getElementById('fi').click()">Trocar</button>
      </div>
      <div class="editor-wrap" id="editor-wrap">
        <div class="editor-toolbar">
          <span class="editor-title">✏️ Editor de planilha</span>
          <div style="display:flex;gap:6px">
            <button class="btn bsm" onclick="addRow()">+ Linha</button>
            <button class="btn bsm bgreen" onclick="confirmData()">✔ Confirmar e continuar</button>
          </div>
        </div>
        <div class="editor-hint" id="editor-hint"></div>
        <div class="grid-wrap"><table class="grid"><thead id="gh"></thead><tbody id="gb"></tbody></table></div>
        <button class="btn bsm" style="margin-top:8px" onclick="addRow()">+ Adicionar linha</button>
      </div>
    </div>
  </div>

  <!-- STEP 3 -->
  <div class="card disabled" id="c3">
    <div class="ch"><div class="sn" id="b3">3</div><span class="ct">Importar vendedores</span></div>
    <div class="cb">
      <div class="ubox">
        <strong>Lógica de username (em ordem):</strong><br>
        1ª → <code id="ex1">matheusoliveira.onboarding</code> (primeiro + último nome . <strong>primeira palavra</strong> da empresa)<br>
        2ª → <code>email do contato</code><br>
        3ª → <code id="ex3">matheusoliveirakx.onboarding</code> (+ 2 letras aleatórias)
      </div>
      <div class="ibar">
        <button class="btn bp" id="btnimp" onclick="startImport()">▶ Iniciar importação</button>
        <button class="btn bsm" id="btndl" onclick="dlLog()" style="display:none">⬇ Baixar log</button>
        <button class="btn bsm" id="btncl" onclick="clLog()" style="display:none">🗑 Limpar</button>
      </div>
      <div class="pbar" id="pbar">
        <div class="pmeta"><span id="plbl">Aguardando...</span><span id="ppct">0%</span></div>
        <div class="ptrack"><div class="pfill" id="pfill"></div></div>
      </div>
      <div class="sgrid" id="sgrid">
        <div class="sc">    <div class="v" id="stot">0</div><div class="l">Total</div></div>
        <div class="sc ok"><div class="v" id="sok">0</div> <div class="l">Sucesso</div></div>
        <div class="sc er"><div class="v" id="ser">0</div> <div class="l">Falha</div></div>
        <div class="sc wa"><div class="v" id="sre">0</div> <div class="l">Retentativas</div></div>
      </div>
      <div class="logsec" id="logsec">
        <div class="loghdr"><span class="logttl">Log de execução</span></div>
        <div class="logbox" id="logbox"></div>
      </div>
    </div>
  </div>
</div>

<script>
let token='',companySlug='',subCompanies=[],rows=[],logLines=[];

const esc=s=>String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const ts=()=>new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
const norm=s=>String(s||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/[^a-z0-9]/g,'');

// Slug = PRIMEIRA palavra da empresa. "Onboarding Matheus" → "onboarding"
function firstWordSlug(name){
  const first=(name||'').trim().split(/\\s+/)[0]||name||'empresa';
  return norm(first);
}

function fuzzyMatch(val){
  const n=norm(val); if(!n)return null;
  return subCompanies.find(s=>norm(s.company_name).includes(n))||null;
}

function log(msg,type='in'){
  const b=document.getElementById('logbox'),t=ts();
  logLines.push('['+t+'] '+msg);
  const d=document.createElement('div');d.className='ll';
  const cls={ok:'lok',er:'ler',wa:'lwa',in:'lin',dm:'ldm'}[type]||'lin';
  d.innerHTML='<span class="lt">'+t+'</span><span class="'+cls+'">'+esc(msg)+'</span>';
  b.appendChild(d);b.scrollTop=b.scrollHeight;
}

function setMsg(id,html,type){const e=document.getElementById(id);e.className='msg '+type;e.innerHTML=html;}

async function proxy(method,url,body){
  const r=await fetch('/proxy',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({method,url,token,body:body||null})});
  return r.json();
}

async function logout(){
  await fetch('/logout',{method:'POST'}); location.href='/login';
}

// ── Step 1 ────────────────────────────────────────────────────────────
async function validateToken(){
  const raw=document.getElementById('tok').value.trim();
  if(!raw)return; token=raw;
  const btn=document.getElementById('btnval');
  btn.disabled=true;btn.innerHTML='<span class="spin">↻</span> Validando...';
  setMsg('tmsg','⏳ Conectando...','info');

  const res=await proxy('GET','https://api.contact2sale.com/integration/me',null);
  if(!res.ok){
    setMsg('tmsg','✖ Falha: '+esc(res.error||JSON.stringify(res.body||{})),'err');
    btn.disabled=false;btn.innerHTML='✔ Validar';return;
  }
  const d=res.body||{};
  const coName=d.company_name||'Empresa';
  subCompanies=d.sub_companies||[];

  // Slug = só primeira palavra
  companySlug=firstWordSlug(coName);

  setMsg('tmsg','✔ Token válido','ok');
  document.getElementById('coname').textContent=coName;
  document.getElementById('cometa').textContent='ID: '+(d.company_id||'')+'  ·  slug: '+companySlug;

  if(subCompanies.length>0){
    document.getElementById('sublabel').style.display='block';
    document.getElementById('chips').innerHTML=subCompanies.map(s=>'<span class="chip">'+esc(s.company_name)+'</span>').join('');
  }
  document.getElementById('cobox').style.display='block';

  document.getElementById('ex1').textContent='matheusoliveira.'+companySlug;
  document.getElementById('ex3').textContent='matheusoliveirakx.'+companySlug;

  done('b1');
  document.getElementById('c2').classList.remove('disabled');
  active('b2');
}

// ── Step 2 ────────────────────────────────────────────────────────────
function handleDrop(e){e.preventDefault();document.getElementById('dz').classList.remove('over');if(e.dataTransfer.files[0])handleFile(e.dataTransfer.files[0]);}

function handleFile(file){
  if(!file)return;
  const reader=new FileReader();
  reader.onload=evt=>{
    try{
      const wb=XLSX.read(evt.target.result,{type:'array'});
      const ws=wb.Sheets[wb.SheetNames[0]];
      const raw=XLSX.utils.sheet_to_json(ws,{defval:'',header:1});
      if(!raw.length)throw new Error('Planilha vazia.');
      const headers=raw[0].map(h=>String(h||'').trim());
      const dataRows=raw.slice(1).filter(r=>r.some(c=>String(c||'').trim()));
      const idx=names=>names.map(n=>headers.findIndex(h=>norm(h)===norm(n))).find(i=>i>=0)??-1;
      const iN=idx(['name','nome']),iE=idx(['email']),iP=idx(['phone1','phone','telefone','celular']),iT=idx(['team','equipe','time']);
      rows=dataRows.map(r=>({
        name:  iN>=0?String(r[iN]||'').trim():'',
        email: iE>=0?String(r[iE]||'').trim():'',
        phone1:iP>=0?String(r[iP]||'').trim():'',
        team:  iT>=0?String(r[iT]||'').trim():'',
      })).map(r=>{
        const m=r.team?fuzzyMatch(r.team):null;
        return{...r,
          _cid:  m?m.company_id  :(subCompanies[0]?.company_id||''),
          _cname:m?m.company_name:(subCompanies[0]?.company_name||''),
          _matched:!!m
        };
      });
      document.getElementById('fn').textContent=file.name;
      document.getElementById('fc').textContent=rows.length+' linhas';
      document.getElementById('fok').style.display='flex';
      document.getElementById('dz').style.display='none';
      buildEditor();
      document.getElementById('editor-wrap').style.display='block';
    }catch(e){alert('Erro: '+e.message);}
  };
  reader.readAsArrayBuffer(file);
}

function buildEditor(){
  const un=rows.filter(r=>r.team&&!r._matched).length;
  const h=document.getElementById('editor-hint');
  if(un>0){
    h.textContent='⚠ '+un+' linha(s) com equipe não reconhecida — selecione no dropdown.';
    h.style.cssText='background:var(--amber-bg);border-color:var(--amber-b);color:var(--amber)';
  }else{
    h.textContent='✔ Equipes mapeadas automaticamente. Edite qualquer célula se necessário.';
    h.style.cssText='background:var(--green-bg);border-color:var(--green-b);color:var(--green)';
  }
  document.getElementById('gh').innerHTML='<tr><th>Nome</th><th>E-mail</th><th>Telefone</th><th>Equipe</th><th style="width:32px"></th></tr>';
  renderBody();
}

function renderBody(){
  const tb=document.getElementById('gb');tb.innerHTML='';
  rows.forEach((r,i)=>{
    const tr=document.createElement('tr');
    tr.innerHTML=
      '<td><input class="cell" value="'+esc(r.name)+'" onchange="rows['+i+'].name=this.value"/></td>'+
      '<td><input class="cell" value="'+esc(r.email)+'" onchange="rows['+i+'].email=this.value"/></td>'+
      '<td><input class="cell" value="'+esc(r.phone1)+'" onchange="rows['+i+'].phone1=this.value"/></td>'+
      '<td>'+teamSel(i)+'</td>'+
      '<td class="rdel"><button onclick="delRow('+i+')" title="Remover">×</button></td>';
    tb.appendChild(tr);
  });
}

function teamSel(i){
  const r=rows[i];
  const cls=r._cid?(r._matched||!r.team?'matched':'matched'):'unmatched';
  let o='<option value="">— sem equipe —</option>';
  subCompanies.forEach(s=>{o+='<option value="'+esc(s.company_id)+'"'+(s.company_id===r._cid?' selected':'')+'>'+esc(s.company_name)+'</option>';});
  return'<select class="tsel '+cls+'" onchange="setTeam('+i+',this)">'+o+'</select>';
}

function setTeam(i,sel){
  const s=subCompanies.find(x=>x.company_id===sel.value);
  rows[i]._cid=s?s.company_id:'';rows[i]._cname=s?s.company_name:'';rows[i]._matched=true;
  sel.className='tsel '+(s?'matched':'unmatched');
}

function delRow(i){rows.splice(i,1);renderBody();}
function addRow(){
  rows.push({name:'',email:'',phone1:'',team:'',_cid:subCompanies[0]?.company_id||'',_cname:subCompanies[0]?.company_name||'',_matched:false});
  renderBody();
  document.querySelectorAll('#gb tr:last-child input.cell')[0]?.focus();
}

function confirmData(){
  rows=rows.filter(r=>r.name&&r.email);
  if(!rows.length){alert('Nenhuma linha com name + email.');return;}
  renderBody();
  const h=document.getElementById('editor-hint');
  h.textContent='✔ '+rows.length+' usuário(s) prontos para importação.';
  h.style.cssText='background:var(--green-bg);border-color:var(--green-b);color:var(--green)';
  done('b2');
  document.getElementById('c3').classList.remove('disabled');
  active('b3');
  document.getElementById('c3').scrollIntoView({behavior:'smooth',block:'start'});
}

// ── Username ──────────────────────────────────────────────────────────
function genUser(name,email,slug,att){
  const p=name.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/[^a-z\\s]/g,'').trim().split(/\\s+/);
  const base=(p[0]||'user')+(p[p.length-1]||'x');
  if(att===1)return base+'.'+slug;
  if(att===2)return email;
  const rnd=Array.from({length:2},()=>'abcdefghijklmnopqrstuvwxyz'[Math.floor(Math.random()*26)]).join('');
  return base+rnd+'.'+slug;
}

// ── Step 3 ────────────────────────────────────────────────────────────
async function startImport(){
  const valid=rows.filter(r=>r.name&&r.email);
  if(!valid.length||!token){alert('Confirme os dados primeiro.');return;}
  const btn=document.getElementById('btnimp');
  btn.disabled=true;btn.innerHTML='<span class="spin">↻</span> Importando...';
  document.getElementById('pbar').style.display='block';
  document.getElementById('sgrid').style.display='grid';
  document.getElementById('logsec').style.display='block';
  document.getElementById('btndl').style.display='';
  document.getElementById('btncl').style.display='';

  let ok=0,err=0,retries=0;
  const total=valid.length;
  log('▶ Iniciando — '+total+' usuário(s)','in');

  for(let i=0;i<valid.length;i++){
    const u=valid[i];
    // Slug = primeira palavra da empresa da equipe do usuário
    const slug=u._cname?firstWordSlug(u._cname):companySlug;
    const cid=u._cid||subCompanies[0]?.company_id||'';
    const pct=Math.round(((i+1)/total)*100);
    document.getElementById('pfill').style.width=pct+'%';
    document.getElementById('ppct').textContent=pct+'%';
    document.getElementById('plbl').textContent=(i+1)+'/'+total+': '+u.name;
    if(u._cname)log('  → '+u._cname,'dm');

    for(let att=1;att<=3;att++){
      const uname=genUser(u.name,u.email,slug,att);
      if(!uname){log('✖ '+u.name+' — sem username','er');err++;break;}
      if(att>1){retries++;log('  ↻ Tentativa '+att+'/3 — '+uname,'wa');}
      const body={name:u.name,email:u.email,username:uname,company_id:cid};
      if(u.phone1)body.phone1=u.phone1;
      const res=await proxy('POST','https://api.contact2sale.com/integration/sellers',body);
      if(res.ok||res.status===200||res.status===201){log('✔ '+u.name+' <'+u.email+'> → '+uname,'ok');ok++;break;}
      const em=res.body?.message||res.body?.error||res.error||'HTTP '+res.status;
      const conflict=res.status===409||res.status===422||['username','exist','already','taken'].some(w=>String(em).toLowerCase().includes(w));
      if(conflict&&att<3){log('  ⚠ "'+uname+'" indisponível — próxima variação...','wa');}
      else{log('✖ '+u.name+' <'+u.email+'> — '+em,'er');err++;break;}
    }
    document.getElementById('stot').textContent=i+1;
    document.getElementById('sok').textContent=ok;
    document.getElementById('ser').textContent=err;
    document.getElementById('sre').textContent=retries;
    await new Promise(r=>setTimeout(r,150));
  }
  const color=err===0?'#16a34a':ok===0?'#dc2626':'#d97706';
  document.getElementById('pfill').style.background=color;
  document.getElementById('plbl').textContent='Concluído — '+ok+' sucesso · '+err+' falha';
  log('━━ Finalizado: '+ok+' sucesso · '+err+' falha · '+retries+' retentativas ━━','dm');
  btn.disabled=false;btn.innerHTML='✔ Importação concluída';
}

function dlLog(){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([logLines.join('\\n')],{type:'text/plain'}));
  a.download='c2s_import_'+new Date().toISOString().slice(0,10)+'.log';a.click();
}
function clLog(){document.getElementById('logbox').innerHTML='';logLines=[];}
function done(id){const e=document.getElementById(id);e.classList.remove('active');e.classList.add('done');e.textContent='✓';}
function active(id){document.getElementById(id).classList.add('active');}
document.getElementById('tok').addEventListener('keydown',e=>{if(e.key==='Enter')validateToken();});
</script>
</body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, ctype, body_bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(body_bytes))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        cookies = self.headers.get("Cookie", "")
        if self.path in ("/", "/index.html"):
            if not check_session(cookies):
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            self._send(200, "text/html;charset=utf-8", APP_HTML.encode())
        elif self.path == "/login":
            self._send(200, "text/html;charset=utf-8", LOGIN_HTML.encode())
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        if self.path == "/auth":
            try:
                data = json.loads(raw)
                u = data.get("u", "").strip()
                p = data.get("p", "")
                # Comparação segura (evita timing attack)
                u_ok = secrets.compare_digest(u, APP_USER)
                p_ok = secrets.compare_digest(p, APP_PASS)
                if u_ok and p_ok:
                    sid = new_session()
                    self.send_response(200)
                    self.send_header("Set-Cookie", f"sid={sid}; HttpOnly; SameSite=Strict; Path=/")
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                else:
                    self._send(401, "application/json", b'{"ok":false}')
            except Exception as ex:
                self._send(400, "application/json", json.dumps({"error": str(ex)}).encode())
            return

        if self.path == "/logout":
            cookies = self.headers.get("Cookie", "")
            for part in cookies.split(";"):
                k, _, v = part.strip().partition("=")
                if k.strip() == "sid":
                    SESSIONS.pop(v.strip(), None)
            self.send_response(200)
            self.send_header("Set-Cookie", "sid=; Max-Age=0; Path=/")
            self.end_headers()
            return

        if self.path == "/proxy":
            cookies = self.headers.get("Cookie", "")
            if not check_session(cookies):
                self._send(401, "application/json", b'{"error":"unauthorized"}')
                return
            try:
                q = json.loads(raw)
                method  = q.get("method", "GET").upper()
                url     = q.get("url", "")
                tok     = q.get("token", "")
                payload = q.get("body", None)
                hdrs = {
                    "Authorization": f"Bearer {tok}",
                    "Content-Type":  "application/json",
                    "Accept":        "application/json",
                }
                bdata = json.dumps(payload).encode() if payload is not None else None
                req   = urllib.request.Request(url, data=bdata, headers=hdrs, method=method)
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = {"ok": True, "status": resp.status,
                                  "body": json.loads(resp.read().decode())}
                except urllib.error.HTTPError as e:
                    st = e.code
                    try:    rb = json.loads(e.read().decode())
                    except: rb = {}
                    result = {"ok": False, "status": st, "body": rb,
                              "error": rb.get("message") or rb.get("error") or f"HTTP {st}"}
            except Exception as ex:
                result = {"ok": False, "status": 0, "error": str(ex), "body": {}}
            out = json.dumps(result).encode()
            self._send(200, "application/json", out)
            return

        self._send(404, "text/plain", b"Not found")


def main():
    srv = http.server.HTTPServer(("0.0.0.0", PORT), H)
    print(f"""
  ╔══════════════════════════════════════════╗
  ║   Contact2Sale — Importador v5           ║
  ╠══════════════════════════════════════════╣
  ║  Usuário : {APP_USER:<30} ║
  ║  Senha   : {APP_PASS:<30} ║
  ╚══════════════════════════════════════════╝

  ✅  http://127.0.0.1:{PORT}
  Ctrl+C para encerrar
""")
    threading.Thread(
        target=lambda: (time.sleep(1), webbrowser.open(f"http://127.0.0.1:{PORT}")),
        daemon=True
    ).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Encerrado.")
        sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Minecraft Server Web Controller - FastAPI + WebSocket"""

import asyncio
import os
import sys
import webbrowser
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse

# ─── Config ─────────────────────────────────────────────
JAVA = r"D:\APP\scoop\apps\temurin21-jdk\current\bin\java.exe"
JAR = "paper-1.21.11-127.jar"
CWD = r"C:\Users\liuqi\Downloads\minecraft"
HOST = "127.0.0.1"
PORT = 8765
MAX_BUF = 2000

app = FastAPI(title="MC Server Controller")


# ─── Server Manager ─────────────────────────────────────
class Server:
    def __init__(self):
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.buf: list[str] = []
        self.ws: set[WebSocket] = set()

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def start(self) -> dict:
        if self.alive:
            return {"ok": 0, "msg": "Already running"}
        jar = os.path.join(CWD, JAR)
        if not os.path.isfile(jar):
            return {"ok": 0, "msg": f"JAR not found: {jar}"}
        try:
            self.proc = await asyncio.create_subprocess_exec(
                JAVA, "-Xms2G", "-Xmx4G", "-jar", JAR, "nogui",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=CWD,
            )
            asyncio.create_task(self._read())
            return {"ok": 1, "msg": "Starting..."}
        except Exception as e:
            return {"ok": 0, "msg": str(e)}

    async def _read(self):
        try:
            while True:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                t = line.decode("utf-8", errors="replace").rstrip()
                self.buf.append(t)
                if len(self.buf) > MAX_BUF:
                    self.buf = self.buf[-MAX_BUF:]
                await self._cast(t)
        except Exception:
            pass
        if self.proc.returncode is not None:
            m = f"[Ctrl] Server exited (code {self.proc.returncode})"
            self.buf.append(m)
            await self._cast(m)

    async def _cast(self, text: str):
        dead = set()
        for s in self.ws:
            try:
                await s.send_text(text)
            except Exception:
                dead.add(s)
        self.ws -= dead

    async def stop(self) -> dict:
        if not self.alive:
            return {"ok": 0, "msg": "Not running"}
        try:
            self.proc.stdin.write(b"stop\n")
            await self.proc.stdin.drain()
            await asyncio.wait_for(self.proc.wait(), timeout=30)
        except asyncio.TimeoutError:
            self.proc.kill()
            await self.proc.wait()
        except Exception:
            if self.proc.returncode is None:
                self.proc.kill()
                await self.proc.wait()
        return {"ok": 1, "msg": "Server stopped"}

    async def command(self, cmd: str) -> dict:
        if not self.alive:
            return {"ok": 0, "msg": "Not running"}
        try:
            self.proc.stdin.write(f"{cmd}\n".encode())
            await self.proc.stdin.drain()
            return {"ok": 1, "msg": f"Sent: {cmd}"}
        except Exception as e:
            return {"ok": 0, "msg": str(e)}


sv = Server()


# ─── API ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.post("/api/start")
async def api_start():
    return await sv.start()


@app.post("/api/stop")
async def api_stop():
    return await sv.stop()


@app.post("/api/command")
async def api_command(command: str = Form(...)):
    return await sv.command(command)


@app.get("/api/status")
async def api_status():
    return {"running": sv.alive}


@app.get("/api/console")
async def api_console(offset: int = 0):
    return {"lines": sv.buf[offset:], "total": len(sv.buf)}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    sv.ws.add(websocket)
    try:
        for line in sv.buf:
            await websocket.send_text(line)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sv.ws.discard(websocket)


# ─── Frontend ───────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MC Server Controller</title>
<style>
:root{--bg:#0f172a;--bg2:#1e293b;--bg3:#0c1222;--text:#e2e8f0;--muted:#94a3b8;--green:#22c55e;--red:#ef4444;--yellow:#eab308;--blue:#3b82f6;--border:#334155;--r:8px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}
.hdr{padding:16px 24px;background:var(--bg2);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.hdr h1{font-size:18px;font-weight:600;display:flex;align-items:center;gap:10px}
.badge{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
.on{background:rgba(34,197,94,.15);color:var(--green);border:1px solid rgba(34,197,94,.3)}
.off{background:rgba(239,68,68,.15);color:var(--red);border:1px solid rgba(239,68,68,.3)}
.bar{padding:12px 24px;background:var(--bg2);border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.sep{width:1px;height:24px;background:var(--border);margin:0 4px}
.btn{padding:8px 16px;border:none;border-radius:var(--r);font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:6px}
.btn:active{transform:scale(.97)}
.bg{background:var(--green);color:#000}.bg:hover{background:#16a34a}
.br{background:var(--red);color:#fff}.br:hover{background:#dc2626}
.by{background:var(--yellow);color:#000}.by:hover{background:#ca8a04}
.bb{background:var(--blue);color:#fff}.bb:hover{background:#2563eb}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.info{margin-left:auto;font-size:12px;color:var(--muted)}
.cw{flex:1;display:flex;flex-direction:column;overflow:hidden}
.con{flex:1;overflow-y:auto;padding:16px 20px;background:var(--bg3);font-family:'Cascadia Code','Fira Code','JetBrains Mono',monospace;font-size:13px;line-height:1.6;scroll-behavior:smooth}
.ln{white-space:pre-wrap;word-break:break-all;padding:1px 0}
.ln.i{color:var(--green)}.ln.w{color:var(--yellow)}.ln.e{color:var(--red)}.ln.d{color:var(--muted)}
.con::-webkit-scrollbar{width:6px}
.con::-webkit-scrollbar-track{background:transparent}
.con::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.ib{padding:12px 24px;background:var(--bg2);border-top:1px solid var(--border);display:flex;gap:8px}
.ib input{flex:1;padding:10px 14px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-family:monospace;font-size:13px;outline:none;transition:border-color .15s}
.ib input:focus{border-color:var(--blue)}
.ib input::placeholder{color:#475569}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);padding:10px 20px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);font-size:13px;opacity:0;transition:opacity .3s;pointer-events:none;z-index:100}
.toast.show{opacity:1}
</style>
</head>
<body>
<div class="hdr">
  <h1>⛏️ MC Server Controller</h1>
  <span id="badge" class="badge off">STOPPED</span>
</div>
<div class="bar">
  <button class="btn bg" onclick="doStart()">▶ Start</button>
  <button class="btn br" onclick="doStop()">⏹ Stop</button>
  <button class="btn by" onclick="doRestart()">↻ Restart</button>
  <div class="sep"></div>
  <button class="btn bb" onclick="clr()">Clear</button>
  <span class="info" id="conn">Connecting...</span>
</div>
<div class="cw"><div class="con" id="con"></div></div>
<div class="ib">
  <input id="cmd" placeholder="Enter command (e.g. /say hello, /list, /gamemode creative @s)..." autocomplete="off" spellcheck="false">
  <button class="btn bg" onclick="send()">Send</button>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id),
  con=$('con'),cmdEl=$('cmd'),bdg=$('badge'),cnn=$('conn'),tst=$('toast');
let ws,hist=[],hi=-1,lc=0;

function toast(m,ms=2500){tst.textContent=m;tst.classList.add('show');setTimeout(()=>tst.classList.remove('show'),ms)}

function addLine(t){
  const d=document.createElement('div');d.className='ln';
  if(/ERROR|SEVERE|Exception|Caused by/i.test(t))d.classList.add('e');
  else if(/WARN/i.test(t))d.classList.add('w');
  else if(/INFO/i.test(t))d.classList.add('i');
  else if(t.startsWith('[Ctrl]'))d.classList.add('d');
  d.textContent=t;con.appendChild(d);lc++;
  if(lc>2000){con.removeChild(con.firstChild);lc--}
  con.scrollTop=con.scrollHeight;
}

function connect(){
  const p=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(`${p}://${location.host}/ws`);
  ws.onopen=()=>{cnn.textContent='● Connected';cnn.style.color='#22c55e'};
  ws.onmessage=e=>addLine(e.data);
  ws.onclose=()=>{cnn.textContent='○ Reconnecting...';cnn.style.color='#ef4444';setTimeout(connect,2000)};
  ws.onerror=()=>ws.close();
}

async function api(u,b){
  const o=b?{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body}:{method:'POST'};
  return(await fetch(u,o)).json();
}

async function doStart(){toast('Starting...');const d=await api('/api/start');toast(d.msg);refresh()}
async function doStop(){toast('Stopping...');const d=await api('/api/stop');toast(d.msg);refresh()}
async function doRestart(){
  toast('Restarting...');
  await api('/api/stop');
  await new Promise(r=>setTimeout(r,1500));
  await api('/api/start');
  refresh();
}
async function send(){
  const c=cmdEl.value.trim();if(!c)return;
  hist.push(c);hi=hist.length;cmdEl.value='';
  if(c==='/stop'){await doStop();return}
  const d=await api('/api/command',`command=${encodeURIComponent(c)}`);
  if(!d.ok)toast(d.msg);
}
async function refresh(){
  try{const r=await fetch('/api/status');const d=await r.json();
  bdg.textContent=d.running?'RUNNING':'STOPPED';
  bdg.className='badge '+(d.running?'on':'off')}catch{}
}
function clr(){con.innerHTML='';lc=0}

cmdEl.addEventListener('keydown',e=>{
  if(e.key==='Enter'){send();return}
  if(e.key==='ArrowUp'){e.preventDefault();if(hi>0){hi--;cmdEl.value=hist[hi]}}
  if(e.key==='ArrowDown'){e.preventDefault();if(hi<hist.length-1){hi++;cmdEl.value=hist[hi]}else{hi=hist.length;cmdEl.value=''}}
});

connect();refresh();setInterval(refresh,5000);addLine('[Ctrl] Ready');
</script>
</body>
</html>"""


# ─── Main ───────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MC Server Web Controller")
    p.add_argument("-p", "--port", type=int, default=PORT)
    p.add_argument("--host", default=HOST)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()

    if not a.no_browser:
        webbrowser.open(f"http://{a.host}:{a.port}")

    print(f"MC Server Controller: http://{a.host}:{a.port}")
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")

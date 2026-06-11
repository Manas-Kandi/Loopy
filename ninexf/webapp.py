"""`9xf app` — the chat-style web app (v0.6): start a session, pick a folder,
type a goal, watch the loop think and build, with a live code-diff panel.

Pure stdlib on the Python side: http.server + one embedded dark-mode HTML page
that polls JSON endpoints. Unlike the dashboard (read-only), the app *controls*
runs: POST /api/start inits a project and spawns a detached `9xf run`
subprocess; POST /api/stop drops the STOP file.

This same server is what the Electron desktop app (app/ at the repo root)
hosts in a native window — the web UI works identically in a plain browser,
so the harness keeps zero pip dependencies.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ninexf import CONFIG_FILENAME, GOAL_FILENAME, STOP_FILENAME, __version__
from ninexf.config import load_config
from ninexf.dashboard import _run_status, collect_runs
from ninexf.looplog import read_entries
from ninexf.registry import read_state
from ninexf.tasks import load_tasks

COMMIT_RE = re.compile(r"^[0-9a-f]{6,40}$")
MAX_DIFF_CHARS = 200_000
MAX_ENTRIES = 300

_PROCS: dict[str, subprocess.Popen] = {}  # dir -> spawned run process


# -- API: read ------------------------------------------------------------------

def _chat_entry(e: dict) -> dict:
    """Whittle a log entry down to what the chat UI renders."""
    return {
        "event": e.get("event", "iteration"),
        "iteration": e.get("iteration", 0),
        "timestamp": e.get("timestamp", ""),
        "mode": e.get("mode", "build"),
        "subtask": e.get("subtask", ""),
        "summary": e.get("summary", ""),
        "ok": bool(e.get("validation_passed")),
        "detail": e.get("validation_detail", ""),
        "errors": [str(x)[:300] for x in (e.get("errors") or [])][:5],
        "files": e.get("files_written", []),
        "commit": e.get("commit", ""),
        "repairs": len(e.get("repairs") or []),
        "repaired_ok": bool((e.get("repairs") or [{}])[-1].get("passed")),
        "candidates": len(e.get("candidates") or []),
        "chosen": e.get("chosen_candidate", 0),
        "critic": e.get("critic_verdict", ""),
        "stuck": e.get("stuck_signals", []),
        "regression": bool(e.get("regression")),
        "task_id": e.get("task_id", 0),
        "acceptance": e.get("acceptance_passed"),
        "overflow": bool(e.get("context_overflow")),
        "tool_runs": [{"name": t.get("name", ""), "result": str(t.get("result", ""))[:200]}
                      for t in (e.get("tool_runs") or [])][:3],
    }


def run_detail(d: Path) -> dict:
    if not (d / GOAL_FILENAME).exists():
        return {"error": f"not a 9xf run: {d}"}
    try:
        cfg = load_config(d)
        model, cap, delay = cfg.model, cfg.max_iterations, cfg.delay_seconds
    except (FileNotFoundError, json.JSONDecodeError):
        model, cap, delay = "?", 0, 5
    entries = read_entries(d)
    iters = [e for e in entries if e.get("event") == "iteration"]
    state = read_state(d)
    tl = load_tasks(d)
    done, total = tl.counts()
    return {
        "dir": str(d),
        "name": d.name,
        "goal": (d / GOAL_FILENAME).read_text().strip(),
        "model": model,
        "cap": cap,
        "status": _run_status(state, delay, iters[-1].get("validation_passed") if iters else None),
        "stopped_reason": state.get("stopped_reason", ""),
        "iteration": state.get("iteration", iters[-1].get("iteration", 0) if iters else 0),
        "mode": state.get("mode", ""),
        "live_subtask": state.get("subtask", ""),
        "finished": any(e.get("event") == "finished" for e in entries),
        "stop_present": (d / STOP_FILENAME).exists(),
        "tasks": [{"num": t.num, "text": t.text, "status": t.status} for t in tl.tasks],
        "tasks_done": done,
        "tasks_total": total,
        "entries": [_chat_entry(e) for e in entries[-MAX_ENTRIES:]],
    }


def commit_diff(d: Path, commit: str) -> dict:
    if not COMMIT_RE.match(commit):
        return {"error": "bad commit"}
    try:
        out = subprocess.run(
            ["git", "show", commit, "--format=%h %s", "--unified=3", "--",
             "src", "tests", "tools", "TASKS.md", "ACCEPTANCE.md", "NOTES.md"],
            cwd=d, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:300] or "git show failed"}
    text = out.stdout
    if len(text) > MAX_DIFF_CHARS:
        text = text[:MAX_DIFF_CHARS] + "\n... (diff truncated)"
    return {"commit": commit, "diff": text}


def browse(path_str: str) -> dict:
    base = Path(path_str).expanduser() if path_str else Path.home()
    try:
        base = base.resolve()
    except OSError:
        base = Path.home()
    if not base.is_dir():
        base = Path.home()
    dirs = []
    try:
        for p in sorted(base.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                dirs.append({"name": p.name, "path": str(p),
                             "is_run": (p / CONFIG_FILENAME).exists()})
    except PermissionError:
        pass
    return {"path": str(base),
            "parent": str(base.parent) if base != base.parent else "",
            "is_run": (base / CONFIG_FILENAME).exists(),
            "dirs": dirs[:200]}


def list_models() -> dict:
    from ninexf.interactive import DEFAULT_MODEL, _ollama_models
    found = [f"ollama/{m}" for m in _ollama_models()]
    return {"models": found or [DEFAULT_MODEL], "default": found[0] if found else DEFAULT_MODEL}


# -- API: control -----------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def is_running(d: Path) -> bool:
    state = read_state(d)
    return bool(state.get("running")) and _pid_alive(state.get("pid", -1))


def start_run(payload: dict) -> dict:
    d = Path(str(payload.get("dir", "")).strip()).expanduser()
    if not str(d) or not d.is_absolute():
        return {"error": "an absolute folder path is required"}
    goal = (payload.get("goal") or "").strip()
    if not (d / CONFIG_FILENAME).exists():
        if not goal:
            return {"error": "a goal is required for a new session"}
        from ninexf.cli import init_project
        try:
            init_project(d, goal, model=payload.get("model") or None,
                         preset=payload.get("preset") or None)
        except (FileExistsError, OSError, ValueError) as e:
            return {"error": str(e)}
    if is_running(d):
        return {"error": "this run is already going"}
    if (d / STOP_FILENAME).exists():
        (d / STOP_FILENAME).unlink()

    cmd = [sys.executable, "-m", "ninexf", "run", "--dir", str(d)]
    if payload.get("iterations"):
        cmd += ["--max-iterations", str(int(payload["iterations"]))]
    if payload.get("hours"):
        cmd += ["--hours", str(float(payload["hours"]))]
    if payload.get("delay") is not None:
        cmd += ["--delay", str(float(payload["delay"]))]
    log = (d / "run.out").open("ab")
    try:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        return {"error": f"could not start the loop: {e}"}
    finally:
        log.close()  # the child holds its own copy of the fd
    _PROCS[str(d)] = proc
    return {"ok": True, "dir": str(d), "pid": proc.pid}


def stop_run(payload: dict) -> dict:
    d = Path(str(payload.get("dir", "")).strip()).expanduser()
    if not (d / GOAL_FILENAME).exists():
        return {"error": f"not a 9xf run: {d}"}
    (d / STOP_FILENAME).write_text("stop requested via 9xf app\n")
    return {"ok": True}


# -- HTTP plumbing ------------------------------------------------------------------

class AppHandler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(json.dumps(obj).encode(), "application/json", code)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                self._send(APP_PAGE.encode(), "text/html; charset=utf-8")
            elif url.path == "/api/runs":
                self._json(collect_runs())
            elif url.path == "/api/run":
                self._json(run_detail(Path(q.get("dir", "")).expanduser()))
            elif url.path == "/api/diff":
                self._json(commit_diff(Path(q.get("dir", "")).expanduser(),
                                       q.get("commit", "")))
            elif url.path == "/api/browse":
                self._json(browse(q.get("path", "")))
            elif url.path == "/api/models":
                self._json(list_models())
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # never let one bad request kill the app
            self._json({"error": str(e)[:300]}, 500)

    def do_POST(self):
        url = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode() or "{}")
            if url.path == "/api/start":
                self._json(start_run(payload))
            elif url.path == "/api/stop":
                self._json(stop_run(payload))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)

    def log_message(self, *args):  # quiet
        pass


def make_server(port: int = 0) -> ThreadingHTTPServer:
    """Bound but not yet serving — tests use port 0 and read the real port."""
    return ThreadingHTTPServer(("127.0.0.1", port), AppHandler)


def serve_app(port: int = 9118, open_browser: bool = True):
    server = make_server(port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"[9xf] app at {url} (Ctrl+C to quit)")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[9xf] app stopped")


# -- the page -------------------------------------------------------------------------

APP_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>9xf</title>
<style>
:root{--bg:#0d1117;--panel:#10151c;--card:#161b22;--card2:#1c2330;--border:#30363d;
--text:#e6edf3;--dim:#8b949e;--green:#3fb950;--red:#f85149;--amber:#d29922;
--blue:#58a6ff;--purple:#bc8cff;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--bg);color:var(--text);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;overflow:hidden}
button{font:inherit;cursor:pointer;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:8px;padding:7px 14px}
button:hover{background:var(--card2)}
button.primary{background:var(--blue);border-color:var(--blue);color:#04111f;font-weight:600}
button.danger{color:var(--red)}
input,textarea,select{font:inherit;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 10px;width:100%}
textarea{resize:vertical;min-height:74px}
::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:5px}

/* sidebar */
#side{width:264px;min-width:264px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column}
#brand{padding:18px 16px 10px;font-size:17px;font-weight:700}#brand .x{color:var(--purple)}
#brand small{display:block;color:var(--dim);font-weight:400;font-size:11px;margin-top:2px}
#newBtn{margin:8px 14px 12px;font-weight:600}
#runlist{flex:1;overflow-y:auto;padding:0 8px 12px}
.runitem{padding:10px 10px;border-radius:8px;cursor:pointer;margin-bottom:4px}
.runitem:hover{background:var(--card)}
.runitem.active{background:var(--card);border:1px solid var(--border)}
.runitem .g{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.runitem .s{font-size:11px;color:var(--dim);display:flex;gap:6px;align-items:center;margin-top:3px}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--dim)}
.dot.running{background:var(--green);box-shadow:0 0 6px var(--green)}
.dot.finished{background:var(--blue)}.dot.failed{background:var(--red)}.dot.stale{background:var(--amber)}

/* main */
#main{flex:1;display:flex;flex-direction:column;min-width:0}
#top{padding:12px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px;background:var(--panel)}
#top .goal{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.pill.running{background:rgba(63,185,80,.15);color:var(--green)}
.pill.finished{background:rgba(88,166,255,.18);color:var(--blue)}
.pill.stopped,.pill.never{background:rgba(139,148,158,.15);color:var(--dim)}
.pill.failed{background:rgba(248,81,73,.12);color:var(--red)}
.pill.stale{background:rgba(210,153,34,.15);color:var(--amber)}
#taskbar{font-size:11px;color:var(--dim);white-space:nowrap}
#panes{flex:1;display:flex;min-height:0}
#chatwrap{flex:1.1;display:flex;flex-direction:column;min-width:0}
#chat{flex:1;overflow-y:auto;padding:22px 26px;scroll-behavior:smooth}
#statusbar{padding:10px 18px;border-top:1px solid var(--border);background:var(--panel);display:flex;align-items:center;gap:12px;font-size:12px;color:var(--dim)}
#statusbar .pulse{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:.25}50%{opacity:1}}

/* chat bubbles */
.msg{max-width:760px;margin:0 auto 14px}
.bubble{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:11px 14px}
.bubble.plan{border-left:3px solid var(--purple)}
.bubble.exec.ok{border-left:3px solid var(--green)}
.bubble.exec.bad{border-left:3px solid var(--red)}
.bubble.clickable{cursor:pointer}
.bubble.clickable:hover{background:var(--card2)}
.bubble.selected{outline:1px solid var(--blue)}
.who{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--dim);margin-bottom:5px;display:flex;gap:8px;align-items:center}
.who .m{color:var(--purple)}
.who .iter{color:var(--dim);font-weight:400}
.who .badge{font-size:10px;padding:1px 7px;border-radius:999px}
.badge.ok{background:rgba(63,185,80,.15);color:var(--green)}
.badge.bad{background:rgba(248,81,73,.15);color:var(--red)}
.badge.info{background:rgba(88,166,255,.13);color:var(--blue)}
.badge.warn{background:rgba(210,153,34,.15);color:var(--amber)}
.sub{font-family:var(--mono);font-size:12.5px;word-break:break-word}
.sum{margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font:11px var(--mono);background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:2px 8px;color:var(--blue)}
.errs{margin-top:8px;font:11.5px var(--mono);color:var(--red);opacity:.9}
.errs div{padding:2px 0;word-break:break-word}
.meta{margin-top:7px;font-size:11px;color:var(--dim);display:flex;flex-wrap:wrap;gap:10px}
.sys{max-width:760px;margin:0 auto 14px;text-align:center;color:var(--dim);font-size:12px}
.sys b{color:var(--text)}
.sys.finish{color:var(--green);font-weight:600;font-size:13px}
.empty{margin:auto;text-align:center;color:var(--dim);padding:60px 30px}
.empty h2{color:var(--text);font-size:20px;margin-bottom:8px}

/* diff pane */
#diffpane{flex:1;border-left:1px solid var(--border);display:flex;flex-direction:column;min-width:0;background:var(--panel)}
#diffhead{padding:10px 16px;border-bottom:1px solid var(--border);font:12px var(--mono);color:var(--dim);display:flex;justify-content:space-between;gap:8px;align-items:center}
#diff{flex:1;overflow:auto;padding:14px 16px;font:12px/1.55 var(--mono);white-space:pre;color:var(--text)}
#diff .add{color:var(--green)}#diff .del{color:var(--red)}
#diff .hunk{color:var(--purple)}#diff .file{color:var(--blue);font-weight:700}
#diff .ctx{color:var(--dim)}

/* modal */
#overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:10}
#overlay.show{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:24px;width:540px;max-width:92vw;max-height:88vh;overflow-y:auto}
.modal h2{font-size:16px;margin-bottom:16px}
.field{margin-bottom:14px}
.field label{display:block;font-size:11.5px;font-weight:600;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.row{display:flex;gap:10px}.row>*{flex:1}
.seg{display:flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg button{flex:1;border:0;border-radius:0;background:var(--bg)}
.seg button.on{background:var(--blue);color:#04111f;font-weight:700}
.modal .actions{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}
#browser{font:12.5px var(--mono);border:1px solid var(--border);border-radius:8px;max-height:220px;overflow-y:auto;margin-top:8px}
#browser .bi{padding:6px 10px;cursor:pointer;display:flex;gap:8px}
#browser .bi:hover{background:var(--card2)}
#browser .bi .tag{color:var(--purple);font-size:10px}
.err{color:var(--red);font-size:12px;margin-top:8px;min-height:14px}
.hint{color:var(--dim);font-size:11.5px;margin-top:6px}
</style></head><body>

<div id="side">
  <div id="brand">9<span class="x">xf</span><small>autonomous coding loops</small></div>
  <button id="newBtn" class="primary">＋ &nbsp;New session</button>
  <div id="runlist"></div>
</div>

<div id="main">
  <div id="top">
    <div class="goal" id="topGoal">welcome</div>
    <span id="taskbar"></span>
    <span class="pill never" id="topPill">no run</span>
    <button id="stopBtn" class="danger" style="display:none">Stop</button>
    <button id="resumeBtn" class="primary" style="display:none">Resume</button>
  </div>
  <div id="panes">
    <div id="chatwrap">
      <div id="chat"><div class="empty"><h2>Set a goal. Go to sleep.</h2>
        Pick a folder, write one sentence, and watch a local model build it —<br>
        plan → write → validate → repair → commit, on a loop.<br><br>
        <button class="primary" onclick="openNew()">Start a session</button></div></div>
      <div id="statusbar" style="display:none"></div>
    </div>
    <div id="diffpane">
      <div id="diffhead"><span id="diffTitle">code changes</span><span id="diffPin"></span></div>
      <div id="diff"><span class="ctx">select an iteration to see its diff</span></div>
    </div>
  </div>
</div>

<div id="overlay"><div class="modal">
  <h2>New session</h2>
  <div class="field"><label>Folder</label>
    <div class="row"><input id="fDir" placeholder="/Users/you/runs/my-tool">
      <button style="flex:0 0 auto" onclick="pickFolder()">Browse…</button></div>
    <div id="browser" style="display:none"></div>
    <div class="hint">an empty (or new) folder for this build — or an existing 9xf run to continue</div>
  </div>
  <div class="field"><label>Goal — the unchanging north star</label>
    <textarea id="fGoal" placeholder="Write a CLI tool that organizes files in a directory by type"></textarea></div>
  <div class="field"><label>Mode</label>
    <div class="seg">
      <button id="mReg" class="on" onclick="setMode('')">Regular</button>
      <button id="mOver" onclick="setMode('overnight')">Overnight (max search)</button>
    </div></div>
  <div class="row">
    <div class="field"><label>Model</label><select id="fModel"></select></div>
    <div class="field"><label>Budget</label>
      <div class="row">
        <input id="fIters" type="number" placeholder="iterations" min="1">
        <input id="fHours" type="number" placeholder="hours" step="0.5" min="0.5">
      </div></div>
  </div>
  <div class="err" id="fErr"></div>
  <div class="actions">
    <button onclick="closeNew()">Cancel</button>
    <button class="primary" onclick="startSession()">Start</button>
  </div>
</div></div>

<script>
const $ = id => document.getElementById(id);
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let current = null, pinnedCommit = null, lastDiffCommit = null, lastRender = '';

// ---------- sidebar ----------
async function tickRuns(){
  let runs; try{ runs = await (await fetch('/api/runs')).json(); }catch(e){ return; }
  $('runlist').innerHTML = runs.map(r => `
    <div class="runitem ${current===r.dir?'active':''}" onclick="selectRun('${esc(r.dir)}')">
      <div class="g">${esc(r.goal)}</div>
      <div class="s"><span class="dot ${r.finished?'finished':esc(r.status)}"></span>
        ${r.finished?'finished':esc(r.status)} · iter ${r.iteration}${r.tasks_total?` · ${r.tasks_done}/${r.tasks_total} tasks`:''}</div>
    </div>`).join('') || '<div class="s" style="padding:12px;color:var(--dim)">no sessions yet</div>';
}

function selectRun(dir){ current = dir; pinnedCommit = null; lastRender=''; tickRun(); tickRuns(); }

// ---------- chat ----------
function badge(e){
  if(e.repairs) return `<span class="badge ${e.ok?'ok':'bad'}">${e.ok?'✓ repaired':'✗ repair failed'}</span>`;
  return `<span class="badge ${e.ok?'ok':'bad'}">${e.ok?'✓ validated':'✗ failed'}</span>`;
}
function entryHtml(e){
  if(e.event === 'iteration'){
    const sel = (pinnedCommit && e.commit===pinnedCommit) ? 'selected' : '';
    return `<div class="msg">
      <div class="bubble plan"><div class="who"><span class="m">${esc(e.mode)}</span>
        <span class="iter">iteration ${e.iteration}</span>
        ${e.task_id?`<span class="badge info">T${e.task_id}</span>`:''}
        ${e.stuck.length?`<span class="badge warn">stuck: ${esc(e.stuck.join('+'))}</span>`:''}</div>
        <div class="sub">${esc(e.subtask)}</div></div>
    </div>
    <div class="msg"><div class="bubble exec ${e.ok?'ok':'bad'} ${e.commit?'clickable':''} ${sel}"
        ${e.commit?`onclick="loadDiff('${esc(e.commit)}', true)"`:''}>
      <div class="who">executor ${badge(e)}
        ${e.regression?'<span class="badge bad">regression</span>':''}
        ${e.acceptance===true?'<span class="badge ok">acceptance ✓</span>':''}
        ${e.acceptance===false?'<span class="badge warn">acceptance ✗</span>':''}
        ${e.candidates>1?`<span class="badge info">best of ${e.candidates}</span>`:''}
        ${e.critic==='REVISE'?'<span class="badge warn">critic: revise</span>':''}
        ${e.overflow?'<span class="badge warn">context overflow</span>':''}</div>
      <div class="sum">${esc(e.summary||'(no summary)')}</div>
      ${e.files.length?`<div class="chips">${e.files.map(f=>`<span class="chip">${esc(f)}</span>`).join('')}</div>`:''}
      ${e.tool_runs.map(t=>`<div class="meta">⚙ ${esc(t.name)}: ${esc(t.result)}</div>`).join('')}
      ${e.errors.length?`<div class="errs">${e.errors.map(x=>`<div>${esc(x)}</div>`).join('')}</div>`:''}
      <div class="meta">${e.commit?`<span>${esc(e.commit)} — click for diff</span>`:'<span>no commit</span>'}
        ${e.repairs?`<span>${e.repairs} repair${e.repairs>1?'s':''}</span>`:''}</div>
    </div></div>`;
  }
  if(e.event === 'finished') return `<div class="sys finish">🏁 ${esc(e.summary)}</div>`;
  if(e.event === 'shutdown') return `<div class="sys">■ run stopped — <b>${esc(e.summary)}</b></div>`;
  if(e.event === 'startup')  return `<div class="sys">▶ ${esc(e.summary)}</div>`;
  return `<div class="sys"><b>${esc(e.event)}</b> — ${esc(e.summary)}</div>`;
}

async function tickRun(){
  if(!current) return;
  let r; try{ r = await (await fetch('/api/run?dir='+encodeURIComponent(current))).json(); }catch(e){ return; }
  if(r.error){ return; }
  $('topGoal').textContent = r.goal;
  const pillClass = r.finished ? 'finished' : (r.status==='never started'?'never':r.status);
  $('topPill').textContent = r.finished ? 'finished' : r.status;
  $('topPill').className = 'pill '+pillClass;
  $('taskbar').textContent = r.tasks_total ? `tasks ${r.tasks_done}/${r.tasks_total}` : '';
  const running = r.status==='running';
  $('stopBtn').style.display = running && !r.stop_present ? '' : 'none';
  $('resumeBtn').style.display = (!running && !r.finished) ? '' : 'none';
  const sb = $('statusbar');
  if(running){ sb.style.display='flex';
    sb.innerHTML = `<span class="pulse"></span> <span><b>${esc(r.mode)}</b> — iteration ${r.iteration} of ${r.cap}${r.live_subtask?` — ${esc(r.live_subtask)}`:''}${r.stop_present?' (stopping at the boundary…)':''}</span>`;
  } else { sb.style.display='none'; }

  const html = r.entries.map(entryHtml).join('') || '<div class="empty">starting up…</div>';
  if(html !== lastRender){
    const chat = $('chat');
    const nearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 160;
    chat.innerHTML = html;
    if(nearBottom) chat.scrollTop = chat.scrollHeight;
    lastRender = html;
    if(!pinnedCommit){
      const commits = r.entries.filter(e=>e.commit && e.event==='iteration');
      if(commits.length) loadDiff(commits[commits.length-1].commit, false);
    }
  }
}

// ---------- diff ----------
function colorize(text){
  return text.split('\n').map(l => {
    const e = esc(l);
    if(l.startsWith('diff --git')||l.startsWith('commit')) return `<span class="file">${e}</span>`;
    if(l.startsWith('+++')||l.startsWith('---')) return `<span class="file">${e}</span>`;
    if(l.startsWith('@@')) return `<span class="hunk">${e}</span>`;
    if(l.startsWith('+')) return `<span class="add">${e}</span>`;
    if(l.startsWith('-')) return `<span class="del">${e}</span>`;
    return `<span class="ctx">${e}</span>`;
  }).join('\n');
}
async function loadDiff(commit, pin){
  if(pin){ pinnedCommit = commit; lastRender=''; }
  if(commit === lastDiffCommit && !pin) return;
  lastDiffCommit = commit;
  $('diffTitle').textContent = 'diff @ '+commit;
  $('diffPin').innerHTML = pin ? `<button onclick="unpin()" style="padding:2px 8px;font-size:11px">follow latest</button>` : '';
  let r; try{ r = await (await fetch(`/api/diff?dir=${encodeURIComponent(current)}&commit=${commit}`)).json(); }catch(e){ return; }
  $('diff').innerHTML = r.error ? `<span class="del">${esc(r.error)}</span>` : colorize(r.diff);
}
function unpin(){ pinnedCommit=null; lastRender=''; $('diffPin').innerHTML=''; tickRun(); }

// ---------- controls ----------
$('stopBtn').onclick = async () => {
  await fetch('/api/stop', {method:'POST', body: JSON.stringify({dir: current})}); tickRun();
};
$('resumeBtn').onclick = async () => {
  const r = await (await fetch('/api/start', {method:'POST', body: JSON.stringify({dir: current})})).json();
  if(r.error) alert(r.error); tickRun();
};

// ---------- new session modal ----------
let mode = '';
function setMode(m){ mode=m; $('mReg').className=m?'':'on'; $('mOver').className=m?'on':''; }
function openNew(){ $('overlay').classList.add('show'); $('fErr').textContent=''; loadModels(); }
function closeNew(){ $('overlay').classList.remove('show'); $('browser').style.display='none'; }
$('newBtn').onclick = openNew;
async function loadModels(){
  try{
    const m = await (await fetch('/api/models')).json();
    $('fModel').innerHTML = m.models.map(x=>`<option ${x===m.default?'selected':''}>${esc(x)}</option>`).join('');
  }catch(e){}
}
async function pickFolder(){
  if(window.ninexf && window.ninexf.pickFolder){      // electron: native dialog
    const p = await window.ninexf.pickFolder();
    if(p) $('fDir').value = p;
    return;
  }
  browseTo($('fDir').value || '');                     // browser: server-side picker
}
async function browseTo(path){
  let r; try{ r = await (await fetch('/api/browse?path='+encodeURIComponent(path))).json(); }catch(e){ return; }
  $('fDir').value = r.path;
  const b = $('browser'); b.style.display='block';
  b.innerHTML = (r.parent?`<div class="bi" onclick="browseTo('${esc(r.parent)}')">⬑ ..</div>`:'') +
    r.dirs.map(d=>`<div class="bi" onclick="browseTo('${esc(d.path)}')">📁 ${esc(d.name)} ${d.is_run?'<span class="tag">9xf run</span>':''}</div>`).join('') +
    `<div class="bi" onclick="$('browser').style.display='none'"><b>✓ use this folder</b> — you can append a new subfolder name in the box above</div>`;
}
async function startSession(){
  const payload = {
    dir: $('fDir').value.trim(), goal: $('fGoal').value.trim(), preset: mode,
    model: $('fModel').value || null,
    iterations: $('fIters').value ? parseInt($('fIters').value) : null,
    hours: $('fHours').value ? parseFloat($('fHours').value) : null,
  };
  if(!payload.dir){ $('fErr').textContent='pick a folder first'; return; }
  if(!payload.goal){ $('fErr').textContent='write a goal — one sentence is enough'; return; }
  $('fErr').textContent='starting…';
  let r; try{ r = await (await fetch('/api/start', {method:'POST', body: JSON.stringify(payload)})).json(); }
  catch(e){ $('fErr').textContent='server error'; return; }
  if(r.error){ $('fErr').textContent = r.error; return; }
  closeNew(); selectRun(r.dir);
}

tickRuns(); setInterval(tickRuns, 2500); setInterval(tickRun, 2000);
</script></body></html>"""

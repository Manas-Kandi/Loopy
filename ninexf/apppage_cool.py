"""The `9xf app` page — cool / terminal-HUD mode.

Aesthetic direction: retro-futuristic aerospace terminal. Jet-black with
electric-cyan primary accent, neon green for passing iterations, hot red for
failures. Full monospace everywhere — the whole interface feels like a system
that knows it is computing. Sharp rectangular geometry, no border-radius
softening. Dot-grid background texture on the main canvas. Subtle scanline
overlay. Oscilloscope-style pulse strip with SVG glow filters. Status
indicators are neon-glowing dots, not muted pips.

Constraints: same single-file, fully offline, no external assets, reduced-
motion respected, :focus-visible keyboard styles, color never the sole signal.
"""

APP_PAGE_COOL = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>9xf // neural os</title>
<style>
:root{
  --bg:#050710;
  --panel:#0b0d1a;
  --panel2:#111628;
  --well:#030409;
  --line:#161b2e;
  --line2:#1e2540;
  --cyan:#00e5ff;
  --cyan2:#0099b8;
  --cyan-dim:#003348;
  --cyan-glow:rgba(0,229,255,.12);
  --green:#00ff9f;
  --green-dim:#006644;
  --green-glow:rgba(0,255,159,.15);
  --red:#ff2d55;
  --red-dim:#44001a;
  --amber:#ff9500;
  --blue:#5ac8fa;
  --purple:#bf5af2;
  --txt:#ccd8f0;
  --dim:#4a5878;
  --faint:#222a40;
  --mono:ui-monospace,"SF Mono","Cascadia Code","Fira Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box;margin:0}
html,body{height:100%;overflow:hidden}
body{
  background:var(--bg);color:var(--txt);
  font:12px/1.6 var(--mono);
  display:flex;
  font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased;
}

/* subtle scanline overlay — non-blocking, adds texture */
body::after{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:200;
  background:repeating-linear-gradient(
    0deg,transparent,transparent 3px,rgba(0,0,0,.06) 3px,rgba(0,0,0,.06) 4px
  );
}

::selection{background:var(--cyan);color:#000}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-thumb{background:var(--line2)}
::-webkit-scrollbar-track{background:transparent}
:focus-visible{outline:1px solid var(--cyan);outline-offset:2px}

/* primitives */
.lbl{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}

button{
  font:inherit;font-size:11px;cursor:pointer;color:var(--cyan);
  background:transparent;border:1px solid var(--cyan2);
  padding:5px 14px;
  transition:background .1s,border-color .1s,box-shadow .1s,color .1s;
  text-transform:uppercase;letter-spacing:.08em;border-radius:0;
}
button:hover{
  background:var(--cyan-glow);border-color:var(--cyan);
  box-shadow:0 0 14px var(--cyan-glow);
}
button:active{transform:translateY(1px)}
button:disabled{opacity:.25;cursor:default;transform:none}
button.primary{
  background:transparent;border-color:var(--cyan);color:var(--cyan);font-weight:700;
  box-shadow:inset 0 0 12px var(--cyan-glow),0 0 12px var(--cyan-glow);
}
button.primary:hover{
  background:var(--cyan);color:#000;
  box-shadow:0 0 24px rgba(0,229,255,.5),0 0 48px rgba(0,229,255,.2);
}
button.danger:hover{border-color:var(--red);color:var(--red);background:rgba(255,45,85,.08);box-shadow:0 0 10px rgba(255,45,85,.15)}

input,textarea,select{
  font:inherit;font-size:12px;background:var(--well);color:var(--txt);
  border:1px solid var(--line2);padding:8px 12px;width:100%;
  border-radius:0;outline:none;
}
input:focus,textarea:focus,select:focus{
  border-color:var(--cyan);box-shadow:0 0 0 2px var(--cyan-glow);
}
textarea{resize:vertical;min-height:72px}

@keyframes blink{0%,55%{opacity:1}56%,100%{opacity:0}}
.cursor{animation:blink 1s steps(1) infinite;color:var(--cyan)}

@keyframes fadein{from{opacity:0}to{opacity:1}}

/* glow pulse on the running LED */
@keyframes pulse-glow{
  0%,100%{box-shadow:0 0 4px var(--green),0 0 8px rgba(0,255,159,.3)}
  50%{box-shadow:0 0 8px var(--green),0 0 20px rgba(0,255,159,.5),0 0 36px rgba(0,255,159,.15)}
}

@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}

/* -------- sidebar -------- */
#side{
  width:264px;min-width:264px;background:var(--well);
  display:flex;flex-direction:column;
  border-right:1px solid var(--line);
  transition:width .16s,min-width .16s;
}
#side.collapsed{width:0;min-width:0;overflow:hidden}

#brand{
  padding:18px 18px 14px;
  border-bottom:1px solid var(--line);
}
#brand .sigil{
  font-size:22px;font-weight:700;
  color:var(--cyan);
  letter-spacing:.04em;
  text-shadow:0 0 16px rgba(0,229,255,.5),0 0 32px rgba(0,229,255,.2);
}
#brand .sigil span{color:var(--txt);opacity:.4}
#brand .tag{
  font-size:9px;color:var(--dim);
  text-transform:uppercase;letter-spacing:.18em;
  margin-top:3px;
}

#newBtn{margin:14px 12px 6px;width:calc(100% - 24px);display:block;font-size:11px}

.raillabel{
  padding:10px 18px 4px;
  font-size:9px;color:var(--faint);
  text-transform:uppercase;letter-spacing:.18em;
}
#runlist{flex:1;overflow-y:auto;padding:0 6px}

.runitem{
  display:flex;gap:10px;align-items:flex-start;
  padding:8px 12px;cursor:pointer;
  margin-bottom:1px;position:relative;
  border:1px solid transparent;
  border-left:2px solid transparent;
  transition:background .1s,border-color .1s;
}
.runitem:hover{background:rgba(0,229,255,.05);border-color:var(--line)}
.runitem.active{
  background:rgba(0,229,255,.07);
  border-left-color:var(--cyan);
  border-color:var(--line);
  box-shadow:inset 0 0 24px var(--cyan-glow);
}

.led{width:7px;height:7px;margin-top:5px;border-radius:50%;background:var(--faint);flex:none}
.led.running{background:var(--green);animation:pulse-glow 2s ease-in-out infinite}
.led.finished{background:var(--cyan);box-shadow:0 0 6px var(--cyan)}
.led.failed{background:var(--red);box-shadow:0 0 6px var(--red)}
.led.stale{background:var(--amber);box-shadow:0 0 6px var(--amber)}

.runitem .g{font-size:11px;color:var(--txt);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px}
.runitem .s{font-size:10px;color:var(--dim);margin-top:1px}

#railfoot{
  padding:10px 18px;display:flex;justify-content:space-between;align-items:center;
  font:10px var(--mono);color:var(--faint);
  border-top:1px solid var(--line);
}
#clock{color:var(--cyan);opacity:.6}
#modeSwitch{
  font:9px var(--mono);color:var(--dim);
  border:1px solid var(--faint);padding:2px 8px;
  text-decoration:none;text-transform:uppercase;letter-spacing:.06em;
  transition:color .1s,border-color .1s;
}
#modeSwitch:hover{color:var(--amber);border-color:var(--amber)}

/* -------- main canvas: dot-grid background -------- */
#main{
  flex:1;display:flex;flex-direction:column;min-width:0;
  background-image:radial-gradient(circle,var(--faint) 1px,transparent 1px);
  background-size:24px 24px;
}
#top{background:var(--panel);border-bottom:1px solid var(--line)}

#readouts{display:flex;align-items:center;gap:22px;padding:12px 20px 10px}
.cell{min-width:0}
.cell .val{margin-top:2px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cell.goal{flex:1}
.cell.goal .val{font-size:13px;font-weight:700;color:var(--txt)}
.cell.iter .val{font:700 18px/1.3 var(--mono);color:var(--cyan);text-shadow:0 0 10px rgba(0,229,255,.4)}
.cell.iter .cap{color:var(--dim);font-size:11px;font-weight:400}

.segs{display:flex;gap:2px;margin-top:5px;flex-wrap:wrap;max-width:220px}
.seg{width:8px;height:8px;border-radius:0;background:var(--faint)}
.seg.done{background:var(--green);box-shadow:0 0 4px rgba(0,255,159,.4)}
.seg.cur{background:var(--cyan);box-shadow:0 0 4px rgba(0,229,255,.4)}
.seg.def{background:var(--red);opacity:.55}

.statusword{font-size:11px;text-transform:uppercase;letter-spacing:.1em}
.statusword.running{color:var(--green);text-shadow:0 0 8px rgba(0,255,159,.5)}
.statusword.finished{color:var(--cyan);text-shadow:0 0 8px rgba(0,229,255,.4)}
.statusword.failed{color:var(--red);text-shadow:0 0 6px rgba(255,45,85,.4)}
.statusword.stale{color:var(--amber)}
.statusword.stopped,.statusword.never{color:var(--dim)}
.cell.actions{display:flex;align-items:center;gap:8px}

/* oscilloscope pulse */
#pulsewrap{padding:0 20px 10px}
#pulsewrap .lbl{display:block;margin-bottom:3px}
#pulse{display:block;width:100%;background:var(--well);border:1px solid var(--line)}

/* -------- panes -------- */
#panes{flex:1;display:flex;min-height:0}
.panehead{
  padding:9px 20px 7px;
  font-size:9px;color:var(--dim);
  text-transform:uppercase;letter-spacing:.14em;
  display:flex;justify-content:space-between;align-items:center;gap:8px;
  border-bottom:1px solid var(--line);
  background:var(--panel);
}
#chatwrap{flex:1;display:flex;flex-direction:column;min-width:280px}

.gutter{
  flex:none;width:4px;cursor:col-resize;
  background:var(--line);transition:background .1s;
}
.gutter:hover,.gutter.drag{background:var(--cyan2)}

.iconbtn{
  border:0;background:transparent;color:var(--dim);
  padding:4px 6px;font-size:14px;line-height:1;
  text-transform:none;letter-spacing:0;border-radius:0;
  box-shadow:none;
}
.iconbtn:hover{color:var(--cyan);background:rgba(0,229,255,.08)}

#chat{flex:1;overflow-y:auto;padding:10px 20px 16px;scroll-behavior:smooth}

#statusbar{
  display:none;border-top:1px solid var(--cyan-dim);
  padding:7px 20px;font-size:11px;color:var(--dim);
  align-items:center;gap:10px;
  background:rgba(0,229,255,.04);
}
#statusbar b{color:var(--cyan)}

/* -------- transcript: log-packet cards -------- */
.rec{
  background:var(--panel);
  border:1px solid var(--line);
  border-left:2px solid var(--faint);
  margin:0 auto 4px;max-width:800px;
  overflow:hidden;
}
.rec.selected{border-color:var(--cyan2);box-shadow:0 0 0 1px var(--cyan-glow)}
.rechead{
  display:flex;align-items:center;gap:10px;
  padding:8px 12px;cursor:pointer;
  font-size:11px;color:var(--dim);
  user-select:none;transition:background .1s;
}
.rechead:hover{background:rgba(0,229,255,.05)}
.chev{
  flex:none;color:var(--faint);font-size:9px;width:9px;
  transition:transform .18s cubic-bezier(.4,0,.2,1);
}
.rec.open .chev,.actgroup.open .chev{transform:rotate(90deg)}
.recno{flex:none;font:700 11px var(--mono);color:var(--cyan);opacity:.65}
.recmode{flex:none;color:var(--faint);text-transform:uppercase;font-size:10px;letter-spacing:.06em}
.rectitle{flex:1;min-width:0;color:var(--txt);font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.flag{flex:none;padding:1px 7px;background:transparent;color:var(--dim);font-size:10px;border:1px solid var(--faint);border-radius:0}
.flag.warn{border-color:var(--amber);color:var(--amber)}
.flag.bad{border-color:var(--red);color:var(--red)}
.flag.good{border-color:var(--green);color:var(--green)}

.verdict{margin-left:auto;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.1em}
.verdict.ok{color:var(--green);text-shadow:0 0 8px rgba(0,255,159,.4)}
.verdict.bad{color:var(--red)}

/* smooth height transition */
.recbody{display:grid;grid-template-rows:0fr;transition:grid-template-rows .2s cubic-bezier(.4,0,.2,1)}
.rec.open .recbody{grid-template-rows:1fr}
.rbi{overflow:hidden;min-height:0;padding:0 12px 0 28px}
.rec.open .rbi{padding-bottom:10px}

.recline{display:flex;gap:10px;padding-top:6px}
.recline .lbl{flex:none;width:36px;font-size:10px;text-transform:uppercase;color:var(--faint);padding-top:1px}
.recline .txt{font-size:11.5px;line-height:1.5;word-break:break-word;min-width:0}
.recline.plan .txt{color:var(--txt)}
.recline.execl .txt{color:var(--dim)}

.files{display:flex;flex-wrap:wrap;gap:5px;padding:7px 0 0 46px}
.file{font:10px var(--mono);background:var(--well);border:1px solid var(--line2);padding:1px 8px;color:var(--blue)}

.errblock{
  margin:6px 0 0 46px;padding:6px 10px;
  font:11px/1.5 var(--mono);color:var(--red);word-break:break-word;
  background:rgba(255,45,85,.06);border-left:2px solid var(--red);
}

.recmeta{display:flex;gap:14px;padding:8px 0 0 46px;font-size:10px;color:var(--faint)}
.recmeta .hash{font-family:var(--mono);color:var(--cyan2);cursor:pointer}
.recmeta .hash:hover{color:var(--cyan);text-decoration:underline;text-shadow:0 0 6px rgba(0,229,255,.3)}

/* card left-border state coloring */
.rec.open[data-ok="true"]{border-left-color:var(--green)}
.rec.open[data-ok="false"]{border-left-color:var(--red)}
.rec[data-live="1"]{border-left-color:var(--cyan)}

/* activity groups */
.actgroup{
  max-width:800px;margin:0 auto 4px;
  background:var(--well);border:1px solid var(--line);
}
.actgroup:hover{border-color:var(--line2)}
.acthead{
  display:flex;align-items:center;gap:9px;padding:6px 12px;cursor:pointer;
  font-size:10px;color:var(--faint);user-select:none;
  text-transform:uppercase;letter-spacing:.08em;
}
.actcount{flex:none;font:700 10px var(--mono);color:var(--cyan);opacity:.55}
.actpath{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.actlast{flex:none;max-width:46%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.7}
.actbody{display:grid;grid-template-rows:0fr;transition:grid-template-rows .2s cubic-bezier(.4,0,.2,1)}
.actgroup.open .actbody{grid-template-rows:1fr}
.abi{overflow:hidden;min-height:0}
.actgroup.open .abi{padding:0 12px 8px 28px}
.actrow{display:flex;gap:10px;padding-top:4px;font-size:10.5px;color:var(--faint)}
.actrow .k{flex:none;width:64px;color:var(--cyan);opacity:.55;font-weight:700;text-transform:uppercase}

/* milestone events */
.evt{
  display:flex;align-items:center;justify-content:center;gap:8px;
  max-width:800px;margin:8px auto;color:var(--faint);font-size:10px;
  text-align:center;text-transform:uppercase;letter-spacing:.12em;
}
.evt b{color:var(--dim)}
.evt.finish{color:var(--green)}
.evt.finish b{color:var(--green);text-shadow:0 0 10px rgba(0,255,159,.4)}

/* empty state */
.empty{margin:auto;text-align:center;padding:60px 30px;max-width:480px}
.empty h2{
  font-size:16px;font-weight:700;margin-bottom:14px;color:var(--cyan);
  line-height:1.4;letter-spacing:.06em;
  text-shadow:0 0 20px rgba(0,229,255,.3);
}
.empty h2 b{color:var(--green);text-shadow:0 0 12px rgba(0,255,159,.3)}
.empty p{
  color:var(--dim);font-size:11px;margin-bottom:28px;
  line-height:1.8;text-transform:uppercase;letter-spacing:.06em;
}

/* -------- diff register -------- */
#diffpane{
  flex:none;width:46%;min-width:240px;
  display:flex;flex-direction:column;min-height:0;
  background:var(--well);
  border-left:1px solid var(--line);
}
#diffTitle .hash{font-family:var(--mono);color:var(--cyan);text-shadow:0 0 6px rgba(0,229,255,.3)}
#diff{
  flex:1;overflow:auto;padding:10px 20px 16px;
  font:11px/1.6 var(--mono);white-space:pre;color:var(--dim);
}
#diff.swap{animation:fadein .16s ease}
#diff .add{color:var(--green)}
#diff .del{color:var(--red)}
#diff .hunk{color:var(--amber)}
#diff .file{color:var(--cyan);font-weight:700}
#diff .ctx{color:var(--faint)}

/* -------- modals -------- */
#overlay,#copyOverlay{
  position:fixed;inset:0;background:rgba(0,0,0,.88);
  display:none;align-items:center;justify-content:center;z-index:10;
  backdrop-filter:blur(6px);
}
#overlay.show,#copyOverlay.show{display:flex}
.modal{
  width:560px;max-width:94vw;max-height:90vh;overflow-y:auto;padding:28px;
  background:var(--panel);
  border:1px solid var(--cyan2);
  box-shadow:0 0 60px rgba(0,229,255,.12),0 0 0 1px var(--line);
}
.modal h2{
  font-size:13px;font-weight:700;color:var(--cyan);
  margin-bottom:20px;text-transform:uppercase;letter-spacing:.14em;
  text-shadow:0 0 12px rgba(0,229,255,.4);
}
.field{margin-bottom:16px}
.field .lbl{display:block;margin-bottom:6px}
.row{display:flex;gap:10px}.row>*{flex:1}
.seg-switch{display:flex;border:1px solid var(--line2);overflow:hidden}
.seg-switch button{flex:1;border:0;background:transparent;color:var(--dim);border-radius:0;box-shadow:none}
.seg-switch button.on{background:var(--cyan);color:#000;font-weight:700;box-shadow:0 0 16px rgba(0,229,255,.3)}
.modal .actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}

#browser{
  border:1px solid var(--line2);margin-top:8px;background:var(--well);
  overflow:hidden;display:none;flex-direction:column;max-height:280px;
}
.browpath{
  flex:none;padding:7px 12px;border-bottom:1px solid var(--line);
  font:11px var(--mono);color:var(--cyan2);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.browlist{flex:1;overflow-y:auto;padding:4px}
#browser .bi{padding:6px 10px;cursor:pointer;display:flex;gap:9px;align-items:center;font-size:11px;color:var(--txt)}
#browser .bi:hover{background:rgba(0,229,255,.07)}
#browser .bi.muted{color:var(--faint);cursor:default}
#browser .bi.muted:hover{background:transparent}
#browser .bi .ic{flex:none;width:12px;color:var(--cyan2);text-align:center}
#browser .bi .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#browser .bi .tag{
  flex:none;color:var(--cyan);font-size:9px;
  border:1px solid var(--cyan2);padding:0 6px;
  text-transform:uppercase;letter-spacing:.06em;
}
.browfoot{flex:none;padding:8px 10px;border-top:1px solid var(--line);display:flex;align-items:center;gap:10px}
.browfoot .sel{flex:1;min-width:0;font:10px var(--mono);color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.browfoot button{flex:none;padding:5px 13px;font-size:11px}
.formerr{color:var(--red);font-size:11px;margin-top:8px;min-height:14px}
.hint{color:var(--faint);font-size:10px;margin-top:5px;text-transform:uppercase;letter-spacing:.06em}
.kbd{font:10px var(--mono);color:var(--cyan2);border:1px solid var(--cyan-dim);padding:1px 6px;border-radius:0}
.modal .actions .sp{margin-right:auto;color:var(--faint);font-size:10px;display:flex;align-items:center;gap:6px}
</style></head><body>

<aside id="side">
  <div id="brand">
    <div class="sigil"><span>[</span>9xf<span>]</span></div>
    <div class="tag">Neural loop OS</div>
  </div>
  <button id="newBtn" class="primary" title="New session  (n)" aria-label="New session">+ New session</button>
  <div class="raillabel">Sessions</div>
  <div id="runlist" role="list"></div>
  <div id="railfoot">
    <span id="clock">--:--:-- UTC</span>
    <a id="modeSwitch" href="/" title="Switch to basic mode">basic mode</a>
  </div>
</aside>

<main id="main">
  <header id="top">
    <div id="readouts">
      <button id="sideToggle" class="iconbtn" title="Toggle sidebar  (⌘/Ctrl+B)" aria-label="Toggle sidebar">☰</button>
      <div class="cell goal"><span class="lbl">Goal</span><div class="val" id="topGoal">—</div></div>
      <div class="cell iter"><span class="lbl">Iter</span>
        <div class="val" id="iterRead">···<span class="cap"></span></div></div>
      <div class="cell tasks"><span class="lbl">Tasks</span>
        <div class="val" id="taskRead">—</div><div class="segs" id="taskSegs"></div></div>
      <div class="cell"><span class="lbl">Status</span>
        <div class="val statusword never" id="topPill">no run</div></div>
      <div class="cell actions">
        <button id="copyBtn" style="display:none">Copy diagnostics</button>
        <button id="stopBtn" class="danger" style="display:none">Stop</button>
        <button id="resumeBtn" class="primary" style="display:none">Resume</button>
      </div>
    </div>
    <div id="pulsewrap" style="display:none">
      <span class="lbl">Pulse — iteration waveform</span>
      <div id="pulse"></div>
    </div>
  </header>

  <div id="panes">
    <section id="chatwrap" aria-label="transcript">
      <div class="panehead"><span>// Transcript</span><span id="livehint"></span></div>
      <div id="chat">
        <div class="empty">
          <h2>Awaiting <b>directive</b></h2>
          <p>Set a goal. Pick a folder. A local model plans,<br>
          writes, tests, and commits — autonomously.<br>
          Your machine works. You sleep.</p>
          <button class="primary" onclick="openNew()">Initialize session</button>
        </div>
      </div>
      <div id="statusbar"></div>
    </section>
    <div class="gutter" id="gutter" role="separator" aria-orientation="vertical" title="Drag to resize"></div>
    <section id="diffpane" aria-label="diff register">
      <div class="panehead"><span id="diffTitle">// Diff register</span><span id="diffPin"></span></div>
      <div id="diff"><span class="ctx">select an iteration record to inspect its commit diff</span></div>
    </section>
  </div>
</main>

<div id="overlay" role="dialog" aria-modal="true"><div class="modal">
  <h2>// Initialize session</h2>
  <div class="field"><span class="lbl">Folder</span>
    <div class="row"><input id="fDir" placeholder="/Users/you/runs/my-tool" autocomplete="off">
      <button style="flex:0 0 auto" onclick="pickFolder()">Browse</button></div>
    <div id="browser" style="display:none"></div>
    <div class="hint">new or empty folder — or an existing 9xf run to continue</div>
  </div>
  <div class="field"><span class="lbl">Goal — the immutable directive</span>
    <textarea id="fGoal" placeholder="Write a CLI tool that organizes files in a directory by type"></textarea></div>
  <div class="field"><span class="lbl">Mode</span>
    <div class="seg-switch" role="radiogroup">
      <button id="mReg" class="on" onclick="setMode('')">Regular</button>
      <button id="mOver" onclick="setMode('overnight')">Overnight · max search</button>
    </div></div>
  <div class="row">
    <div class="field"><span class="lbl">Model</span><select id="fModel"></select></div>
    <div class="field"><span class="lbl">Budget</span>
      <div class="row">
        <input id="fIters" type="number" placeholder="iters" min="1">
        <input id="fHours" type="number" placeholder="hours" step="0.5" min="0.5">
      </div></div>
  </div>
  <div class="formerr" id="fErr" role="alert"></div>
  <div class="actions">
    <span class="sp"><span class="kbd">⌘/Ctrl ↵</span> to start</span>
    <button onclick="closeNew()">Cancel</button>
    <button id="startBtn" class="primary" onclick="startSession()">Start</button>
  </div>
</div></div>

<div id="copyOverlay" role="dialog" aria-modal="true"><div class="modal">
  <h2>// Diagnostic bundle</h2>
  <div class="field"><span class="lbl">Copy this text</span>
    <textarea id="copyText" style="min-height:320px"></textarea>
    <div class="hint" id="copyHint">Clipboard access was unavailable, so the bundle is shown here.</div>
  </div>
  <div class="actions">
    <button onclick="$('copyOverlay').classList.remove('show')">Close</button>
  </div>
</div></div>

<script>
const $ = id => document.getElementById(id);
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pad3 = n => String(n).padStart(3,'0');
let current = null, pinnedCommit = null, lastDiffCommit = null, lastRender = '', lastRail = '';
let openIters = new Set(), touched = new Set(), autoIter = null, lastEntries = [];
let openActs = new Set();

setInterval(() => { $('clock').textContent = new Date().toISOString().slice(11,19) + ' UTC'; }, 1000);

/* ---------- sidebar ---------- */
function ledClass(r){
  if (r.finished) return 'finished';
  if (r.status === 'running') return 'running';
  if (r.status === 'failed') return 'failed';
  if (r.status === 'stale') return 'stale';
  return '';
}
async function tickRuns(){
  let runs; try{ runs = await (await fetch('/api/runs')).json(); }catch(e){ return; }
  const html = runs.map(r => `
    <div class="runitem ${current===r.dir?'active':''}" role="listitem" tabindex="0"
         onclick="selectRun('${esc(r.dir)}')" onkeydown="if(event.key==='Enter')selectRun('${esc(r.dir)}')">
      <i class="led ${ledClass(r)}" aria-hidden="true"></i>
      <div><div class="g">${esc(r.goal)}</div>
      <div class="s">${r.finished?'finished':esc(r.status)} · iter ${r.iteration}${r.tasks_total?` · ${r.tasks_done}/${r.tasks_total}`:''}</div></div>
    </div>`).join('') ||
    '<div class="s" style="padding:12px 16px;color:var(--faint);font-size:10px;text-transform:uppercase;letter-spacing:.1em">no sessions on record</div>';
  if (html !== lastRail){ $('runlist').innerHTML = html; lastRail = html; }
}
function selectRun(dir){
  current = dir; pinnedCommit = null; lastRender = ''; lastRail = '';
  openIters = new Set(); touched = new Set(); autoIter = null; lastEntries = [];
  openActs = new Set();
  tickRun(); tickRuns();
}

/* ---------- pulse strip: oscilloscope style ---------- */
function pulseSvg(entries, running){
  const iters = entries.filter(e => e.event === 'iteration').slice(-140);
  const step = 8, w = Math.max(600, iters.length*step + 26), h = 34, base = 21;
  const defs = `<defs>
    <filter id="glow-g" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="1.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow-r" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="1.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow-c" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>`;
  /* subtle grid lines */
  const grid = `<line x1="0" y1="${base}" x2="${w}" y2="${base}" stroke="#161b2e" stroke-width="1"/>`;
  const parts = [defs, grid];
  iters.forEach((e, i) => {
    const x = 8 + i*step;
    parts.push(e.ok
      ? `<line x1="${x}" y1="${base}" x2="${x}" y2="5" stroke="#00ff9f" stroke-width="2" filter="url(#glow-g)"><title>iter ${e.iteration}: validated</title></line>`
      : `<line x1="${x}" y1="${base}" x2="${x}" y2="${h-3}" stroke="#ff2d55" stroke-width="2" filter="url(#glow-r)"><title>iter ${e.iteration}: failed</title></line>`);
  });
  if (running) parts.push(
    `<rect class="cursor" x="${8 + iters.length*step}" y="8" width="5" height="13" fill="#00e5ff" filter="url(#glow-c)"/>`
  );
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMinYMid meet"
    role="img" aria-label="iteration waveform: ${iters.filter(e=>e.ok).length} passed, ${iters.filter(e=>!e.ok).length} failed">${parts.join('')}</svg>`;
}

/* ---------- task segments ---------- */
function segsHtml(tasks){
  return tasks.slice(0, 28).map(t => {
    const c = t.status==='x' ? 'done' : t.status==='!' ? 'def' : t.status==='~' ? 'cur' : '';
    return `<i class="seg ${c}" title="T${t.num} ${esc(t.text)}"></i>`;
  }).join('');
}

/* ---------- transcript ---------- */
function flags(e){
  const f = [];
  if (e.task_id) f.push(`<span class="flag">T${e.task_id}</span>`);
  if (e.repairs) f.push(`<span class="flag ${e.ok?'good':'bad'}">repair×${e.repairs}</span>`);
  if (e.candidates > 1) f.push(`<span class="flag">best/${e.candidates}</span>`);
  if (e.critic === 'REVISE') f.push(`<span class="flag warn">critic revise</span>`);
  if (e.stuck.length) f.push(`<span class="flag warn">stuck ${esc(e.stuck.join('+'))}</span>`);
  if (e.regression) f.push(`<span class="flag bad">regression</span>`);
  if (e.acceptance === true) f.push(`<span class="flag good">acceptance ✓</span>`);
  if (e.acceptance === false) f.push(`<span class="flag warn">acceptance ✗</span>`);
  if (e.overflow) f.push(`<span class="flag warn">ctx overflow</span>`);
  return f.join('');
}
function toggleRec(it){
  it = Number(it);
  if (openIters.has(it)) openIters.delete(it); else openIters.add(it);
  touched.add(it);
  renderTranscript(lastEntries, false);
}
function toggleAct(key){
  if (openActs.has(key)) openActs.delete(key); else openActs.add(key);
  renderTranscript(lastEntries, false);
}
function activityGroupHtml(group){
  const key = 'act' + (group[0].iteration || 0);
  const open = openActs.has(key);
  const path = [...new Set(group.map(g => g.mode).filter(Boolean))].slice(0, 7);
  const last = group[group.length - 1];
  const rows = group.map(g =>
    `<div class="actrow"><span class="k">${esc(g.mode||'')}</span><span>${esc(g.summary)}</span></div>`).join('');
  const n = group.length;
  return `<div class="actgroup ${open?'open':''}">
    <div class="acthead" onclick="toggleAct('${key}')">
      <span class="chev">▶</span>
      <span class="actcount">${n}×</span>
      <span class="actpath">${path.map(esc).join('  ›  ')}</span>
      ${open?'':`<span class="actlast">${esc(last.summary||'')}</span>`}
    </div>
    <div class="actbody"><div class="abi">${rows}</div></div>
  </div>`;
}
function entryHtml(e){
  if (e.event === 'live'){
    return `<article class="rec open" data-live="1">
      <div class="rechead" style="cursor:default">
        <span class="chev" style="visibility:hidden">▶</span>
        <span class="recno">${pad3(e.iteration)}</span>
        <span class="recmode">${esc(e.mode)}</span>
        <span class="rectitle">${esc(e.subtask)}</span>
        <span class="flag warn">live</span>
        <span class="verdict ok"><span class="cursor">▮</span> Running</span>
      </div>
      <div class="recbody"><div class="rbi">
        <div class="recline execl"><span class="lbl">Exec</span><span class="txt">${esc(e.summary)}</span></div>
        <div class="recmeta"><span>not committed yet</span></div>
      </div></div>
    </article>`;
  }
  if (e.event === 'iteration'){
    const open = openIters.has(e.iteration);
    const sel = pinnedCommit && e.commit === pinnedCommit ? 'selected' : '';
    const title = esc(e.subtask || '(no task)');
    return `<article class="rec ${open?'open':''} ${sel}" data-ok="${e.ok}">
      <div class="rechead" onclick="toggleRec(${e.iteration})">
        <span class="chev">▶</span>
        <span class="recno">${pad3(e.iteration)}</span>
        <span class="recmode">${esc(e.mode)}</span>
        <span class="rectitle">${title}</span>
        ${flags(e)}
        <span class="verdict ${e.ok?'ok':'bad'}">${e.ok?'Pass':'Fail'}</span>
      </div>
      <div class="recbody"><div class="rbi">
        <div class="recline plan"><span class="lbl">Plan</span><span class="txt">${title}</span></div>
        <div class="recline execl"><span class="lbl">Exec</span><span class="txt">${esc(e.summary||'(no summary)')}</span></div>
        ${e.files.length?`<div class="files">${e.files.map(f=>`<span class="file">${esc(f)}</span>`).join('')}</div>`:''}
        ${e.model_calls?`<div class="recline execl"><span class="lbl">Model</span><span class="txt">${e.model_calls} call${e.model_calls===1?'':'s'} · ${esc(e.model_seconds)}s</span></div>`:''}
        ${e.tool_runs.map(t=>`<div class="recline execl"><span class="lbl">Tool</span><span class="txt">${esc(t.name)} → ${esc(t.result)}</span></div>`).join('')}
        ${e.warnings&&e.warnings.length?`<div class="errblock" style="color:var(--amber);border-left-color:var(--amber)">${e.warnings.map(x=>esc(x)).join('<br>')}</div>`:''}
        ${e.errors.length?`<div class="errblock">${e.errors.map(x=>esc(x)).join('<br>')}</div>`:''}
        <div class="recmeta">${e.commit?`<span class="hash" onclick="event.stopPropagation();loadDiff('${esc(e.commit)}',true)">${esc(e.commit)}</span><span>view diff →</span>`:'<span>no commit</span>'}</div>
      </div></div>
    </article>`;
  }
  if (e.event === 'finished') return `<div class="evt finish"><b>◉ directive complete</b> ${esc(e.summary)}</div>`;
  if (e.event === 'shutdown') return `<div class="evt">■ halted — <b>${esc(e.summary)}</b></div>`;
  if (e.event === 'startup')  return `<div class="evt">▶ ${esc(e.summary)}</div>`;
  return `<div class="evt"><b>${esc(e.event)}</b> ${esc(e.summary)}</div>`;
}

function renderTranscript(entries, allowScroll){
  let html = '', i = 0;
  while (i < entries.length){
    if (entries[i].event === 'activity'){
      const group = [];
      while (i < entries.length && entries[i].event === 'activity'){ group.push(entries[i]); i++; }
      html += activityGroupHtml(group);
    } else {
      html += entryHtml(entries[i]); i++;
    }
  }
  if (!html) html = '<div class="empty"><p>Initializing…</p></div>';
  if (html === lastRender) return;
  const chat = $('chat');
  const nearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 160;
  chat.innerHTML = html;
  if (allowScroll && nearBottom) chat.scrollTop = chat.scrollHeight;
  lastRender = html;
}

async function tickRun(){
  if (!current) return;
  let r; try{ r = await (await fetch('/api/run?dir='+encodeURIComponent(current))).json(); }catch(e){ return; }
  if (r.error) return;
  $('topGoal').textContent = r.goal;
  $('iterRead').innerHTML = `${pad3(r.iteration)}<span class="cap"> /${r.cap}</span>`;
  $('taskRead').textContent = r.tasks_total ? `${r.tasks_done} of ${r.tasks_total}` : '—';
  $('taskSegs').innerHTML = segsHtml(r.tasks || []);
  const status = r.finished ? 'finished' : (r.status === 'never started' ? 'never' : r.status);
  $('topPill').textContent = r.finished ? '◉ finished' : r.status;
  $('topPill').className = 'val statusword ' + status;
  const running = r.status === 'running';
  $('stopBtn').style.display = running && !r.stop_present ? '' : 'none';
  $('resumeBtn').style.display = (!running && !r.finished) ? '' : 'none';
  $('copyBtn').style.display = current ? '' : 'none';
  $('pulsewrap').style.display = r.entries.some(e => e.event === 'iteration') ? '' : 'none';
  $('pulse').innerHTML = pulseSvg(r.entries, running);

  const sb = $('statusbar');
  if (running){
    sb.style.display = 'flex';
    sb.innerHTML = `<span class="cursor">▮</span><span><b>${esc(r.mode||'…')}</b> — iter ${r.iteration}/${r.cap}${r.live_subtask?` — ${esc(r.live_subtask)}`:''}${r.stop_present?' — stopping at boundary':''}</span>`;
    $('livehint').textContent = 'live · polling 2s';
  } else { sb.style.display = 'none'; $('livehint').textContent = ''; }

  const iterNums = r.entries.filter(e => e.event === 'iteration').map(e => e.iteration);
  const latestIter = iterNums.length ? Math.max(...iterNums) : null;
  if (latestIter !== null && latestIter !== autoIter){
    if (autoIter !== null && !touched.has(autoIter)) openIters.delete(autoIter);
    if (!touched.has(latestIter)) openIters.add(latestIter);
    autoIter = latestIter;
  }
  lastEntries = r.entries;
  renderTranscript(r.entries, true);
  if (!pinnedCommit){
    const commits = r.entries.filter(e => e.commit && e.event === 'iteration');
    if (commits.length) loadDiff(commits[commits.length-1].commit, false);
  }
}

/* ---------- diff register ---------- */
function colorize(text){
  return text.split('\n').map(l => {
    const e = esc(l);
    if (l.startsWith('diff --git') || l.startsWith('commit')) return `<span class="file">${e}</span>`;
    if (l.startsWith('+++') || l.startsWith('---')) return `<span class="file">${e}</span>`;
    if (l.startsWith('@@')) return `<span class="hunk">${e}</span>`;
    if (l.startsWith('+')) return `<span class="add">${e}</span>`;
    if (l.startsWith('-')) return `<span class="del">${e}</span>`;
    return `<span class="ctx">${e}</span>`;
  }).join('\n');
}
async function loadDiff(commit, pin){
  if (pin){ pinnedCommit = commit; lastRender = ''; }
  if (commit === lastDiffCommit && !pin) return;
  lastDiffCommit = commit;
  $('diffTitle').innerHTML = `// Diff register · <span class="hash">${esc(commit)}</span>`;
  $('diffPin').innerHTML = pin ? `<button onclick="unpin()" style="padding:2px 10px;font-size:10px">follow latest</button>` : '';
  let r; try{ r = await (await fetch(`/api/diff?dir=${encodeURIComponent(current)}&commit=${commit}`)).json(); }catch(e){ return; }
  const d = $('diff');
  d.innerHTML = r.error ? `<span class="del">${esc(r.error)}</span>` : colorize(r.diff);
  d.classList.remove('swap'); void d.offsetWidth; d.classList.add('swap');
}
function unpin(){ pinnedCommit = null; lastRender = ''; $('diffPin').innerHTML = ''; tickRun(); }

/* ---------- controls ---------- */
$('stopBtn').onclick = async () => {
  const b = $('stopBtn'); b.disabled = true; b.textContent = 'Stopping…';
  await fetch('/api/stop', {method:'POST', body: JSON.stringify({dir: current})});
  b.disabled = false; b.textContent = 'Stop'; tickRun();
};
$('resumeBtn').onclick = async () => {
  const r = await (await fetch('/api/start', {method:'POST', body: JSON.stringify({dir: current})})).json();
  if (r.error) alert(r.error); tickRun();
};
$('copyBtn').onclick = async () => {
  if (!current) return;
  const btn = $('copyBtn'), old = btn.textContent;
  btn.textContent = 'Copying…';
  let r;
  try{ r = await (await fetch('/api/export?dir='+encodeURIComponent(current))).json(); }
  catch(e){ btn.textContent = 'Copy failed'; setTimeout(()=>btn.textContent=old, 1600); return; }
  if (r.error){ alert(r.error); btn.textContent = old; return; }
  try{
    await navigator.clipboard.writeText(r.text);
    btn.textContent = `Copied ${Math.round((r.chars||r.text.length)/1000)}k`;
    if (r.path) btn.textContent += ' · saved';
    setTimeout(()=>btn.textContent=old, 1800);
  }catch(e){
    $('copyText').value = r.text;
    $('copyHint').textContent = r.path
      ? `Clipboard unavailable. Bundle saved to ${r.path}.`
      : 'Clipboard unavailable. Bundle shown below.';
    $('copyOverlay').classList.add('show');
    $('copyText').focus(); $('copyText').select();
    btn.textContent = old;
  }
};

/* ---------- new session modal ---------- */
let mode = '';
function setMode(m){ mode = m; $('mReg').className = m ? '' : 'on'; $('mOver').className = m ? 'on' : ''; }
function openNew(){ $('overlay').classList.add('show'); $('fErr').textContent=''; loadModels(); $('fGoal').focus(); }
function closeNew(){ $('overlay').classList.remove('show'); $('browser').style.display='none'; }
$('newBtn').onclick = openNew;
const typing = () => /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement||{}).tagName||'');
const modalOpen = () => $('overlay').classList.contains('show');
document.addEventListener('keydown', e => {
  if (e.key === 'Escape'){ closeNew(); $('copyOverlay').classList.remove('show'); return; }
  if ((e.metaKey || e.ctrlKey) && (e.key === 'b' || e.key === 'B')){
    e.preventDefault(); $('side').classList.toggle('collapsed'); return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && modalOpen()){
    e.preventDefault(); startSession(); return;
  }
  if (e.key === 'n' && !typing() && !modalOpen() && !e.metaKey && !e.ctrlKey){
    e.preventDefault(); openNew();
  }
});
async function loadModels(){
  try{
    const m = await (await fetch('/api/models')).json();
    const recommended = new Set(m.recommended || []);
    $('fModel').innerHTML = m.models.map(x => {
      const label = recommended.has(x) ? `${x} · recommended` : x;
      return `<option value="${esc(x)}" ${x===m.default?'selected':''}>${esc(label)}</option>`;
    }).join('');
  }catch(e){}
}
async function pickFolder(){
  if (window.ninexf && window.ninexf.pickFolder){
    try{ const p = await window.ninexf.pickFolder(); if (p) $('fDir').value = p; return; }
    catch(e){}
  }
  browseTo($('fDir').value || '');
}
async function browseTo(path){
  let r; try{ r = await (await fetch('/api/browse?path='+encodeURIComponent(path))).json(); }catch(e){ return; }
  $('fDir').value = r.path;
  const rows = (r.parent
      ? `<div class="bi" onclick="browseTo('${esc(r.parent)}')"><span class="ic">↑</span><span class="nm">..</span></div>`
      : '') +
    (r.dirs.length
      ? r.dirs.map(d=>`<div class="bi" onclick="browseTo('${esc(d.path)}')"><span class="ic">▸</span><span class="nm">${esc(d.name)}</span>${d.is_run?'<span class="tag">9xf run</span>':''}</div>`).join('')
      : '<div class="bi muted"><span class="ic"></span><span class="nm">no subfolders here</span></div>');
  const b = $('browser'); b.style.display = 'flex';
  b.innerHTML =
    `<div class="browpath" title="${esc(r.path)}">${esc(r.path)}${r.is_run?'  ·  existing 9xf run':''}</div>` +
    `<div class="browlist">${rows}</div>` +
    `<div class="browfoot"><span class="sel">use this folder${r.is_run?' (continue run)':''}</span>` +
    `<button class="primary" onclick="$('browser').style.display='none'">Use folder</button></div>`;
}
async function startSession(){
  const payload = {
    dir: $('fDir').value.trim(), goal: $('fGoal').value.trim(), preset: mode,
    model: $('fModel').value || null,
    iterations: $('fIters').value ? parseInt($('fIters').value) : null,
    hours: $('fHours').value ? parseFloat($('fHours').value) : null,
  };
  if (!payload.dir){ $('fErr').textContent = 'Pick a folder first'; return; }
  if (!payload.goal){ $('fErr').textContent = 'Write a goal — one sentence is enough'; return; }
  const btn = $('startBtn');
  btn.disabled = true; btn.textContent = 'Initializing…'; $('fErr').textContent = '';
  let r; try{ r = await (await fetch('/api/start', {method:'POST', body: JSON.stringify(payload)})).json(); }
  catch(e){ $('fErr').textContent = 'Server unreachable'; btn.disabled=false; btn.textContent='Start'; return; }
  if (r.error){ $('fErr').textContent = r.error; btn.disabled=false; btn.textContent='Start'; return; }
  btn.disabled = false; btn.textContent = 'Start';
  closeNew(); selectRun(r.dir);
}

/* ---------- sidebar toggle ---------- */
$('sideToggle').onclick = () => $('side').classList.toggle('collapsed');

/* ---------- resizable split ---------- */
(function(){
  const gutter = $('gutter'), pane = $('diffpane'), panes = $('panes');
  let dragging = false;
  gutter.addEventListener('mousedown', e => {
    dragging = true; gutter.classList.add('drag');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const rect = panes.getBoundingClientRect();
    let w = rect.right - e.clientX;
    w = Math.max(240, Math.min(w, rect.width - 320));
    pane.style.width = w + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false; gutter.classList.remove('drag');
    document.body.style.cursor = ''; document.body.style.userSelect = '';
  });
})();

tickRuns(); setInterval(tickRuns, 2500); setInterval(tickRun, 2000);
</script></body></html>"""

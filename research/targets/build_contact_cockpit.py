#!/usr/bin/env python3
"""Generate contact_cockpit.html: who to contact, what for, and the proof-key per person.

Layers the unified-spine system (ring -> capture-ladder rung -> proof-key -> when -> goal)
onto the scored target universe, so the page answers "who do I talk to, why, what converts
them, and when" at a glance. Reads outreach_universe_scored.json; writes a self-contained
HTML file (data embedded, vanilla JS, no deps, opens offline).

  uv run python research/targets/build_contact_cockpit.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "outreach_universe_scored.json"
OUT = HERE / "contact_cockpit.html"

# ring -> the new spine. R5 (bottleneck operators) is NOT here: it is generated per live
# board call by pope-capture, not harvested into this universe.
SPINE = {
    "advisor":   {"label": "R1 · Advisor",     "rung": "3 · advise (signal)",
                  "proof_key": "ForecastBench rank + the 3-arm ablation",
                  "when": "after FB + ablation",
                  "goal": "credential + warm intros (want only 3-5)", "color": "#8b7bd8"},
    "client":    {"label": "R2 · Client",       "rung": "3 · sell intel",
                  "proof_key": "a forecast that would have made / saved THEM money",
                  "when": "after FB, warm via an advisor",
                  "goal": "paying pilot — revenue = control", "color": "#4fae84"},
    "angel":     {"label": "R3 · Angel",        "rung": "4 · take a position",
                  "proof_key": "record + ablation + ≥1 pilot",
                  "when": "last — only if barter can't fund the moat",
                  "goal": "small SAFE, no board seat", "color": "#d8a64f"},
    "amplifier": {"label": "R4 · Amplifier",    "rung": "1 · be seen",
                  "proof_key": "the live scored board + FB result",
                  "when": "right after FB",
                  "goal": "broadcast the record (inbound)", "color": "#4fa6d8"},
    "client-vc": {"label": "R2/3 · Client-VC",  "rung": "3-4 · sell / position",
                  "proof_key": "record + ablation",
                  "when": "after FB",
                  "goal": "intro + capital / distribution", "color": "#d86f9b"},
}

KEEP = ["name", "role", "profile", "ring", "segment", "channel", "contact", "to_email",
        "confidence", "fit_score", "priority_tier", "specific_hook", "fit_reason", "cta",
        "subject", "day0", "day3", "source", "message_source"]


def trim(r):
    o = {k: (r.get(k) or "") for k in KEEP}
    try:
        o["fit_score"] = int(float(o["fit_score"]))
    except (ValueError, TypeError):
        o["fit_score"] = 0
    o["sendable"] = bool(r.get("to_email"))
    return o


def main():
    data = [trim(r) for r in json.loads(SRC.read_text())]
    data.sort(key=lambda r: r["fit_score"], reverse=True)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data))
            .replace("__SPINE__", json.dumps(SPINE)))
    OUT.write_text(html)
    n_send = sum(1 for r in data if r["sendable"])
    print(f"wrote {OUT}  ({len(data)} people, {n_send} with direct email)")


TEMPLATE = r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vaticinus · Contact Cockpit</title>
<style>
  :root{ --bg:#0d0f14; --panel:#161a22; --panel2:#1d2230; --line:#2a3142; --ink:#e7ecf4;
         --dim:#8a94a8; --accent:#cfd8ea; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:14px/1.5 ui-sans-serif,-apple-system,Segoe UI,Roboto,Helvetica,Arial}
  a{color:#8fb6ff}
  .wrap{max-width:1280px;margin:0 auto;padding:24px 20px 80px}
  h1{font-size:20px;letter-spacing:.2px;margin:0 0 2px}
  .sub{color:var(--dim);font-size:13px;margin-bottom:18px}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  .banner{background:#27210f;border:1px solid #5b4a18;color:#e8d29a;border-radius:8px;
          padding:9px 13px;font-size:12.5px;margin-bottom:18px}
  /* spine legend */
  .spine{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:20px}
  .card{background:var(--panel);border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:11px 13px}
  .card .lab{font-weight:600;font-size:13px;margin-bottom:6px}
  .card .kv{font-size:11.5px;color:var(--dim);margin:2px 0}
  .card .kv b{color:var(--accent);font-weight:500}
  /* controls */
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px;
            position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
  input[type=search]{background:var(--panel2);border:1px solid var(--line);color:var(--ink);
       border-radius:7px;padding:7px 11px;width:230px;font-size:13px}
  .seg{display:inline-flex;background:var(--panel);border:1px solid var(--line);border-radius:7px;overflow:hidden}
  .seg button{background:none;border:0;color:var(--dim);padding:6px 11px;font-size:12px;cursor:pointer}
  .seg button.on{background:var(--panel2);color:var(--ink)}
  .toggle{font-size:12px;color:var(--dim);display:inline-flex;gap:6px;align-items:center;cursor:pointer;user-select:none}
  .count{margin-left:auto;color:var(--dim);font-size:12px}
  /* table */
  table{width:100%;border-collapse:collapse}
  th{ text-align:left;color:var(--dim);font-weight:500;font-size:11px;text-transform:uppercase;
      letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid var(--line)}
  td{padding:9px 10px;border-bottom:1px solid #1b2030;vertical-align:top}
  tr.row{cursor:pointer}
  tr.row:hover{background:#12161f}
  .chip{display:inline-block;font-size:11px;padding:1px 8px;border-radius:20px;font-weight:600;white-space:nowrap}
  .tier{font-size:10.5px;color:var(--dim);font-family:ui-monospace,monospace}
  .nm{font-weight:600}
  .role{color:var(--dim);font-size:12px}
  .sc{font-family:ui-monospace,monospace;color:var(--accent)}
  .goal{font-size:12px}
  .mailpill{font-size:10px;color:#4fae84;border:1px solid #2c5a44;border-radius:10px;padding:0 6px;margin-left:6px}
  tr.detail td{background:#10141d;border-bottom:1px solid var(--line);padding:14px 18px}
  .detail .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .detail h4{margin:0 0 5px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--dim)}
  .msg{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:11px;
       white-space:pre-wrap;font-size:12.5px;color:#d7deea}
  .hidden{display:none}
  .why{font-size:12.5px}
</style></head>
<body><div class="wrap">
  <h1>Vaticinus · Contact Cockpit</h1>
  <div class="sub">Who to contact, what for, and the exact proof that converts them. Ring → capture-ladder rung → proof-key → when → goal.</div>
  <div class="banner"><b>Hold before sending.</b> The list is for review and sequencing now. Don't send until the proof lands (live board + ForecastBench, June 21). Every auto-harvested row is verify-before-contact.</div>

  <div id="spine" class="spine"></div>

  <div class="controls">
    <input id="q" type="search" placeholder="search name / role / hook…" autocomplete="off">
    <span class="seg" id="ringSeg"></span>
    <span class="seg" id="tierSeg">
      <button data-t="P0P1" class="on">P0+P1</button>
      <button data-t="all">all tiers</button>
      <button data-t="P2-enrich-scaled">P2</button>
      <button data-t="P3-universe-hold">P3</button>
    </span>
    <label class="toggle"><input type="checkbox" id="send"> direct-email only</label>
    <span class="count" id="count"></span>
  </div>

  <table>
    <thead><tr>
      <th>Name</th><th>Ring</th><th>Tier</th><th>Why them (hook)</th>
      <th>Score</th><th>What for (goal)</th><th>Proof-key</th>
    </tr></thead>
    <tbody id="body"></tbody>
  </table>
</div>

<script>
const DATA = __DATA__;
const SPINE = __SPINE__;

// spine legend
document.getElementById('spine').innerHTML = Object.entries(SPINE).map(([k,s])=>`
  <div class="card" style="border-left-color:${s.color}">
    <div class="lab" style="color:${s.color}">${s.label}</div>
    <div class="kv">rung · <b>${s.rung}</b></div>
    <div class="kv">proof-key · <b>${s.proof_key}</b></div>
    <div class="kv">when · <b>${s.when}</b></div>
    <div class="kv">goal · <b>${s.goal}</b></div>
  </div>`).join('') +
  `<div class="card" style="border-left-color:#586079">
    <div class="lab" style="color:#9aa3ba">R5 · Operator (Builder)</div>
    <div class="kv">not in this list — generated per live board call by <b>pope-capture</b></div>
    <div class="kv">rung · <b>1-2 · be useful / broker / barter</b></div>
    <div class="kv">proof-key · <b>a specific correct insight about THEIR world</b></div>
    <div class="kv">when · <b>now (proof-agnostic)</b></div>
  </div>`;

// ring filter buttons
const rings = ['all', ...Object.keys(SPINE)];
document.getElementById('ringSeg').innerHTML = rings.map((r,i)=>
  `<button data-r="${r}" class="${i===0?'on':''}">${r==='all'?'all rings':SPINE[r].label.split(' · ')[0]}</button>`).join('');

let ring='all', tier='P0P1', q='', sendOnly=false;
const esc = s => String(s||'').replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function pass(r){
  if(ring!=='all' && r.ring!==ring) return false;
  if(tier==='P0P1' && !(r.priority_tier==='P0-founder-1to1'||r.priority_tier==='P1-personal-1to1')) return false;
  if(tier!=='all' && tier!=='P0P1' && r.priority_tier!==tier) return false;
  if(sendOnly && !r.sendable) return false;
  if(q){ const h=(r.name+' '+r.role+' '+r.segment+' '+r.specific_hook+' '+r.fit_reason).toLowerCase();
         if(!h.includes(q)) return false; }
  return true;
}

function render(){
  const rows = DATA.filter(pass);
  const body = document.getElementById('body');
  body.innerHTML = rows.map((r,i)=>{
    const s = SPINE[r.ring] || {color:'#586079',goal:'',proof_key:'',rung:'',when:''};
    const tierShort = (r.priority_tier||'').split('-')[0];
    const mail = r.sendable ? `<span class="mailpill">email</span>` : '';
    return `<tr class="row" data-i="${i}">
      <td><span class="nm">${esc(r.name)}</span>${mail}<div class="role">${esc(r.role||r.profile)}</div></td>
      <td><span class="chip" style="background:${s.color}22;color:${s.color}">${esc(s.label||r.ring)}</span></td>
      <td class="tier">${esc(tierShort)}</td>
      <td class="why">${esc(r.specific_hook||r.fit_reason)}</td>
      <td class="sc">${r.fit_score}</td>
      <td class="goal">${esc(s.goal)}</td>
      <td class="why" style="color:var(--dim)">${esc(s.proof_key)}</td>
    </tr>
    <tr class="detail hidden" data-d="${i}"><td colspan="7">
      <div class="grid">
        <div>
          <h4>Why them</h4><div class="why">${esc(r.fit_reason||r.specific_hook)}</div>
          <h4 style="margin-top:12px">Capture plan</h4>
          <div class="kv why">rung · ${esc(s.rung)} &nbsp;·&nbsp; when · ${esc(s.when)}</div>
          <div class="kv why">goal · ${esc(s.goal)}</div>
          <div class="kv why">proof-key · ${esc(s.proof_key)}</div>
          <h4 style="margin-top:12px">Contact</h4>
          <div class="why mono">${esc(r.contact||r.to_email||'— needs enrichment —')} &nbsp;<span style="color:var(--dim)">(${esc(r.channel)}, ${esc(r.confidence)})</span></div>
          <div class="why" style="color:var(--dim)">source: ${esc(r.source)} · copy: ${esc(r.message_source)}</div>
        </div>
        <div>
          <h4>Subject</h4><div class="why">${esc(r.subject)}</div>
          <h4 style="margin-top:10px">Day 0 message (give-before-ask)</h4>
          <div class="msg">${esc(r.day0)}</div>
          ${r.day3?`<h4 style="margin-top:10px">Day 3 nudge</h4><div class="msg">${esc(r.day3)}</div>`:''}
        </div>
      </div>
    </td></tr>`;
  }).join('');
  document.getElementById('count').textContent = `${rows.length} of ${DATA.length} people`;
}

document.getElementById('body').addEventListener('click', e=>{
  const row = e.target.closest('tr.row'); if(!row) return;
  const d = document.querySelector(`tr.detail[data-d="${row.dataset.i}"]`);
  if(d) d.classList.toggle('hidden');
});
document.getElementById('q').addEventListener('input', e=>{ q=e.target.value.trim().toLowerCase(); render(); });
document.getElementById('send').addEventListener('change', e=>{ sendOnly=e.target.checked; render(); });
document.getElementById('ringSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return; ring=b.dataset.r;
  document.querySelectorAll('#ringSeg button').forEach(x=>x.classList.toggle('on', x===b)); render(); });
document.getElementById('tierSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return; tier=b.dataset.t;
  document.querySelectorAll('#tierSeg button').forEach(x=>x.classList.toggle('on', x===b)); render(); });

render();
</script>
</body></html>'''


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build an HTML panel for the scored outreach and email-enrichment exports."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
SCORED = HERE / "outreach_universe_scored.json"
ENRICH = HERE / "public_email_enrichment_top300.csv"
OUT = ROOT / "outreach_panel.html"


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows = json.loads(SCORED.read_text())
    enrich_by_rank = {str(r.get("rank")): r for r in load_csv(ENRICH)}
    for row in rows:
        e = enrich_by_rank.get(str(row.get("rank")))
        row["found_email_status"] = e.get("found_email_status", "") if e else ""
        row["found_email"] = e.get("found_email", "") if e else ""
        row["enriched_to_email"] = e.get("enriched_to_email", "") if e else ""
        row["email_source_url"] = e.get("email_source_url", "") if e else ""
        row["panel_email_state"] = (
            "strict-ready"
            if row.get("found_email_status") in {"confirmed_existing", "found_public_high"}
            else "candidate"
            if row.get("found_email_status") == "found_public_possible"
            else "not-found"
            if row.get("found_email_status") == "not_found"
            else "not-checked"
        )

    html = TEMPLATE.replace("/*DATA*/", json.dumps(rows, ensure_ascii=False))
    OUT.write_text(html)
    print(f"Wrote {OUT} with {len(rows)} rows")


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vaticinus Outreach Panel</title>
<style>
:root{--bg:#0b0d10;--panel:#131820;--line:#27303d;--ink:#e9edf2;--dim:#8d98a8;--blue:#87b7ff;--green:#65d6a6;--amber:#e7c76b;--red:#ef8888;--violet:#c9a4ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
header{position:sticky;top:0;z-index:5;background:#0b0d10f2;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:18px 22px 12px}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--dim);max-width:1040px;font-size:12px}
.stats{display:grid;grid-template-columns:repeat(8,minmax(92px,1fr));gap:8px;margin-top:12px}
.stat{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:8px}.stat b{font-size:17px;display:block}.stat span{color:var(--dim);font-size:11px}
.wrap{padding:14px 22px 60px}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
input[type=search]{background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--ink);padding:8px 11px;min-width:260px;outline:none}
input[type=search]:focus{border-color:var(--blue)}.chip{border:1px solid var(--line);background:var(--panel);color:var(--dim);border-radius:999px;padding:5px 10px;font-size:11px;cursor:pointer;user-select:none}
.chip.on{background:var(--blue);border-color:var(--blue);color:#06101f;font-weight:700}.label{font-size:10px;color:#5e6877;text-transform:uppercase;letter-spacing:.6px;margin-left:8px}
.count{color:var(--dim);font-size:12px;margin:8px 0}
table{width:100%;border-collapse:collapse}th{position:sticky;top:109px;background:#0b0d10;text-align:left;color:#647084;font-size:10px;text-transform:uppercase;letter-spacing:.5px;padding:7px 8px;border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid #1d2430;vertical-align:top}tr:hover td{background:#10151c}
.name{font-weight:700;white-space:nowrap}.role{color:#c8d0dc;max-width:380px}.muted{color:var(--dim)}
.pill{display:inline-block;border:1px solid var(--line);border-radius:5px;padding:1px 6px;font-size:10px;white-space:nowrap;color:var(--dim)}
.tier-P0-founder-1to1{color:#07120d;background:var(--green);border-color:var(--green);font-weight:700}.tier-P1-personal-1to1{color:#07101f;background:var(--blue);border-color:var(--blue);font-weight:700}
.state-strict-ready{color:#06120d;background:var(--green);border-color:var(--green);font-weight:700}.state-candidate{color:#1b1302;background:var(--amber);border-color:var(--amber);font-weight:700}
.state-not-found{color:#311010;background:#ef888830;border-color:#ef888866}.state-not-checked{color:#858fa0}
.copy{max-width:520px;color:#d6dce5}.email{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}th:nth-child(7),td:nth-child(7),th:nth-child(8),td:nth-child(8){display:none}}
</style></head><body>
<header>
<h1>Vaticinus Outreach Panel</h1>
<div class="sub">Scored outreach universe with message and email-enrichment status. Nothing here is send-authorized: strict-ready emails still have <b>hold/final-verify</b> status.</div>
<div class="stats" id="stats"></div>
</header>
<div class="wrap">
<div class="controls">
<input id="q" type="search" placeholder="Search name, role, hook, email...">
<span class="label">Tier</span><span id="tier"></span>
<span class="label">Email</span><span id="state"></span>
<span class="label">Ring</span><span id="ring"></span>
<span class="label">Channel</span><span id="channel"></span>
</div>
<div class="count" id="count"></div>
<table><thead><tr><th>#</th><th>Name</th><th>Tier</th><th>Ring</th><th>Channel</th><th>Email</th><th>Hook</th><th>Day 0</th></tr></thead><tbody id="tb"></tbody></table>
</div>
<script>
const P=/*DATA*/;
const st={q:"",tier:new Set(),state:new Set(),ring:new Set(),channel:new Set()};
const esc=s=>(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
function vals(k){return [...new Set(P.map(x=>x[k]||"").filter(Boolean))].sort();}
function chipBox(id,key,items){const el=document.getElementById(id);items.forEach(v=>{const c=document.createElement("span");c.className="chip";c.textContent=v;c.onclick=()=>{st[key].has(v)?st[key].delete(v):st[key].add(v);c.classList.toggle("on");render();};el.appendChild(c);});}
function ok(r){if(st.q){const s=[r.name,r.role,r.profile,r.specific_hook,r.day0,r.found_email,r.enriched_to_email,r.contact].join(" ").toLowerCase();if(!s.includes(st.q))return false}
 for(const k of ["tier","state","ring","channel"]){const field=k==="tier"?"priority_tier":k==="state"?"panel_email_state":k;if(st[k].size&&!st[k].has(r[field]||""))return false}
 return true}
function linkFor(r){const c=r.contact||"";if(r.channel==="email")return"mailto:"+c;if(r.channel==="x"){const h=c.replace(/^@/,"");return c.startsWith("http")?c:"https://x.com/"+h}return c.startsWith("http")?c:"#"}
function render(){const L=P.filter(ok);document.getElementById("count").textContent=`${L.length} of ${P.length} rows`;
document.getElementById("tb").innerHTML=L.slice(0,2000).map(r=>{const email=r.enriched_to_email||r.to_email||r.found_email||"";const emailHtml=email?`<div class="email">${esc(email)}</div>`:"";const src=r.email_source_url?`<a href="${esc(r.email_source_url)}" target="_blank">source</a>`:"";return `<tr>
<td>${r.rank}</td><td class="name"><a href="${linkFor(r)}" target="_blank">${esc(r.name)}</a><div class="muted">${esc((r.role||r.profile||"").slice(0,90))}</div></td>
<td><span class="pill tier-${esc(r.priority_tier)}">${esc(r.priority_tier)}</span></td><td>${esc(r.ring)}</td><td>${esc(r.channel)}</td>
<td><span class="pill state-${esc(r.panel_email_state)}">${esc(r.panel_email_state)}</span>${emailHtml}<div>${src}</div></td>
<td class="role">${esc(r.specific_hook)}</td><td class="copy">${esc((r.day0||"").slice(0,260))}</td></tr>`}).join("")}
function stats(){const n=k=>P.filter(x=>x.panel_email_state===k).length;const t=k=>P.filter(x=>x.priority_tier===k).length;document.getElementById("stats").innerHTML=[
["Total",P.length],["P0/P1",t("P0-founder-1to1")+t("P1-personal-1to1")],["Contactable",P.filter(x=>!["openalex","orcid"].includes(x.channel)&&x.contact).length],["Strict Email",n("strict-ready")],["Candidates",n("candidate")],["Not Found",n("not-found")],["Not Checked",n("not-checked")],["Hold",P.filter(x=>(x.send_status||"").startsWith("hold")).length]
].map(([a,b])=>`<div class="stat"><b>${b}</b><span>${a}</span></div>`).join("")}
chipBox("tier","tier",["P0-founder-1to1","P1-personal-1to1","P2-enrich-scaled","P3-universe-hold"]);
chipBox("state","state",["strict-ready","candidate","not-found","not-checked"]);
chipBox("ring","ring",vals("ring"));chipBox("channel","channel",vals("channel"));
document.getElementById("q").oninput=e=>{st.q=e.target.value.toLowerCase();render()};stats();render();
</script></body></html>"""


if __name__ == "__main__":
    main()

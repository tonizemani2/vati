#!/usr/bin/env python3
"""Merge all target sources -> dedupe -> targets.json + targets_panel.html."""
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent  # research/
RESEARCHER_CAP = 2400

# --- round-1 curated 33 (have bespoke messages in outreach_messages.md) -------
R1 = [
 ("Eli Lifland","AI Futures Project; #1 all-time RAND FI","advisor","forecasting-authority","x","@eli_lifland"),
 ("Ezra Karger","FRI; lead author of ForecastBench","advisor","benchmark-creator","email","ezra.karger@chi.frb.org"),
 ("Danny Halawi","First author, LLM-forecasting paper","advisor","applied-ai","email","dhalawi@berkeley.edu"),
 ("Nuño Sempere","Forecasting Newsletter; Samotsvety","advisor","forecasting-authority","email","nuno.semperelh@protonmail.com"),
 ("Peter Wildeford","Metaculus board; IAPS","advisor","market-insider","email","peter@iaps.ai"),
 ("Tom Liptay","Metaculus AIB; FutureSearch","advisor","market-insider","x","@TLiptay"),
 ("Molly Hickman","Metaculus PM; AIB co-author","advisor","market-insider","x","@celloMolly"),
 ("wasabipesto","brier.fyi / Calibration City","advisor","market-insider","email","contact@wasabipesto.com"),
 ("Phil Godzin","Top Metaculus AIB bot (pgodzinai)","advisor","applied-ai","x","@pgodzin"),
 ("Warren Hatch","CEO, Good Judgment","advisor","quant-forecasting","linkedin","https://www.linkedin.com/in/warren-hatch"),
 ("Agustin Lebron","Ex-Jane Street; Laws of Trading","advisor","quant","x","@AgustinLebron3"),
 ("Corey Hoffstein","Newfound; Flirting with Models","advisor","quant","x","@choffstein"),
 ("Misha Yagudin","Samotsvety; Arb Research","advisor","forecasting-authority","email","mike.yagudin@gmail.com"),
 ("Robin Hanson","GMU; prediction-market pioneer","advisor","market-pioneer","email","rhanson@gmu.edu"),
 ("Nate Silver","Silver Bulletin; advises Polymarket","advisor","forecasting-authority","email","silverbulletin.media@gmail.com"),
 ("Joey Krug","Augur; Founders Fund partner","angel","ai-forecasting-investor","email","joey@foundersfund.com"),
 ("Adhi Rajaprabhakaran","5c(c) Capital (prediction-market VC)","angel","ai-forecasting-investor","x","@eightyhi"),
 ("Robert de Neufville","Telling the Future podcast","amplifier","media-voice","web","https://tellingthefuture.substack.com"),
 ("Dustin Gouker","The Event Horizon newsletter","amplifier","media-voice","x","@DustinGouker"),
 ("Zvi Mowshowitz","Don't Worry About the Vase","amplifier","media-voice","x","@TheZvi"),
 ("Saul Munn","Organizes Manifest","amplifier","media-voice","x","@saulmunn"),
 ("Austin Chen","Manifold / Manifund","angel","applied-ai-angel","email","akrolsmir@gmail.com"),
 ("Panshul42","Won Metaculus Q2 AI Benchmark","advisor","applied-ai","web","https://github.com/Panshul42"),
 ("Barbara Mellers","UPenn; GJP co-founder","advisor","academic","email","mellers@wharton.upenn.edu"),
 ("Don Moore","Berkeley Haas; GJP co-founder","advisor","academic","email","dmoore@haas.berkeley.edu"),
 ("Lyle Ungar","UPenn; silicon-crowd paper","advisor","academic","email","ungar@cis.upenn.edu"),
 ("Jacob Steinhardt","Berkeley; MMLU; LLM-forecasting","advisor","applied-ai","email","jsteinhardt@berkeley.edu"),
 ("Pavel Atanasov","IE University; aggregation","advisor","academic","email","pavel.atanasov@ie.edu"),
 ("Joshua D. Clinton","Vanderbilt; market-scoring study","advisor","academic","email","josh.clinton@vanderbilt.edu"),
 ("Anthony Aguirre","Metaculus co-founder; FLI","advisor","market-insider","email","aguirre@scipp.ucsc.edu"),
 ("Josh Rosenberg","CEO, FRI","advisor","forecasting-org","email","info@forecastingresearch.org"),
 ("Richard Craib","Founder, Numerai","advisor","quant","x","@richardcraib"),
 ("Andreas Stuhlmüller","Ought / Elicit","advisor","applied-ai","email","andreas@stuhlmueller.org"),
]

def norm(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii","ignore").decode().lower()
    n = re.sub(r"[^a-z0-9 ]","",n)
    return re.sub(r"\s+"," ",n).strip()

def load_jsonl(p):
    if not p.exists(): return []
    out=[]
    for line in p.read_text().splitlines():
        line=line.strip()
        if line:
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def main():
    rows=[]
    seen=set()
    def add(rec):
        k=norm(rec["name"])
        if not k or k in seen: return
        seen.add(k); rows.append(rec)

    # 1) round-1 (priority, flagged)
    for n,role,ring,seg,chan,contact in R1:
        add({"name":n,"role":role,"profile":role,"ring":ring,"segment":seg,"vein":seg,
             "channel":chan,"contact":contact,"source":"round-1","confidence":"high",
             "tier1":True,"has_message":True})

    # 2) salvaged curated angels
    for r in load_jsonl(HERE/"angels_salvage.jsonl"):
        r.setdefault("role",r.get("vein","")); r["tier1"]=False; r["has_message"]=False
        add(r)

    # 3) OpenAlex researchers (cap)
    res=load_jsonl(HERE/"researchers_openalex.jsonl")
    res.sort(key=lambda r:r.get("works_on_topic",0),reverse=True)
    for r in res[:RESEARCHER_CAP]:
        topics=", ".join(t for t in r.get("topics",[])[:2])
        add({"name":r["name"],"role":r.get("affiliation",""),
             "profile":f'{r.get("affiliation","")} · {r.get("works_on_topic",0)} works ({topics})',
             "ring":"advisor","segment":"researcher","vein":r.get("vein","researcher"),
             "channel":"orcid" if r.get("orcid") else "openalex",
             "contact":(f'https://orcid.org/{r["orcid"]}' if r.get("orcid") else r.get("openalex","")),
             "source":r.get("openalex",""),"confidence":"high","tier1":False,"has_message":False})

    # 4) keyless-Exa harvest
    for r in load_jsonl(HERE/"harvest_web.jsonl"):
        r.setdefault("role",""); r["tier1"]=False; r["has_message"]=False
        add(r)

    (HERE/"targets.json").write_text(json.dumps(rows,ensure_ascii=False))
    # summary
    from collections import Counter
    by_ring=Counter(r["ring"] for r in rows)
    by_conf=Counter(r.get("confidence","") for r in rows)
    print(f"TOTAL {len(rows)} unique people")
    print("by ring:",dict(by_ring))
    print("by confidence:",dict(by_conf))
    write_html(rows)
    print(f"-> {ROOT/'targets_panel.html'}")

def write_html(rows):
    data=json.dumps(rows,ensure_ascii=False)
    html=PANEL_TMPL.replace("/*DATA*/", data)
    (ROOT/"targets_panel.html").write_text(html)

PANEL_TMPL=r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vaticinus — Target Universe</title>
<style>
:root{--bg:#0b0e14;--panel:#121722;--line:#232b3d;--ink:#e6ebf2;--dim:#8a97ad;--accent:#6ea8fe;--good:#5fd0a0;--warn:#e8c468;--gold:#f0c674}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{padding:18px 22px 12px;border-bottom:1px solid var(--line);position:sticky;top:0;background:#0b0e14f2;backdrop-filter:blur(4px);z-index:5}
h1{margin:0 0 3px;font-size:18px}.sub{color:var(--dim);font-size:12px;max-width:900px}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:var(--dim)}.stats b{color:var(--ink);font-size:15px;display:block}
.wrap{padding:14px 22px 60px}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
input[type=search]{background:var(--panel);border:1px solid var(--line);color:var(--ink);padding:7px 11px;border-radius:8px;min-width:220px;outline:none}
input[type=search]:focus{border-color:var(--accent)}
.chip{padding:4px 10px;border:1px solid var(--line);border-radius:999px;background:var(--panel);color:var(--dim);cursor:pointer;font-size:11px;user-select:none}
.chip.on{background:var(--accent);border-color:var(--accent);color:#06101f;font-weight:600}
.glabel{font-size:10px;color:#5a6678;text-transform:uppercase;letter-spacing:.6px;margin:0 2px 0 8px}
.count{color:var(--dim);font-size:12px;margin:0 0 8px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#5a6678;padding:6px 8px;border-bottom:1px solid var(--line);position:sticky;top:96px;background:#0b0e14}
td{padding:6px 8px;border-bottom:1px solid #1a2130;vertical-align:top}
tr:hover td{background:#10151f}
.nm{font-weight:600;white-space:nowrap}.star{color:var(--gold)}
.rl{color:var(--dim);max-width:420px}
.bdg{font-size:9px;padding:1px 6px;border-radius:5px;border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.ring-client{background:#16263f;color:#9cc4ff}.ring-angel{background:#10261c;color:#6fe0ad}.ring-advisor{background:#2a1d3a;color:#d6b3ff}.ring-amplifier{background:#2f2616;color:#f0c674}.ring-client-vc{background:#16263f;color:#9cc4ff}
.cf-high{color:var(--good)}.cf-med{color:var(--warn)}.cf-low{color:#7a8699}
.msgflag{font-size:9px;color:var(--good);border:1px solid #1f573d;border-radius:5px;padding:1px 5px}
.foot{color:#5a6678;font-size:11px;margin-top:18px}
</style></head><body>
<header>
<h1>Vaticinus — Target Universe</h1>
<div class="sub">Full prospecting list across advisors, clients, angels and amplifiers. Harvested keyless (Exa + OpenAlex), deduped. Confidence: high = verified source / OpenAlex author / curated; med/low = auto-extracted profile, verify before outreach. ★ = curated round-1 with a bespoke message in outreach_messages.md. The curated 33 with messages also live in <a href="people_panel.html">people_panel.html</a>.</div>
<div class="stats" id="stats"></div>
</header>
<div class="wrap">
<div class="controls">
<input type="search" id="q" placeholder="Search name, role, firm…">
<span class="glabel">Ring</span><span id="ringChips"></span>
<span class="glabel">Channel</span><span id="chanChips"></span>
<span class="glabel">Conf</span><span id="confChips"></span>
<span class="chip" id="t1">★ round-1 only</span>
</div>
<div class="count" id="count"></div>
<table><thead><tr><th>Name</th><th>Role / firm</th><th>Ring</th><th>Segment</th><th>Chan</th><th>Conf</th><th>Contact</th></tr></thead>
<tbody id="tb"></tbody></table>
<div class="foot">Round 1, 2026-06-17. Email/phone enrichment for med/low rows = the orca Exa-Websets pipeline (separate batch). Do not cold-send until the ablation + ForecastBench result are live.</div>
</div>
<script>
const P=/*DATA*/;
const st={q:"",ring:new Set(),chan:new Set(),conf:new Set(),t1:false};
function link(r){let c=r.contact||"";if(r.channel==="email")return"mailto:"+c;
 if(r.channel==="x"){let h=c.replace(/^@/,"");return c.startsWith("http")?c:"https://x.com/"+h;}
 return c.startsWith("http")?c:"#";}
function linktext(r){return r.channel==="x"&&!r.contact.startsWith("http")?r.contact:(r.contact||"").replace(/^https?:\/\/(www\.)?/,"").slice(0,42);}
function chips(id,vals,bucket){const e=document.getElementById(id);vals.forEach(v=>{const c=document.createElement("span");c.className="chip";c.textContent=v;c.onclick=()=>{st[bucket].has(v)?st[bucket].delete(v):st[bucket].add(v);c.classList.toggle("on");render();};e.appendChild(c);});}
function ok(r){if(st.t1&&!r.tier1)return false;
 if(st.ring.size&&!st.ring.has(r.ring))return false;
 if(st.chan.size&&!st.chan.has(r.channel))return false;
 if(st.conf.size&&!st.conf.has(r.confidence))return false;
 if(st.q){const s=(r.name+" "+(r.role||"")+" "+(r.profile||"")+" "+(r.segment||"")).toLowerCase();if(!s.includes(st.q))return false;}
 return true;}
function esc(t){return(t||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function render(){const tb=document.getElementById("tb");const L=P.filter(ok);
 document.getElementById("count").textContent=L.length+" of "+P.length+" people";
 tb.innerHTML=L.slice(0,5000).map(r=>`<tr>
 <td class="nm">${r.tier1?'<span class="star">★</span> ':''}${esc(r.name)}</td>
 <td class="rl">${esc(r.role||r.profile||"")}</td>
 <td><span class="bdg ring-${r.ring}">${esc(r.ring)}</span></td>
 <td>${esc(r.segment||"")}</td>
 <td>${esc(r.channel||"")}</td>
 <td class="cf-${r.confidence}">${esc(r.confidence||"")}</td>
 <td>${r.has_message?'<span class="msgflag">msg</span> ':''}<a href="${link(r)}" target="_blank" rel="noopener">${esc(linktext(r))}</a></td>
 </tr>`).join("");}
function stats(){const e=document.getElementById("stats");const c=k=>P.filter(x=>x.ring===k).length;
 e.innerHTML=`<div><b>${P.length}</b>total</div><div><b>${c("advisor")}</b>advisors</div><div><b>${c("client")+c("client-vc")}</b>clients</div><div><b>${c("angel")}</b>angels</div><div><b>${c("amplifier")}</b>amplifiers</div><div><b>${P.filter(x=>x.tier1).length}</b>★ round-1</div>`;}
chips("ringChips",["advisor","client","client-vc","angel","amplifier"],"ring");
chips("chanChips",["email","linkedin","x","substack","web","orcid","openalex"],"chan");
chips("confChips",["high","med","low"],"conf");
document.getElementById("t1").onclick=function(){st.t1=!st.t1;this.classList.toggle("on");render();};
document.getElementById("q").addEventListener("input",e=>{st.q=e.target.value.toLowerCase();render();});
stats();render();
</script></body></html>"""

if __name__=="__main__":
    main()

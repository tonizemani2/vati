#!/usr/bin/env python3
"""Deterministic keyless-Exa people harvester (no LLM tokens).

Runs a wide query matrix through keyless Exa, keeps only person-profile results
(LinkedIn /in/, X/Twitter handles, Substack), extracts name + role + channel,
dedupes, and writes research/targets/harvest_web.jsonl.
"""
import asyncio
import json
import re
import time
from pathlib import Path

import httpx

from engine.adapters._vendor.exa_search import ExaClient, DDGClient

OUT = Path(__file__).parent / "harvest_web.jsonl"
RESULTS_PER_QUERY = 18

QUANT_FIRMS = ["Two Sigma", "DE Shaw", "Citadel", "Millennium", "Point72", "AQR",
    "Bridgewater", "Marshall Wace", "Man Group AHL", "Renaissance Technologies",
    "Balyasny", "WorldQuant", "Squarepoint", "Qube Research", "PDT Partners", "Voleon",
    "Schonfeld", "ExodusPoint", "Verition", "Capula", "BlueCrest", "GSA Capital",
    "Winton", "Systematica", "Aspect Capital", "QRT", "Cinctive", "Cubist"]
PROP_FIRMS = ["DRW", "Jane Street", "Hudson River Trading", "Citadel Securities",
    "Susquehanna SIG", "Optiver", "Jump Trading", "Tower Research", "IMC Trading",
    "Akuna Capital", "Five Rings", "XTX Markets", "Flow Traders", "Headlands Technologies",
    "Maven Securities", "Mako Trading", "Da Vinci Derivatives", "GTS", "Virtu Financial",
    "Old Mission", "Belvedere Trading", "TransMarket Group"]
MACRO_FUNDS = ["Brevan Howard", "Rokos Capital", "Caxton Associates", "Element Capital",
    "Tudor Investment", "Moore Capital", "Balyasny macro", "Millennium macro",
    "Bridgewater macro", "Elliott Management macro", "Dymon Asia", "BlueBay Asset Management",
    "PIMCO macro", "GIC macro strategy", "CPP Investments global macro"]
ASSET_MANAGERS = ["BlackRock systematic active equity", "State Street Global Advisors research",
    "Vanguard Investment Strategy Group", "Invesco research", "Franklin Templeton Institute",
    "Wellington Management research", "Fidelity macro research", "J.P. Morgan Asset Management research",
    "Morgan Stanley Investment Management research", "Goldman Sachs Asset Management research"]
FAMILY_OFFICE = ["family office chief investment officer", "multi family office head of research",
    "family office investment strategist", "family office macro strategist",
    "endowment chief investment officer", "foundation investment officer",
    "sovereign wealth fund strategy research"]
REINSURANCE_RISK = ["Swiss Re emerging risk", "Munich Re risk research", "SCOR strategic risk",
    "Aon geopolitical risk", "Marsh McLennan strategic risk", "Willis Towers Watson risk research",
    "Lloyds emerging risks", "AXA XL risk research", "Allianz risk barometer"]
CORP_FORESIGHT = ["head of corporate foresight", "chief strategy officer scenario planning",
    "strategic foresight director", "head of futures research corporation",
    "corporate strategy emerging trends", "scenario planning lead",
    "Shell scenarios team", "Microsoft future of work research", "Google strategy foresight",
    "Salesforce futures research", "Deloitte Center for the Edge", "McKinsey Global Institute director",
    "BCG Henderson Institute fellow", "Bain Futures", "PwC strategy foresight"]
VC_FUNDS = ["a16z partner", "Lux Capital partner", "Founders Fund principal", "Sequoia AI partner",
    "Index Ventures AI partner", "Accel AI partner", "General Catalyst AI partner",
    "Bessemer AI partner", "Greylock AI partner", "Radical Ventures partner",
    "Air Street Capital partner", "Conviction AI partner", "Amplify Partners AI investor",
    "NFX AI partner", "Point Nine AI partner", "Seedcamp AI partner", "LocalGlobe AI partner",
    "Episode 1 Ventures partner", "firstminute capital AI partner", "Hoxton Ventures AI partner"]

def build_matrix():
    m = []  # (ring, segment, vein, query)
    for f in QUANT_FIRMS:
        m += [("client","quant-fund","quant-fund",f"{f} head of research LinkedIn"),
              ("client","quant-fund","quant-fund",f"{f} quantitative researcher LinkedIn"),
              ("client","quant-fund","quant-fund",f"{f} portfolio manager LinkedIn"),
              ("client","quant-fund","quant-fund",f"{f} investment strategist LinkedIn")]
    for f in PROP_FIRMS:
        m += [("client","prop-trading","prop-trading",f"{f} head of research LinkedIn"),
              ("client","prop-trading","prop-trading",f"{f} quantitative trader LinkedIn"),
              ("client","prop-trading","prop-trading",f"{f} strategy research LinkedIn")]
    m += [("client","macro-familyoffice","macro-familyoffice",f"{q} LinkedIn") for q in MACRO_FUNDS]
    m += [("client","asset-manager","asset-manager",f"{q} LinkedIn") for q in ASSET_MANAGERS]
    m += [("client","macro-familyoffice","macro-familyoffice",f"{q} LinkedIn") for q in FAMILY_OFFICE]
    m += [("client","risk-reinsurance","risk-reinsurance",f"{q} LinkedIn") for q in REINSURANCE_RISK]
    m += [("client","corp-foresight","corp-foresight",f"{q} LinkedIn") for q in CORP_FORESIGHT]
    m += [("client-vc","vc-thesis","vc-thesis",f"{q} LinkedIn") for q in VC_FUNDS]
    aif = ["Mantic forecasting startup investor","Episode 1 Ventures partner LinkedIn",
        "prediction market angel investor LinkedIn","Metaculus investor",
        "Polymarket investor angel","Kalshi investor angel","5cc Capital prediction market fund",
        "FutureSearch AI forecasting investor","forecasting startup seed investor LinkedIn",
        "Manifold Markets investor", "forecasting research investor", "AI forecasting startup angel"]
    m += [("angel","ai-forecasting-investor","ai-forecasting-investor",q) for q in aif]
    qfa = ["ex hedge fund founder angel investor LinkedIn","quant trader angel investor LinkedIn",
        "fintech founder angel investor LinkedIn","ex Jane Street angel investor LinkedIn",
        "ex Citadel founder investor LinkedIn","ex Two Sigma angel investor LinkedIn",
        "trading firm founder investor startups LinkedIn","former portfolio manager angel investor LinkedIn",
        "systematic trading angel investor LinkedIn","market data startup angel investor LinkedIn"]
    m += [("angel","quant-fintech-angel","quant-fintech-angel",q) for q in qfa]
    aia = ["AI angel investor LinkedIn","ex OpenAI angel investor","ex DeepMind angel investor",
        "applied AI seed investor LinkedIn","Air Street Capital partner","Conviction AI partner",
        "Amplify Partners AI investor LinkedIn","AI researcher turned investor LinkedIn",
        "frontier AI angel investor", "AI evals investor", "AI infrastructure angel investor"]
    m += [("angel","applied-ai-angel","applied-ai-angel",q) for q in aia]
    amp = ["AI newsletter Substack author","quant finance Substack writer","forecasting Substack writer",
        "prediction markets newsletter author","AI podcast host","systematic investing podcast host",
        "fintech newsletter writer Substack","AI safety writer Substack","markets commentary Substack",
        "macro newsletter Substack author", "hedge fund podcast host", "forecasting podcast host",
        "LessWrong forecasting writer", "ACX forecasting writer", "AI markets newsletter"]
    m += [("amplifier","media-voice","media-voice",q) for q in amp]
    comm = ["Metaculus top forecaster","Samotsvety forecaster","Manifold Markets top forecaster",
        "superforecaster Good Judgment Open","Metaculus AI benchmark bot builder",
        "Astral Codex Ten prediction contest","RAND Forecasting Initiative top forecaster",
        "INFER forecasting tournament top forecaster","forecasting researcher Effective Altruism",
        "prediction market researcher", "forecasting tournament researcher", "calibration researcher"]
    m += [("advisor","forecasting-community","forecasting-community",q) for q in comm]
    return m

JUNK = re.compile(r"\b(jobs?|salary|salaries|careers?|hiring|list of|top \d+|best |reviews?|"
    r"glassdoor|indeed|wikipedia|ranking|vs\.?|how to|guide|companies|template)\b", re.I)
COMPANY_TOKENS = re.compile(r"\b(Capital|Partners|Ventures|LLC|Inc|Group|Management|Fund|"
    r"Securities|Trading|Technologies|Holdings|LinkedIn|Substack)\b")

def clean_name(title, domain):
    t = title.strip()
    if "linkedin" in domain:
        t = re.split(r"\s[-–|]\s", t)[0]
        t = re.sub(r"\s+on LinkedIn.*$", "", t, flags=re.I)
    elif "x.com" in domain or "twitter" in domain:
        t = re.split(r"\s*\(@", t)[0]
        t = re.split(r"\s+[/|]\s+", t)[0]
        t = re.sub(r"\s+on (X|Twitter).*$", "", t, flags=re.I)
    else:
        t = re.split(r"\s[-–|]\s", t)[0]
    return t.strip().strip("·-–|").strip()

def role_from_title(title, domain):
    if "linkedin" in domain:
        parts = re.split(r"\s[-–|]\s", title)
        if len(parts) > 1:
            return " - ".join(p.strip() for p in parts[1:] if "linkedin" not in p.lower())[:120]
    parts = re.split(r"\s[-–|]\s", title)
    if len(parts) > 1:
        return " - ".join(p.strip() for p in parts[1:])[:120]
    return ""

def is_profile(url):
    u = url.lower()
    if "linkedin.com/in/" in u: return "linkedin"
    if re.search(r"(x\.com|twitter\.com)/[a-z0-9_]{2,15}/?$", u): return "x"
    if "substack.com" in u and "/p/" not in u: return "substack"
    return ""

def valid_name(n):
    if not n or len(n) < 4: return False
    toks = n.split()
    if not (2 <= len(toks) <= 4): return False
    if any(c.isdigit() for c in n): return False
    if JUNK.search(n): return False
    if COMPANY_TOKENS.search(n) and len(toks) <= 3: return False
    if not re.match(r"^[A-Za-zÀ-ÿ.'\- ]+$", n): return False
    return True

async def main():
    matrix = build_matrix()
    print(f"{len(matrix)} queries")
    seen_name, seen_url = set(), set()
    rows = []
    ex = ExaClient()
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as c:
        for i,(ring,seg,vein,q) in enumerate(matrix):
            try:
                res = await ex.search(q, num_results=RESULTS_PER_QUERY, client=c, text_chars=260)
                if not res:
                    res = await DDGClient().search(q, num_results=RESULTS_PER_QUERY, client=c)
            except Exception:
                res = []
            for r in res:
                kind = is_profile(r.url)
                if not kind: continue
                if r.url.lower() in seen_url: continue
                name = clean_name(r.title, kind)
                if not valid_name(name): continue
                key = name.lower()
                if key in seen_name: continue
                seen_name.add(key); seen_url.add(r.url.lower())
                rows.append({"name":name,
                    "role":role_from_title(r.title, kind),
                    "segment":seg,"vein":vein,"ring":ring,
                    "profile":(r.snippet or "")[:160],
                    "channel":kind,"contact":r.url,"source":r.url,
                    "query":q,"title":r.title,
                    "confidence":"med" if kind=="linkedin" else "low"})
            if i % 20 == 0:
                print(f"  {i}/{len(matrix)}  rows={len(rows)}")
            time.sleep(0.25)
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(rows)} people -> {OUT}")

if __name__ == "__main__":
    asyncio.run(main())

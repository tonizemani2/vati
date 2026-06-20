"""Emergent-constraint scan — the data→predict→CAPTURE loop (DeepSeek-driven).

WHAT (2026-06-19). Closes the loop from the new per-concept emergence signal (concept_emergence) to
an ACTIONABLE, value-capture-ready call. For each concept whose share of world literature is
accelerating NOW (the detector fired + sustained), it:

  1. GROUNDS  — pulls the measured context: the emergence verdict (where it's MOVING), the dependency
     edges both ways (who it leans on / who leans on it, each tagged with ITS own acceleration), the
     paper→patent reliance (commercialization intensity), and the priced-in market anchor.
  2. JUDGES   — DeepSeek reasons over that grounded pack to find the BINDING INELASTIC INPUT one layer
     down (the needle, never the theme) and whether it is PRE-CONSENSUS (an accelerating concept whose
     less-famous upstream input is also accelerating but unpriced = the edge). Commits to P + horizon,
     or kills it as already-priced / too-broad. No free-association — it must cite the grounded signal.
  3. CAPTURES — for survivors, a keyless web search grounds a NAMED real-world target, then DeepSeek
     names the factory/company + the role/person to contact + the exact ask + HOW the rent is captured
     (advisory / offtake / position / intel / brokered intro). "Find the factory, find the person."

This is recall-at-the-detector → precision-at-the-gate → act. The emergence signal fires wide; the
LLM judge + priced-in anchor converge; capture turns a surviving call into a move you can make.

COST: DeepSeek-V4 (keyed, cheap — ~sub-cent per call); keyless web search ($0). The real batch spend is
logged as one approved cost_ledger row (the per-call gate runs at $0 so it never blocks). NO Opus.

USAGE
  uv run python -m engine.emergent_scan --limit 12              # scan + judge + capture, print report
  uv run python -m engine.emergent_scan --limit 20 --no-capture # judge only (cheaper)
  uv run python -m engine.emergent_scan --limit 5 --json        # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from engine import db, market, signals
from engine.adapters import search
from engine.adapters.llm import complete
from engine.feeds.concept_emergence import top_emergent
from engine.schemas import CostLedgerEntry, _now

PROVIDER = "deepseek"

# Where the last scan's PURSUE calls are parked so the `emergent-card` CLI can graduate a reviewed one
# into an immutable forecast card (fork C — "make it land"). Never auto-promoted (rule 7): a human picks.
LATEST = Path(__file__).resolve().parents[1] / "data" / "emergent_scan_latest.json"

# Fork B — bias the pool HARD to PHYSICAL/COMMERCIALIZING needles, where "find the factory, find the
# person" is a real move. A pure research-data / methodological concept (a treebank, a benchmark corpus,
# a proof technique) can accelerate hard but has no factory and no operator to call — the capture step
# comes up empty on it. A physical input (a material, reagent, fabrication step, organism, device) is
# where rent accrues to a constrained, ownable supply chain. _NON_PHYSICAL is dropped under --physical;
# _PHYSICAL gets a score boost so materials/biotech/chemistry needles rise above the abstract ones.
_NON_PHYSICAL = re.compile(
    r"\b(treebank|corp(us|ora)|benchmark|datasets?|ontolog|taxonom|algorithm|heuristic|theorem|lemma|"
    r"conjecture|complexity|topolog|sentiment|semantic|syntax|grammar|linguistic|natural language|"
    r"machine translation|information retrieval|social media|survey|questionnaire|pedagog|curriculum|"
    r"psychometr|qualitative|ethnograph|literary|narrative|historiograph|jurisprudence|econometr)\b", re.I)
_PHYSICAL = re.compile(
    r"\b(materi|alloy|ceramic|polymer|composite|cataly|reagent|solvent|membrane|electrode|electrolyt|"
    r"semiconductor|lithograph|wafer|nanoparticle|nanotube|graphene|niobate|perovskite|crystal|isotope|"
    r"rare earth|lithium|cobalt|nickel|gallium|niobium|tantalum|magnet|photonic|laser|fabricat|"
    r"deposition|etch|sinter|peptide|antibod|antigen|epitope|plasmid|enzyme|protein|genome|reactor|"
    r"turbine|battery|fuel cell|electroly|propellant|actuator|sensor|coating|adhesive|fib(er|re)|"
    r"textile|pharmaceutic|vaccine|chromatograph|spectroscop|fermentation|bioreactor)\b", re.I)
# AI/ML-core themes accelerate hardest of all but have no single factory to find — the rent is diffuse
# (chips, energy, data, talent). Damp them so physical/commercializing needles outrank them in the pool;
# they are NOT dropped, because the judge can still decompose one to a physical sub-layer needle.
_AI_CORE = re.compile(
    r"\b(discriminat|reinforcement learning|adversarial|generative|neural network|deep learning|"
    r"transformer|attention mechanism|embedding|gradient|backpropagat|convolutional|large language|"
    r"diffusion model|representation learning|self-supervised|feature extraction|classifier|"
    r"artificial neural)\b", re.I)
# The structural JUDGMENT (decompose to the sub-layer needle + pre-consensus) is the hard reasoning
# step — deepseek-reasoner does it well but spends its token budget on chain-of-thought first, so it
# needs generous max_tokens. Capture is lighter extraction → the cheaper v4-pro. (flash was too weak:
# ~40% JSON failures + blanket-rejected without decomposing.)
JUDGE_MODEL = "deepseek-reasoner"
JUDGE_MAX_TOKENS = 4000
CAPTURE_MODEL = "deepseek-v4-pro"
EST_CENTS_PER_CALL = 2  # honest estimate for a reasoner judge call, for the batch ledger row

JUDGE_SYS = (
    "You are a pre-consensus structural forecaster. Your edge: rent accrues to the BINDING CONSTRAINT, "
    "and you spot it move before it is priced. You are given a research concept whose share of world "
    "literature is ACCELERATING (a measured, dated signal), plus its citation-dependency graph (what it "
    "leans on / who leans on it, each tagged with its OWN acceleration) and commercialization intensity. "
    "Reason ALONG that measured data — never free-associate.\n\n"
    "Find the needle: the INELASTIC INPUT one layer DOWN that this acceleration will bottleneck on — a "
    "specific material, tool, process, or capability, NEVER the broad theme. The pre-consensus edge is an "
    "accelerating concept whose less-famous UPSTREAM input is also rising but the crowd has not priced. "
    "Commit to a side. If the concept is already consensus and the constraint is already priced, say so "
    "and KILL it — a correct-but-priced call has zero edge.\n\n"
    "Return ONLY compact JSON: {\"pre_consensus\": bool, \"verdict\": \"PURSUE\"|\"PASS\", "
    "\"inelastic_input\": str, \"thesis\": str (one sentence: over <horizon> [sector] reorganizes so that "
    "[measurable structural claim] because [binding constraint]), \"p\": float 0-1, \"horizon_years\": int, "
    "\"dated_metric\": str (the falsifiable thing to watch), \"why_unpriced\": str, \"kill\": str "
    "(REQUIRED, never empty — the specific observation by which this thesis is WRONG)}. "
    "PASS when it is a theme not a needle, or already priced. "
    "Output ONLY the JSON object — no reasoning, no preamble, no markdown."
)

CAPTURE_SYS = (
    "You are a value-capture operator. Given a surviving pre-consensus thesis and real web-search results "
    "naming actual companies/people in that supply layer, produce a concrete plan to CAPTURE the rent. "
    "Ground every name in the provided search results — do NOT invent a company or person; if the search "
    "is thin, say what to search next and name the ROLE to find. Return ONLY compact JSON: "
    "{\"target_org\": str, \"why_them\": str, \"person_or_role\": str, \"reach_path\": str, "
    "\"the_ask\": str, \"capture_mechanism\": str (advisory retainer | paid intel | offtake | position | "
    "equity | brokered-intro fee | data licence), \"who_pays\": str, \"first_move_this_week\": str}."
)


def _extract_json(raw: str) -> dict | None:
    """Pull the JSON object out of a model response (handles prose/CoT before it). Last object wins."""
    # try the whole greedy span first (clean json_object responses), then fall back to the LAST {...}
    for span in (re.findall(r"\{.*\}", raw, re.DOTALL) or [])[::-1]:
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue
    # progressive: scan from each '{' for a parseable object (reasoner sometimes trails a fragment)
    for i, ch in enumerate(raw):
        if ch == "{":
            for j in range(len(raw), i, -1):
                try:
                    return json.loads(raw[i:j])
                except json.JSONDecodeError:
                    continue
    return None


def _deepseek_json(conn, prompt: str, system: str, *, model: str = CAPTURE_MODEL,
                   max_tokens: int = 1300) -> dict | None:
    """One DeepSeek call → parsed JSON (robust to CoT/prose). $0 gate; batch spend logged once.

    Retries once with a blunt 'JSON only' nudge — a model occasionally spends its budget reasoning."""
    last = {"_error": "unknown"}
    for attempt in range(2):
        p = prompt if attempt == 0 else prompt + "\n\nReturn ONLY the JSON object, nothing else."
        try:
            raw = complete(conn, p, provider=PROVIDER, system=system, model=model,
                           max_tokens=max_tokens, est_cost_cents=0,
                           extra_body={"response_format": {"type": "json_object"}})
        except Exception as exc:  # noqa: BLE001 — network/key/gate: report, never crash the scan
            return {"_error": f"{type(exc).__name__}: {exc}"}
        parsed = _extract_json(raw)
        if parsed is not None:
            return parsed
        last = {"_error": "no json in response", "_raw": raw[:200]}
    return last


def _candidates(conn, *, pool: int = 600, min_patents: int = 200, min_inbound: int = 1,
                physical: bool = True) -> list[dict]:
    """Rank candidates toward COMMERCIALIZING, PHYSICAL industrial constraints, not the famous AI core.

    A pre-consensus call where "find the factory" is meaningful needs three things at once: the concept
    is accelerating (fired+sustained), it is DEPENDED-UPON (inbound edges = a blast radius), and it is
    already COMMERCIALIZING (paper→patent reliance = there is a real supply chain to capture). Score
    rewards acceleration × commercialization, penalizes giant generic fields (priced/known), and — fork
    B — biases HARD toward physical needles: a _PHYSICAL match is boosted, and with physical=True any
    pure research-data/methodological concept (_NON_PHYSICAL: treebank, benchmark, proof technique) is
    dropped outright because it has no factory and no operator to capture. The LLM gate still converges."""
    pat = signals._concept_patents()
    rows = conn.execute(
        "SELECT * FROM concept_emergence WHERE fired=1 AND sustained=1 AND dissolving=0 "
        "ORDER BY sustained_sigma DESC LIMIT ?", (pool,)).fetchall()
    scored = []
    for r in rows:
        em = dict(r)
        name = em["concept_name"]
        rel = pat.get(name.lower())
        if not rel or rel["n_patents"] < min_patents:
            continue
        is_abstract = bool(_NON_PHYSICAL.search(name))
        if physical and is_abstract:
            continue  # no factory to find — drop it from the capture-oriented pool
        inbound = conn.execute(
            "SELECT count(*) FROM graph_edges x JOIN graph_nodes g ON x.dst=g.id "
            "WHERE x.chain='concept_flow' AND lower(g.name)=lower(?)", (name,)).fetchone()[0]
        if inbound < min_inbound:
            continue
        np = rel["n_patents"]
        # physical needles boosted 1.6×; AI/ML-core themes (no single factory) damped 0.5×; an abstract
        # research-data one that survived (physical=False) damped 0.4×. acceleration enters as sqrt so a
        # 33σ AI theme can't bury a 6σ commercializing material — commercialization+physicality lead.
        phys_mult = (1.6 if _PHYSICAL.search(name)
                     else 0.5 if _AI_CORE.search(name)
                     else 0.4 if is_abstract else 1.0)
        score = em["sustained_sigma"] ** 0.5 * (1 + np**0.5 / 50.0) * phys_mult / (1 + em["total_works"] / 50000.0)
        em.update({"inbound_load": inbound, "n_patents": np, "_score": score,
                   "physical": bool(_PHYSICAL.search(name))})
        scored.append(em)
    scored.sort(key=lambda x: -x["_score"])
    return scored


def _ground_context(conn, concept_name: str, em: dict) -> str:
    """Compact measured pack for one concept: emergence + dependency edges + patents + priced-in."""
    pack = signals.evidence_pack(concept_name)
    def _edge(e):
        return f"{e['name']} ({e['weight']:.0%}){e.get('emerge','')}{e.get('shift','')}"
    dep = "\n".join(
        f"  - [{d['concept']}] draws_on: "
        + (", ".join(_edge(e) for e in d['draws_on']) or "—")
        + " | drawn_on_by: "
        + (", ".join(_edge(e) for e in d['drawn_on_by']) or "—")
        + (f" | {d['patent_reliance']['n_patents']:,} patents cite it"
           if d.get('patent_reliance') else "")
        for d in pack.get("dependency", [])[:3]
    ) or "  (no dependency edges in the graph for this concept)"
    try:
        anchor = market.market_anchor(concept_name)
        priced = anchor.get("verdict", "UNPRICED-UNSEEN")
    except Exception:  # noqa: BLE001
        priced = "UNPRICED-UNSEEN (anchor unavailable)"
    return (
        f"CONCEPT: {concept_name}\n"
        f"EMERGENCE: share-acceleration {em['sustained_sigma']:.0f}σ̄ (max {em['surprise_sigma']:.0f}σ), "
        f"{em['last_works']} works in {em['last_year']}, sparkline {em['spark']} "
        f"(rising = reorientation of attention, leak-free, dropped provisional trailing year)\n"
        f"DEPENDENCY GRAPH (↑Nσ = that neighbor concept is ALSO accelerating; ↓diss = its rent is "
        f"leaving; ↗Nσ = that RELIANCE EDGE is TIGHTENING = the binding constraint is migrating onto "
        f"that input — the strongest pre-consensus tell; ↘ = the link is decaying):\n{dep}\n"
        f"PRICED-IN ANCHOR: {priced}  (UNPRICED-UNSEEN is NOT a green light — judge pre-consensus on structure)"
    )


def _recurring_orgs(hits: list) -> list[str]:
    """Proper-noun-ish phrases that recur across ≥2 hits = the real operators (not one blog's invention)."""
    counts: Counter = Counter()
    stop = {"The", "This", "These", "Market", "Report", "Global", "Research", "News", "Inc", "Ltd"}
    for h in hits:
        for m in re.findall(r"\b([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,2})\b",
                            f"{h.title}. {h.snippet}"):
            if m.split()[0] not in stop and len(m) > 3:
                counts[m] += 1
    return [t for t, c in counts.most_common(15) if c >= 2][:8]


def _capture(conn, thesis: dict, log=print) -> dict:
    """Ground a real named target via a MULTI-QUERY keyless search, then DeepSeek names factory/person/ask.

    Fork B — capture is the weakest link, so widen the evidence: four decorrelated queries (market
    leaders / largest producer / supply-chain bottleneck / who-makes-it), deduped, plus the orgs that
    RECUR across hits handed to the model as the most-likely real operators. The anti-hallucination
    guard still blanks any org not present in the evidence."""
    needle = str(thesis.get("inelastic_input", "")).strip()
    queries = [
        f"{needle} leading manufacturers suppliers market share",
        f"largest producer of {needle} production capacity company",
        f"{needle} supply chain bottleneck shortage 2025",
        f"who makes {needle} factory industrial",
    ]
    try:
        res = search.search_multi(conn, queries, num_results=5)
        hits = [h for q in queries for h in res.get(q, [])]
    except Exception as exc:  # noqa: BLE001
        hits = []
        log(f"      (search failed: {type(exc).__name__})")
    seen: set[str] = set()
    hits = [h for h in hits if not (h.url in seen or seen.add(h.url))][:16]  # dedup by url, cap
    recurring = _recurring_orgs(hits)
    evidence = "\n".join(f"  - {h.title} :: {h.snippet[:160]} ({h.url})" for h in hits) or "  (no search hits)"
    prompt = (
        f"THESIS: {thesis.get('thesis','')}\n"
        f"INELASTIC INPUT (the needle): {needle}\n"
        f"ORGS THAT RECUR ACROSS HITS (most likely the real operators — prefer these): "
        f"{', '.join(recurring) or '(none recurred — be conservative)'}\n"
        f"WEB SEARCH RESULTS (real, ground every name in these):\n{evidence}\n\n"
        "Name the factory and the person, and how we capture the rent."
    )
    # v4-pro reasons in prose before the JSON (like the judge) — give it headroom or it truncates mid-CoT
    # and returns no parseable object (the all-6-empty failure). 2500 clears the chain-of-thought.
    out = _deepseek_json(conn, prompt, CAPTURE_SYS, max_tokens=2500) or {}
    out["_search_hits"] = [{"title": h.title, "url": h.url} for h in hits[:5]]
    out["_recurring_orgs"] = recurring
    # anti-hallucination: a named target_org MUST appear in the real search evidence, else it is invented
    # (the "Upwind Technology Inc" failure). Ungrounded → blank the org, keep the role + a search-next note.
    blob = " ".join(f"{h.title} {h.snippet}" for h in hits).lower()
    org = str(out.get("target_org", "")).strip()
    org_toks = [t for t in re.split(r"[^a-z0-9]+", org.lower()) if len(t) >= 4]
    grounded = bool(org_toks) and any(t in blob for t in org_toks)
    if not grounded:
        out["target_org"] = "(no named org grounded in search — run the search-next below before naming one)"
        out["_ungrounded"] = True
        if not out.get("first_move_this_week"):
            out["first_move_this_week"] = (f"search '{queries[0]}' + a trade directory (e.g. ICIS, "
                                           "Panjiva); name the real operator before any outreach")
    return out


def scan(conn, *, limit: int = 12, do_capture: bool = True, min_inbound: int = 1,
         physical: bool = True, log=print) -> list[dict]:
    """The full loop: top emergent concepts → judge pre-consensus → capture the survivors."""
    cands = _candidates(conn, min_inbound=min_inbound, physical=physical)[: max(limit * 6, 24)]
    log(f"scanning {len(cands)} accelerating+commercializing concepts "
        f"({'physical-only' if physical else 'all'}; DeepSeek judge; "
        f"capture={'on' if do_capture else 'off'}) ...")
    calls = 0
    results: list[dict] = []
    for em in cands:
        name = em["concept_name"]
        inbound = em["inbound_load"]
        ctx = _ground_context(conn, name, em)
        verdict = _deepseek_json(conn, ctx + "\n\nJudge this concept.", JUDGE_SYS,
                                 model=JUDGE_MODEL, max_tokens=JUDGE_MAX_TOKENS)
        calls += 1
        if not verdict or verdict.get("_error"):
            log(f"  ? {name[:34]:34s} — judge error: {verdict.get('_error') if verdict else 'none'}")
            continue
        verdict.update({"concept": name, "inbound_load": inbound,
                        "sustained_sigma": em["sustained_sigma"], "spark": em["spark"]})
        tag = "PURSUE" if verdict.get("pre_consensus") and verdict.get("verdict") == "PURSUE" else "pass"
        log(f"  {'→' if tag=='PURSUE' else ' '} {name[:34]:34s} {tag:7s} "
            f"P={verdict.get('p','?')} needle={str(verdict.get('inelastic_input',''))[:40]}")
        if do_capture and tag == "PURSUE":
            verdict["capture"] = _capture(conn, verdict, log=log)
            calls += 1
        results.append(verdict)
        if len([x for x in results if x.get("verdict") == "PURSUE"]) >= limit:
            break
    # one honest approved ledger row for the whole DeepSeek batch (per-call gate ran at $0)
    cents = calls * EST_CENTS_PER_CALL
    e = CostLedgerEntry(action="emergent_scan:deepseek", provider="deepseek", units=calls,
                        est_cost_cents=cents, actual_cost_cents=cents)
    conn.execute(
        "INSERT INTO cost_ledger (id,ts,action,provider,units,est_cost_cents,actual_cost_cents,"
        "approval_status) VALUES (?,?,?,?,?,?,?,?)",
        (e.id, e.ts.isoformat(), e.action, e.provider, e.units, cents, cents, "approved"))
    conn.commit()
    _persist(results)
    log(f"\n{calls} DeepSeek calls (~{cents}¢ logged); {sum(1 for x in results if x.get('verdict')=='PURSUE')} PURSUE")
    return results


def _persist(results: list[dict]) -> None:
    """Park the PURSUE calls so `emergent-card` can graduate a reviewed one into a tracked card (fork C)."""
    pursue = [r for r in results if r.get("verdict") == "PURSUE" and r.get("pre_consensus")]
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(
        {"computed_at": _now().isoformat(), "calls": pursue}, ensure_ascii=False, indent=2))


def load_latest() -> list[dict]:
    """The parked PURSUE calls from the most recent scan (for the emergent-card CLI)."""
    if not LATEST.exists():
        return []
    return json.loads(LATEST.read_text()).get("calls", [])


def build_card_fields(call: dict, *, resolution_date: date | None = None,
                      question: str | None = None) -> dict:
    """Turn one reviewed PURSUE call into create_card(**fields) — the fork-C bridge to a tracked card.

    Frames a falsifiable, point-in-time binary from the call's dated_metric (the operator may override
    --question), sets the resolution from horizon_years, and carries the kill-criterion + the structural
    rationale. create_card's altitude + seed-QC gates remain the safety net; nothing is auto-promoted."""
    horizon = int(call.get("horizon_years") or 3)
    res = resolution_date or (date.today().replace(year=date.today().year + horizon))
    metric = str(call.get("dated_metric") or "").strip().rstrip(".")
    q = question or f"By {res.isoformat()}, will it hold that {metric}?"
    kill = str(call.get("kill") or "").strip()
    sig = call.get("sustained_sigma")
    sig_s = f"{float(sig):.1f}" if isinstance(sig, (int, float)) else str(sig or "?")
    thesis = str(call.get("thesis", "")).strip().rstrip(".")
    unpriced = str(call.get("why_unpriced", "")).strip().rstrip(".")
    rationale = (
        f"Emergent-constraint scan (leak-free share-acceleration signal). Concept '{call.get('concept')}' "
        f"share-acceleration {sig_s}σ̄, inbound load {call.get('inbound_load','?')}. "
        f"Needle (inelastic input): {call.get('inelastic_input','')}. Thesis: {thesis}. "
        f"Why unpriced: {unpriced}.")
    return {
        "question": q,
        "probability": float(call.get("p") or 0.5),
        "resolution_date": res,
        "kill_criteria": [kill] if kill else ["(set a falsifiable kill-criterion before tracking)"],
        "rationale": rationale,
    }


def format_report(results: list[dict]) -> str:
    pursue = [r for r in results if r.get("verdict") == "PURSUE" and r.get("pre_consensus")]
    out = ["=" * 78, f"EMERGENT-CONSTRAINT SCAN — {len(pursue)} pre-consensus calls worth acting on", "=" * 78]
    for r in sorted(pursue, key=lambda x: -float(x.get("p", 0) or 0)):
        out += [
            "",
            f"▶ {r['concept']}  (accel {r['sustained_sigma']:.0f}σ̄, inbound load {r['inbound_load']})  {r['spark']}",
            f"  NEEDLE (inelastic input): {r.get('inelastic_input','')}",
            f"  THESIS: {r.get('thesis','')}",
            f"  P={r.get('p','?')}  horizon={r.get('horizon_years','?')}y  watch: {r.get('dated_metric','')}",
            f"  why unpriced: {r.get('why_unpriced','')}",
            f"  kill: {r.get('kill','')}",
        ]
        cap = r.get("capture")
        if cap and not cap.get("_error"):
            out += [
                f"  ── CAPTURE ──",
                f"    target: {cap.get('target_org','?')} — {cap.get('why_them','')}",
                f"    person/role: {cap.get('person_or_role','?')}  | reach: {cap.get('reach_path','')}",
                f"    ask: {cap.get('the_ask','')}",
                f"    mechanism: {cap.get('capture_mechanism','?')}  | who pays: {cap.get('who_pays','')}",
                f"    THIS WEEK: {cap.get('first_move_this_week','')}",
            ]
    out += ["", "=" * 78,
            "Recall at the detector, precision at the gate: these PASSED the priced-in + needle gate.",
            "Not auto-promoted to cards (rule 7) — Ruben decides which become tracked forward calls."]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="DeepSeek emergent-constraint detect→gate→capture scan.")
    ap.add_argument("--limit", type=int, default=12, help="target number of PURSUE calls")
    ap.add_argument("--no-capture", action="store_true", help="judge only, skip the capture step")
    ap.add_argument("--all", action="store_true",
                    help="include abstract research-data concepts too (default: physical needles only)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv[1:])
    conn = db.connect()
    results = scan(conn, limit=args.limit, do_capture=not args.no_capture, physical=not args.all)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, default=str))
    else:
        print("\n" + format_report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

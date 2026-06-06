"""Component 17b — the narrative-saturation meter (the MEASURED pre-consensus leg).

The novelty-detection fix. discover.pre_consensus() calls a thesis EARLY when the LAGGING channels we
INDEX (OpenAlex, SEC, patents, Federal Register, Wikipedia) are still flat. But most real-world
coverage lives OUTSIDE those — trade press, FERC orders, national-lab reports, finance Substacks — so
a heavily-covered theme (grain-oriented electrical steel, the interconnection queue) read as "least-
seen" only because the engine never looked. This module LOOKS: a keyless web search ($0) over public
coverage, scored by a TRANSPARENT formula. High saturation HARD-DEMOTES an EARLY candidate to PRICED
(Ruben's locked decision: if it's already in the trade press, it is not pre-consensus).

Doctrine fit: the keyless search is the SCALE part (collect the coverage); the saturation SCORE is an
explicit in-engine formula, NOT an LLM opinion — judgment stays in-session (CLAUDE.md). Two honesty
rails (mirroring adapters/answer.py): the hit URLs are always kept and cited; a search that returns
nothing degrades to a flagged UNMEASURED read (absence of hits ≠ obscurity) — it never fabricates
novelty. $0, cost-gated inside adapters.search, 0 new deps.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from urllib.parse import urlparse

from engine.adapters import search
from engine.schemas import SaturationScore

# Substrings that mean "the crowd / market / regulator already covers this" — the LAG definition made
# concrete (this is what discover.py's narrow LAG provider-set was missing). Three bands: mainstream +
# finance press (the market is watching), trade/industry press (the sector discusses it), and
# regulatory / national-lab / official (an institution has named it). Documented, transparent, tunable.
AUTHORITY_MARKERS = (
    # mainstream + finance
    "bloomberg.", "reuters.", "wsj.", "ft.com", "nytimes.", "cnbc.", "forbes.", "economist.",
    "marketwatch.", "barrons.", "finance.yahoo", "seekingalpha.", "businessinsider.",
    "apnews.", "theguardian.", "washingtonpost.", "axios.", "politico.", "npr.org",
    # energy / metals / industrials trade press
    "ieee.org", "spectrum.ieee", "pv-magazine", "powermag", "utilitydive", "greentechmedia",
    "spglobal", "woodmac", "mining.com", "oilprice", "tradingeconomics", "canarymedia",
    # pharma / biotech / health trade press
    "fiercepharma", "fiercebiotech", "statnews", "endpts", "biopharmadive", "biospace",
    "medscape", "drugs.com", "pharmavoice", "pharmtech",
    # consumer / enterprise tech trade press (NOT research journals — nature/science cover EVERY niche
    # topic and would mint false authority on genuinely obscure research, so they are deliberately out)
    "techcrunch", "arstechnica", "theverge", "wired.",
    # regulatory / national-lab / official
    ".gov", "ferc.", "nrel.", "lbl.gov", "lbnl", "iea.org", "eia.gov", "doe.gov", "sec.gov", "europa.eu",
)

# Official FORECASTERS + macro research houses — the channel that matters at structural/macro altitude
# (the reframe): if the IEA/IMF/a major bank already PROJECTS the reorganization, the structural claim
# is the consensus base case → priced, however "obscure" the micro-input. This is also the pass-1 miss
# fix — Spruce Pine read 'obscure' on the narrow channels while it was a macro-newsletter / book staple;
# these domains + the substack/newsletter markers catch the coverage the academic/SEC channels can't see.
FORECASTER_MARKERS = (
    "iea.org", "eia.gov", "imf.org", "oecd.org", "worldbank.org", "weforum.org", "bis.org",
    "federalreserve.gov", "ecb.europa.eu", "blackrock.com", "mckinsey.com", "goldmansachs.com",
    "jpmorgan.com", "morganstanley.com", "bcg.com", "bain.com", "rand.org", "brookings.edu",
    "spglobal", "woodmac", "rystadenergy", "gartner.com", "idc.com", "statista.com",
    "substack.com", "ourworldindata", "visualcapitalist",
)
AUTHORITY_MARKERS = AUTHORITY_MARKERS + tuple(
    m for m in FORECASTER_MARKERS if m not in AUTHORITY_MARKERS)

# Score parameters (a first, stated calibration — not vibes; tune against known cases). The backbone
# is the COUNT of distinct authoritative DOMAINS covering the topic — robust to query phrasing and to
# the fact that a capped search always returns ~N hits (so raw hit-count is NOT a saturation signal).
# saturation = W_AUTHORITY·min(1, auth_domains/AUTH_TARGET) + W_RECENCY·(recent share). Authority-
# DOMINANT on purpose: recency over noisy hits is weak, so it only modulates — it must not push a
# topic with ~1 authoritative outlet over the demote line (that was an early miscalibration).
W_AUTHORITY, W_RECENCY = 0.80, 0.20
AUTH_TARGET = 5              # this many distinct mainstream/trade/regulatory outlets ≈ saturated
DEMOTE_AT = 0.55             # saturation at/above this = priced/known (not pre-consensus)
RECENT_YEARS = 2             # a hit referencing this-year or last ~2 counts as live coverage
_YEAR = re.compile(r"\b(20[0-9]{2})\b")


def _domain(url: str) -> str:
    net = urlparse(url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def _tier(s: float, measured: bool) -> str:
    if not measured:
        return "unmeasured"
    if s >= 0.65:
        return "saturated"
    if s >= 0.50:
        return "mainstream"
    if s >= 0.30:
        return "emerging"
    return "obscure"


def score_topic(conn: sqlite3.Connection, topic: str, *, entity_id: str | None = None,
                num_results: int = 10, today: date | None = None, log=print) -> SaturationScore:
    """Measure how saturated `topic`'s public narrative is, persist it, and return the score.

    Transparent: saturation = W_AUTHORITY·(authoritative share) + W_COVERAGE·(volume/target)
    + W_RECENCY·(recent share), all read off real search hits. Honest rails: cite the hit URLs;
    a search that returns nothing → UNMEASURED (never assert obscurity from a failed lookup)."""
    today = today or date.today()
    # Union two query variants, deduped by URL — robust to phrasing (one query may miss the mainstream
    # coverage another surfaces). Both keyless, $0, each cost-gated inside adapters.search.
    queries = [topic, f"{topic} news report 2026"]
    seen, hits = set(), []
    for qy in queries:
        try:
            for h in search.search(conn, qy, num_results=num_results):
                if h.url and h.url not in seen:
                    seen.add(h.url)
                    hits.append(h)
        except Exception as e:                  # search down → UNMEASURED, not "obscure" (honesty rail)
            log(f"  saturation: a search failed ({str(e)[:50]}) — partial coverage, flagged")

    n = len(hits)
    if n == 0:
        score = SaturationScore(
            topic=topic, entity_id=entity_id, as_of=today, saturation=0.0, tier="unmeasured",
            n_hits=0, n_authoritative=0, n_recent=0, verdict="pre_consensus",
            rationale="search returned no hits — saturation UNMEASURED (absence of hits ≠ obscurity; "
                      "do not treat as pre-consensus evidence; widen the query / retry).",
            evidence_urls=[])
        _persist(conn, score)
        return score

    auth_domains: set[str] = set()
    n_recent = 0
    for h in hits:
        url = (h.url or "").lower()
        if any(m in url for m in AUTHORITY_MARKERS):
            auth_domains.add(_domain(url))
        years = [int(y) for y in _YEAR.findall(f"{h.title} {h.url} {h.snippet}")]
        if years and max(years) >= today.year - RECENT_YEARS:
            n_recent += 1

    n_auth = len(auth_domains)                  # distinct authoritative OUTLETS — the robust backbone
    authority = min(1.0, n_auth / AUTH_TARGET)
    recency = n_recent / n
    sat = round(W_AUTHORITY * authority + W_RECENCY * recency, 3)
    verdict = "priced/known" if sat >= DEMOTE_AT else "pre_consensus"
    tier = _tier(sat, measured=True)

    score = SaturationScore(
        topic=topic, entity_id=entity_id, as_of=today, saturation=sat, tier=tier,
        n_hits=n, n_authoritative=n_auth, n_recent=n_recent, verdict=verdict,
        rationale=(f"{n} hits · {n_auth} distinct mainstream/trade/regulatory outlets "
                   f"({', '.join(sorted(auth_domains)[:5]) or 'none'}) · {n_recent}/{n} reference the "
                   f"last {RECENT_YEARS}y (recency {recency:.0%}). saturation={sat:.2f} ({tier}) → "
                   f"{'NOT pre-consensus — the crowd/press is already here (hard-demote)' if verdict=='priced/known' else 'still pre-consensus on the measured coverage'}."),
        evidence_urls=[h.url for h in hits if h.url][:num_results])
    _persist(conn, score)
    log(f"  saturation[{topic[:48]}] = {sat:.2f} ({tier}) · {verdict} · "
        f"{n_auth}/{n} authoritative, {n_recent}/{n} recent")
    return score


def consensus_forecast(conn: sqlite3.Connection, claim: str, *, num_results: int = 10,
                       log=print) -> dict:
    """Is this structural claim ALREADY covered — by forecasters OR specialist/trade press?

    HONEST ASYMMETRY (the calibration fix, 2026-06-04, after a reviewer caught false 'pre-consensus'
    reads on SWU / GLP-1 fill-finish / gas takeaway): a keyless web search can RELIABLY find that a
    thesis IS covered (→ priced/covered), but it can NEVER certify pre-consensus — it is blind to
    paywalled sell-side notes + specialist B2B trade press, so 'found nothing' ≠ 'no one wrote it'.
    So this NEVER returns a green light. Verdicts: PRICED (≥2 forecaster outlets) · PARTLY (1) ·
    COVERED (broad trade/finance coverage, no forecaster-grade) · UNCONFIRMED (little surfaced — NOT
    pre-consensus, the in-session judgment + the scored record settle that) · UNMEASURED (search dead).
    """
    # Query 2 probes SPECIALIST coverage (analyst notes / thesis pieces), where a sophisticated thesis
    # actually lives — not just official projections (the reviewer's point: the SWU/gas calls were
    # saturated in sell-side notes a forecaster-domain headcount can't see). Neutral: no seeded names.
    queries = [f"{claim} forecast outlook projection", f"{claim} analyst note bottleneck thesis"]
    seen, hits = set(), []
    for qy in queries:
        try:
            for h in search.search(conn, qy, num_results=num_results):
                if h.url and h.url not in seen:
                    seen.add(h.url)
                    hits.append(h)
        except Exception as e:
            log(f"  consensus-forecast: a search failed ({str(e)[:50]})")
    if not hits:
        return {"verdict": "unmeasured", "n_forecasters": 0, "n_covered": 0, "outlets": [],
                "evidence_urls": [], "rationale": "search returned no hits — UNMEASURED (a dead lookup "
                "is NOT evidence of pre-consensus; widen the query / retry)."}
    forecasters: set[str] = set()
    covered: set[str] = set()               # broad: trade press + finance + forecasters (any authority)
    for h in hits:
        url = (h.url or "").lower()
        if any(m in url for m in FORECASTER_MARKERS):
            forecasters.add(_domain(url))
        if any(m in url for m in AUTHORITY_MARKERS):
            covered.add(_domain(url))
    nf, nc = len(forecasters), len(covered)
    n, outlets = nf, forecasters
    if nf >= 2:
        verdict = "priced"
    elif nf == 1:
        verdict = "partly"
    elif nc >= 3:
        verdict = "covered"                 # specialist/trade coverage, no forecaster-grade projection
    else:
        verdict = "unconfirmed"             # little surfaced — NOT a pre-consensus green light (keyless is blind to sell-side)
    rationale = (f"{nf} forecaster + {nc} broad-authority outlet(s) cover this "
                 f"({', '.join(sorted(covered)[:4]) or 'none'}) → "
                 + {"priced": "forecasters already project this — the consensus base case (PRICED)",
                    "partly": "one forecaster is here — partly priced; judge if it's the base case",
                    "covered": "specialist/trade press already covers this — known, not forecaster-grade (COVERED)",
                    "unconfirmed": "little authoritative coverage surfaced — but keyless search is BLIND to "
                                   "sell-side notes + specialist B2B press, so this is UNCONFIRMED, NOT a "
                                   "pre-consensus green light; the in-session judgment + the scored record decide"}[verdict])
    log(f"  consensus-forecast[{claim[:44]}] → {verdict.upper()} ({nf} forecaster, {nc} broad outlets)")
    return {"verdict": verdict, "n_forecasters": nf, "n_covered": nc, "outlets": sorted(forecasters),
            "covered_outlets": sorted(covered),
            "evidence_urls": [h.url for h in hits if h.url][:num_results], "rationale": rationale}


def _persist(conn: sqlite3.Connection, s: SaturationScore) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO saturation "
        "(id, topic, entity_id, as_of, saturation, tier, n_hits, n_authoritative, n_recent, "
        " verdict, rationale, evidence_urls, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (s.id, s.topic, s.entity_id, s.as_of.isoformat(), s.saturation, s.tier, s.n_hits,
         s.n_authoritative, s.n_recent, s.verdict, s.rationale, json.dumps(s.evidence_urls),
         s.created_at.isoformat()),
    )
    conn.commit()


def latest_for(conn: sqlite3.Connection, *, entity_id: str | None = None,
               topic: str | None = None) -> sqlite3.Row | None:
    """The most recent saturation read for an entity (by id) or a topic — a pure read for the board."""
    if entity_id:
        row = conn.execute(
            "SELECT * FROM saturation WHERE entity_id=? ORDER BY created_at DESC LIMIT 1",
            (entity_id,)).fetchone()
        if row:
            return row
    if topic:
        return conn.execute("SELECT * FROM saturation WHERE topic=?", (topic,)).fetchone()
    return None


def score_early_board(conn: sqlite3.Connection, *, limit: int = 12, log=print) -> dict:
    """Measure saturation for the current EARLY discovery candidates (the ones a pitch would cite).

    For each EARLY entity, search a query built from its name + domain, score it, and link it by
    entity_id so pre_consensus() can read the verdict and hard-demote the saturated ones. Returns a
    summary of how many flipped EARLY→PRICED once their real-world coverage was actually measured."""
    from engine import discover

    pc = discover.pre_consensus(conn)
    early = pc["early"][:limit]
    if not early:
        log("no EARLY candidates to score (run `discover` first).")
        return {"scored": 0, "demoted": 0}
    demoted = 0
    for e in early:
        topic = f"{e['name']} {e['domain'] or ''} shortage bottleneck supply constraint".strip()
        s = score_topic(conn, topic, entity_id=e["eid"], log=log)
        if s.verdict == "priced/known":
            demoted += 1
    log(f"\nscored {len(early)} EARLY candidate(s); {demoted} flip EARLY→PRICED once coverage is "
        f"measured (they were 'early' only because the indexed lag-channels missed the trade press).")
    return {"scored": len(early), "demoted": demoted}

"""The FORCES axis — politics/geo · social · talent · narrative (the cross-cutting forces).

The 9 pillars are a *causal data-flow spine* for ONE kind of thing: capability → supply → price.
But scarcity is also relocated by forces that act ACROSS that spine — a state cornering an input
by decree, a demographic labour cap, elite talent pivoting, a narrative cresting. The discovery
funnel was structurally blind to them (a politics- or society-driven constraint migration could
never surface on its own — the same class of blindness as missing deep learning). This module opens
that aperture. Each force is a *modulator* of the spine, tagged `domain="forces"`, kept to the SAME
falsifiable-scored discipline (a leading signal + a binding-constraint framing + a dated kill-metric
+ Brier) — never punditry. Added by the steering Decision of 2026-06-05 (widens plan.md's narrowed
scope; overrides the build moratorium for this one axis).

Two halves, like the rest of the engine:
  • DETECTOR half — thin keyless collectors that surface a force's leading signal as a series the
    frozen detector/FDR/discover funnel already consume (so a force can fire *autonomously*).
  • LENS half — the force as a frame for authoring structural calls in-session (the generative act,
    gated by `hypothesis.gate`). The first forces-driven calls live in the hypotheses table.

v1 detector = the GEOPOLITICS / NEWS force via GDELT (global news index, keyless). It reads the
*event-velocity* of supply-bending geopolitical events (export bans, chokepoints, sanctions on a
named input) — a politics force that creates scarcity by decree. HONEST PLACEMENT: news volume is an
ATTENTION channel (LAG/decoy-aware in discover.py, like Wikipedia/Federal-Register) — its job is
early-warning timing + feeding the consensus gate, NOT a leading capability detector. The genuinely
LEADING politics channel (a decreed-scarcity event repricing an input before the market catches up)
is the `[ ]` decreed-scarcity slot below.

DECREED-SCARCITY half (built 2026-06-05 — the genuinely LEADING politics channel). A decree (an
export ban, an Entity-List designation, a sanctions program) is itself the scarcity-creating ACT — it
runs AHEAD of the price repricing the cornered input, where GDELT/news only carry ATTENTION about it.
So this channel is placed LEADING in discover.py via a distinct provider (`ofac_bis`, NOT in
LAG_PROVIDERS) — unlike forces-GDELT (`gdelt`, LAG) and policy.py (`federal_register`, LAG). It reads
the Federal Register (keyless, dated, not throttled) for OFAC + BIS *rule* documents, types each to
the physical INPUT it corners (rare-earth refining, gallium/germanium, semiconductor compute, critical
minerals), nets polarity (a designation IMPOSES scarcity +1; a general-license/removal RELAXES it −1),
and emits a per-input monthly trailing-12-month NET decree-velocity series. A changepoint up = decreed
scarcity forming on that input before it is priced. This is the leading data-feed behind the authored
politics/geo call (weaponized export controls → ex-China refining as the binding constraint).

Mendeleev slots (mapped, not yet built — CONSTITUTION rule: reserved, created when the work arrives):
  [x] decreed-scarcity  — BUILT (see `collect_decreed` below): OFAC/BIS Federal-Register rule DELTAS,
                          typed per cornered input, polarity-netted, placed LEADING. (USITC tariff
                          deltas + per-entity Entity-List counts via LLM extraction = a v2 deepening.)
  [ ] social/demographic — labour-supply + acceptance (permitting/NIMBY) as binding constraints;
                          distinct from `slow.py` (which does demographic THRESHOLD binding) — here a
                          velocity/acceleration channel (e.g. skilled-trades wage acceleration).
  [—] talent (broadened) — NOT MEASURABLE with open data (investigated + rejected 2026-06-05). The
                          SCIENCE channel (`research.py:talent_inflow`, the recall jewel that caught
                          deep learning 2013) works because academic authorship is a clean, person-
                          level, leak-free inflow signal. Cross-industry/engineering talent has NO
                          equivalent: a GitHub repo COUNT is not people (hype-inflated, bot-noised,
                          one author → many repos), job postings measure DEMAND not inflow, and
                          LinkedIn-style title-migration is ToS-blocked. Filling the slot with a proxy
                          would inject unvalidated noise (the precision-tanking trap). The one
                          defensible extension if ever built = academia→industry AFFILIATION flux
                          (person-level, leak-free) — but it is still research-visible talent and
                          won't catch the manufacturing-led misses, so it stays unbuilt until proven.

$0 keyless; a cost-ledger row is logged (rule 3); the collector degrades gracefully when GDELT
throttles (it rate-limits this network hard — same per-IP wall patents hit; revisit via a spaced run
or the blessed proxy, §6).
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from math import sqrt

from engine import store
from engine.pillars.frontier import UA, _content_hash, _log_cost, _upsert_series, _upsert_source
from engine.schemas import Observation, Series, Source, SourceKind

GEO_PILLAR_ID = 8  # geopolitics modulates the policy/geo layer; tagged domain="forces" to mark the axis
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL_S = 6.0  # GDELT asks for ≤ 1 request / 5s — be a good citizen

# Supply-bending geopolitical EVENTS (a politics force that corners a physical input by decree), not
# tech themes. A detector fire = one of these breaking into global coverage — an early-warning that a
# scarcity shock is forming, before it reprices the input. Phrase-quoted to keep the query specific.
GEO_EVENTS: list[tuple[str, str]] = [
    ("rare earth export controls", '"rare earth" (export controls OR export ban)'),
    ("gallium germanium export curbs", '(gallium OR germanium) export'),
    ("semiconductor export controls", 'semiconductor "export controls"'),
    ("Taiwan Strait blockade", '"Taiwan Strait" (blockade OR tensions)'),
    ("Strait of Hormuz disruption", '"Strait of Hormuz"'),
    ("Red Sea shipping disruption", '"Red Sea" shipping'),
    ("Panama Canal drought", '"Panama Canal" drought'),
    ("critical minerals sanctions", '"critical minerals" (sanctions OR ban OR restrictions)'),
]
WINDOW_MONTHS = 60  # GDELT DOC index covers ~2017→present


def _timelinevol(query: str, *, retries: int = 2) -> list[tuple[date, float]] | None:
    """GDELT DOC 2.0 timelinevol → [(month_end, volume_intensity_pct)]. None on persistent throttle.

    `value` is the % of all global coverage matching the query — an attention-intensity, aggregated
    here to a monthly mean (point-in-time: a month's value is knowable at month-end)."""
    params = {"query": query, "mode": "timelinevol", "format": "json",
              "timespan": f"{WINDOW_MONTHS}m"}
    url = f"{GDELT_DOC}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=40).read()
            data = json.loads(raw)  # throttle returns a plain-text message → JSONDecodeError → retry
        except Exception:  # noqa: BLE001 — throttle/parse/network: back off, retry, then None
            if attempt < retries:
                time.sleep(GDELT_MIN_INTERVAL_S * (attempt + 1))
                continue
            return None
        tl = data.get("timeline") or []
        pts = tl[0].get("data", []) if tl else []
        # bucket daily points → monthly mean (drop the partial current month at read time elsewhere)
        by_month: dict[tuple[int, int], list[float]] = defaultdict(list)
        for p in pts:
            try:
                d = date.fromisoformat(p["date"][:10])
                by_month[(d.year, d.month)].append(float(p["value"]))
            except (KeyError, ValueError):
                continue
        out: list[tuple[date, float]] = []
        for (y, m), vals in sorted(by_month.items()):
            # month-end as_of; next-month-day-1 minus a day, cheaply
            last_day = 28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31)
            out.append((date(y, m, last_day), statistics.fmean(vals)))
        return out or None


def collect(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """GEOPOLITICS/NEWS force: GDELT event-velocity per supply-bending geopolitical event. Idempotent.

    $0. Degrades gracefully: if GDELT throttles this network (frequent — per-IP rate wall), it logs
    and returns 0 series rather than faking data; a later spaced run (or the proxy, §6) populates it.
    """
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "gdelt_forces_collect", "gdelt", float(len(GEO_EVENTS)))
    # probe once — if GDELT is throttling, skip the whole run cleanly (no half-built series)
    if _timelinevol(GEO_EVENTS[0][1]) is None:
        log("  ! GDELT unreachable/throttled this run — 0 geo-force series (revisit spaced or via proxy).")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0, "throttled": True}
    n_series = n_obs = 0
    for label, query in GEO_EVENTS:
        pts = _timelinevol(query)
        time.sleep(GDELT_MIN_INTERVAL_S)
        if not pts or len(pts) < 12:
            log(f"  - skip {label!r} ({0 if not pts else len(pts)} months)")
            continue
        payload = {p[0].isoformat(): round(p[1], 4) for p in pts}
        src = Source(
            url=f"{GDELT_DOC}?query={urllib.parse.quote(query)}&mode=timelinevol",
            title=f"GDELT event-velocity — {label}",
            pillar_id=GEO_PILLAR_ID, kind=SourceKind.news, trust_score=55,
            trust_rationale=(
                "GDELT DOC 2.0 timelinevol (keyless, global news index): monthly mean of the % of "
                "world coverage matching a supply-bending geopolitical EVENT. ATTENTION-class "
                "(decoy-aware, LAG in discover.py) — an early-warning/timing + consensus-gate signal, "
                "NOT a leading capability detector; the rate-of-change of an EVENT (not a theme) is "
                "the signal. Trust 55: news volume is noisy/manipulable; phrase-quoted to stay specific."
            ),
            recency=pts[-1][0], content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=GEO_PILLAR_ID, source_id=source_id, provider="gdelt",
            external_id=label, label=f"{label} (GDELT)", metric="gdelt_volume_intensity",
            unit="pct_coverage", domain="forces",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=d, value=v, unit="pct_coverage",
                        uncertainty=max(1e-4, v * 0.10))  # ~10% relative on a noisy attention %
            for d, v in pts
        ])
        n_series += 1
        n_obs += len(pts)
        log(f"  + {label:<32} {pts[0][0]}→{pts[-1][0]}  {len(pts)} months")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs, "throttled": False}


# ─────────────────────────────────────────────────────────────────────────────
# DECREED-SCARCITY — the LEADING politics channel (OFAC/BIS Federal-Register rule deltas)
# ─────────────────────────────────────────────────────────────────────────────
FED_REGISTER = "https://www.federalregister.gov/api/v1/documents.json"
DECREE_AGENCIES = ["foreign-assets-control-office", "industry-and-security-bureau"]  # OFAC + BIS
DECREE_WINDOW_START = 2004  # Federal Register API full coverage; ~2 pages of rules total

# Physical INPUTS a decree can corner. A rule is typed to an input if any term appears in its
# title+abstract (lowercased). Phrase-specific to stay on the physical input, not the country program.
DECREE_INPUTS: list[tuple[str, tuple[str, ...]]] = [
    ("rare_earth_refining", ("rare earth", "rare-earth", "neodymium", "dysprosium", "samarium",
                             "praseodymium", "terbium", "lanthanide", "permanent magnet")),
    ("gallium_germanium", ("gallium", "germanium")),
    ("semiconductor_compute", ("semiconductor", "advanced computing", "lithography", "euv ",
                               "integrated circuit", "high bandwidth memory", "advanced node")),
    ("critical_minerals", ("critical mineral", "lithium", "cobalt", "graphite", "antimony",
                           "tungsten", "tantalum")),
]
# Polarity: a rule RELAXES scarcity if it carries an explicit relaxation marker (a general license,
# a removal/delisting, an authorization); otherwise a rule from these two decree agencies IMPOSES it.
# Keyword-classed and broad on purpose — the rate-of-change of the NET is the signal, not the level.
DECREE_RELAX = ("general license", "removal of", "remove", "delete", "delist", "authoriz",
                "rescind", "license exception", "easing", "waiver")
DECREE_MIN_MONTHS = 24  # need a real curve before the changepoint detector can read it


def _fetch_decrees(*, retries: int = 2, log=print) -> list[tuple[date, str]] | None:
    """All OFAC+BIS RULE docs since DECREE_WINDOW_START → [(pub_date, title+abstract lower)]. None on
    persistent failure. Paginated static-file-style read of the keyless Federal Register API (not the
    GDELT-style throttle: generous limits, no per-IP wall)."""
    out: list[tuple[date, str]] = []
    page = 1
    while True:
        params = [("conditions[agencies][]", a) for a in DECREE_AGENCIES]
        params += [("conditions[type][]", "RULE"),
                   ("conditions[publication_date][gte]", f"{DECREE_WINDOW_START}-01-01"),
                   ("per_page", "1000"), ("page", str(page)), ("order", "oldest"),
                   ("fields[]", "publication_date"), ("fields[]", "title"), ("fields[]", "abstract")]
        url = f"{FED_REGISTER}?{urllib.parse.urlencode(params)}"
        data = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                data = json.loads(urllib.request.urlopen(req, timeout=40).read())
                break
            except Exception:  # noqa: BLE001 — rate-limit/parse/network: back off, retry, then None
                if attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None if not out else out  # partial pages already in hand are still usable
        results = data.get("results", []) if data else []
        for r in results:
            try:
                d = date.fromisoformat(r["publication_date"][:10])
            except (KeyError, ValueError, TypeError):
                continue
            blob = f"{r.get('title') or ''} {r.get('abstract') or ''}".lower()
            out.append((d, blob))
        if not results or page >= (data.get("total_pages", 1) if data else 1):
            break
        page += 1
        time.sleep(0.3)
    return out or None


def _monthly_ttm_net(events: list[tuple[date, int]]) -> list[tuple[date, float]]:
    """[(date, polarity±1)] → monthly trailing-12-month NET series [(month_end, net)]. Point-in-time:
    a month-end's value is the signed count of decrees in the prior 12 months (knowable then)."""
    if not events:
        return []
    events = sorted(events)
    start, end = events[0][0], events[-1][0]
    out: list[tuple[date, float]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last_day = 28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31)
        me = date(y, m, last_day)
        lo = date(y - 1, m, 1)  # 12-month trailing window: (lo, me]
        net = sum(pol for d, pol in events if lo < d <= me)
        out.append((me, float(net)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def collect_decreed(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """DECREED-SCARCITY: per-input monthly TTM net decree-velocity from OFAC/BIS Federal-Register
    rules. Idempotent. $0, keyless. The LEADING politics channel (provider `ofac_bis`, not LAG)."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "decreed_scarcity_collect", "federal_register", float(len(DECREE_INPUTS)))
    decrees = _fetch_decrees(log=log)
    if not decrees:
        log("  ! Federal Register unreachable — 0 decreed-scarcity series.")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0}
    log(f"  · {len(decrees)} OFAC/BIS rules {decrees[0][0]}→{decrees[-1][0]}")
    n_series = n_obs = 0
    for label, terms in DECREE_INPUTS:
        events: list[tuple[date, int]] = []
        for d, blob in decrees:
            if any(t in blob for t in terms):
                pol = -1 if any(r in blob for r in DECREE_RELAX) else 1
                events.append((d, pol))
        pts = _monthly_ttm_net(events)
        if len(pts) < DECREE_MIN_MONTHS:
            log(f"  - skip {label!r} ({len(events)} decrees, {len(pts)} months)")
            continue
        payload = {p[0].isoformat(): p[1] for p in pts}
        src = Source(
            url=f"{FED_REGISTER}?agencies=ofac,bis&type=rule&input={urllib.parse.quote(label)}",
            title=f"OFAC/BIS decree-velocity — {label}",
            pillar_id=GEO_PILLAR_ID, kind=SourceKind.filing, trust_score=78,
            trust_rationale=(
                "Federal Register API (keyless, official US rulemaking): OFAC + BIS RULE documents "
                "typed to a physical input and polarity-netted (a designation/control IMPOSES scarcity "
                "+1; a general-license/removal RELAXES it −1), as a monthly trailing-12-month NET. "
                "LEADING (provider `ofac_bis`, not in LAG_PROVIDERS): a decree is the scarcity-creating "
                "ACT, ahead of the price — unlike GDELT news (attention) or broad Fed-Register term "
                "velocity (policy.py). Trust 78: official + dated, but keyword typing/polarity is broad "
                "so the rate-of-change of the net is the signal, not the level. v2 = per-entity counts "
                "via LLM extraction + USITC tariff deltas."
            ),
            recency=pts[-1][0], content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=GEO_PILLAR_ID, source_id=source_id, provider="ofac_bis",
            external_id=label, label=f"{label} (OFAC/BIS decrees)",
            metric="decree_scarcity_velocity", unit="net_decrees_ttm", domain="forces",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=d, value=v, unit="net_decrees_ttm",
                        uncertainty=max(0.5, abs(v) ** 0.5))
            for d, v in pts
        ])
        n_series += 1
        n_obs += len(pts)
        peak = max(pts, key=lambda p: p[1])
        log(f"  + {label:<22} {len(events):>3} decrees  TTM-net peak {peak[1]:.0f} @ {peak[0]}")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}


# ─────────────────────────────────────────────────────────────────────────────
# CHINA DECREE-FOOTPRINT — the OTHER side of the politics force (confirmation/LAG, not leading)
# ─────────────────────────────────────────────────────────────────────────────
# China decrees the scarcities the US decree channel is blind to (gallium/germanium Aug-2023, graphite
# Oct-2023, rare-earth tech Dec-2023, antimony 2024, NdFeB magnets Apr-2025) — but its decrees are not
# in any keyless feed: MOFCOM English is geoblocked, the Chinese site's history is un-paginable post-
# restructure, and a Chinese-HTML scrape would be brittle GIGO. What IS clean and keyless is the
# decree's PHYSICAL FOOTPRINT: China's own export VALUE of the cornered input (UN Comtrade preview).
# A control biting shows as an export collapse — e.g. rare-earth compounds (HS 2846) $671M(2022)→
# $393M(2024), −41%. HONEST PLACEMENT: annual + ~12-month reporting lag → this CANNOT lead (it confirms
# a decree long after the price), so it is a LAG/confirmation channel (provider `comtrade_china`, in
# LAG_PROVIDERS — it must never mint a pre-consensus EARLY by itself). Its job is to make the rare-earth
# / critical-minerals calls' kill-metric a COMPUTABLE live feed (a trade proxy for the ex-China-refining
# migration; trade ≠ refining, so it corroborates, not proves). The genuinely-LEADING China-decree slot
# stays open — its unlock is the blessed proxy (§6) + a Chinese-language parse, not a clean source today.
COMTRADE_PREVIEW = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CHINA_REPORTER = 156
COMTRADE_WINDOW_START = 2012
# Cornered inputs → HS6 code. Only those with clean, multi-year China export data survive the gate.
CHINA_INPUTS: list[tuple[str, str]] = [
    ("rare_earth_compounds", "2846"),    # the jewel — rare-earth oxides/salts (separation output)
    ("rare_earth_metals", "280530"),     # refined rare-earth metals
    ("permanent_magnets", "850511"),     # sintered NdFeB magnets (Apr-2025 control)
    ("natural_graphite", "250410"),      # anode feedstock (Oct-2023 control)
    ("gallium_germanium", "811292"),     # Ga/Ge basket (Aug-2023 control; coarse — 7-metal HS)
    ("antimony", "811010"),              # unwrought antimony (2024 control)
]
CHINA_MIN_YEARS = 5


def _parse_comtrade(data: dict) -> list[tuple[int, float]] | None:
    out: list[tuple[int, float]] = []
    for r in data.get("data", []) or []:
        try:
            v = float(r["primaryValue"])
            if v > 0:
                out.append((int(r["refYear"]), v))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(out) or None


COMTRADE_MAX_PERIODS = 12  # the preview endpoint rejects >12 periods/call with HTTP 400


def _comtrade_get(url: str, *, retries: int, proxy_provider: str | None, log) -> dict | None:
    """One Comtrade GET. DIRECT first (free); if this IP is throttled and a proxy is configured,
    escalate to a fresh rotating proxy IP (cost-gated spend, Ruben-approved — the blessed ladder §6)."""
    rungs: list[str | None] = [None] + ([proxy_provider] if proxy_provider else [])
    for prov in rungs:
        for attempt in range(retries + 1):
            try:
                if prov:
                    import httpx
                    from engine.adapters import proxy as _proxy
                    with httpx.Client(proxy=_proxy.proxy_url(prov), timeout=45,
                                      headers={"User-Agent": UA}) as cl:
                        return cl.get(url).json()  # fresh rotating IP per Client → dodges per-IP 429
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                return json.loads(urllib.request.urlopen(req, timeout=45).read())
            except Exception:  # noqa: BLE001 — 429 / proxy / parse: back off, retry, then next rung
                if attempt < retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
        if prov is None and proxy_provider:
            log("    · Comtrade direct throttled — escalating to proxy (§6).")
    return None


def _china_exports(hs: str, *, retries: int = 3, proxy_provider: str | None = None,
                   log=print) -> list[tuple[int, float]] | None:
    """China annual export VALUE (USD) of HS code → [(year, value)]. Chunked into ≤12-period calls
    (the preview 400s above that), merged. None if any chunk fails."""
    all_years = list(range(COMTRADE_WINDOW_START, 2025))
    merged: dict[int, float] = {}
    for i in range(0, len(all_years), COMTRADE_MAX_PERIODS):
        chunk = all_years[i:i + COMTRADE_MAX_PERIODS]
        params = {"reporterCode": CHINA_REPORTER, "period": ",".join(str(y) for y in chunk),
                  "cmdCode": hs, "flowCode": "X", "partnerCode": 0}
        url = f"{COMTRADE_PREVIEW}?{urllib.parse.urlencode(params)}"
        data = _comtrade_get(url, retries=retries, proxy_provider=proxy_provider, log=log)
        if data is None:
            return None
        for y, v in _parse_comtrade(data) or []:
            merged[y] = v
    return sorted(merged.items()) or None


def collect_china_footprint(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """CHINA decree-footprint: China annual export value of cornered inputs (UN Comtrade, keyless).
    Idempotent. $0. CONFIRMATION/LAG channel (`comtrade_china`) — the rare-earth call's computable
    kill-metric proxy, not a leading detector."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    from engine.adapters import proxy as _proxy
    # direct is free; the proxy is the throttle escape hatch (resi Evomi → DC Floxy → none).
    prov = "evomi" if _proxy.available("evomi") else ("floxy" if _proxy.available("floxy") else None)
    _log_cost(conn, "china_footprint_collect", f"comtrade{'+'+prov if prov else ''}",
              float(len(CHINA_INPUTS)))
    if _china_exports(CHINA_INPUTS[0][1], proxy_provider=prov, log=log) is None:
        log("  ! Comtrade unreachable (direct + proxy) — 0 China-footprint series.")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0}
    n_series = n_obs = 0
    for label, hs in CHINA_INPUTS:
        pts = _china_exports(hs, proxy_provider=prov, log=log)
        time.sleep(1.0)  # be a good citizen to the preview endpoint
        if not pts or len(pts) < CHINA_MIN_YEARS:
            log(f"  - skip {label!r} (HS {hs}: {0 if not pts else len(pts)} yrs clean)")
            continue
        payload = {str(y): round(v) for y, v in pts}
        src = Source(
            url=f"{COMTRADE_PREVIEW}?reporterCode=156&cmdCode={hs}&flowCode=X",
            title=f"China export value — {label} (HS {hs})",
            pillar_id=GEO_PILLAR_ID, kind=SourceKind.filing, trust_score=70,
            trust_rationale=(
                "UN Comtrade preview (keyless): China's annual export VALUE (USD) of a cornered input. "
                "A Chinese export-control decree shows as an export collapse (rare-earth compounds HS "
                "2846: $671M 2022 → $393M 2024). CONFIRMATION/LAG channel (provider `comtrade_china`, in "
                "LAG_PROVIDERS — must NOT mint a pre-consensus EARLY): annual + ~12mo reporting lag, so "
                "it corroborates a decree long after the price, and it is the only keyless China feed "
                "(MOFCOM is geoblocked / un-paginable). Trust 70: official trade data but a PROXY — trade "
                "≠ refining capacity, and basket HS codes (811292) blur a single input. Grounds the "
                "rare-earth/critical-minerals calls' kill-metric as a live computable feed."
            ),
            recency=date(pts[-1][0], 12, 31), content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=GEO_PILLAR_ID, source_id=source_id, provider="comtrade_china",
            external_id=label, label=f"{label} (China exports)",
            metric="china_export_value", unit="usd", domain="forces",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=date(y, 12, 31), value=v, unit="usd",
                        uncertainty=max(1.0, v * 0.05))  # ~5% on trade-data revisions
            for y, v in pts
        ])
        n_series += 1
        n_obs += len(pts)
        log(f"  + {label:<22} HS {hs}  {pts[0][0]}→{pts[-1][0]}  "
            f"${pts[0][1]/1e6:.0f}M→${pts[-1][1]/1e6:.0f}M")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}


# ─────────────────────────────────────────────────────────────────────────────
# CHINA DECREES — the genuinely LEADING China-decree channel (mirror of OFAC/BIS for China)
# ─────────────────────────────────────────────────────────────────────────────
# The decree's PHYSICAL footprint (collect_china_footprint) is lagged confirmation; the LEADING signal
# is the decree ACT itself, dated, the moment China corners an input. MOFCOM's own English mirror is
# down (502, even via proxy), but China's official Export Control Information Network
# (exportcontrol.mofcom.gov.cn) is reachable — refuting the earlier "no clean China source" verdict.
# Two gotchas probed before building (GIGO discipline): the JSON API mislabels its charset → returns
# '?'-corrupted CJK UNLESS you send `Accept: application/json;charset=utf-8`; and its PAGINATION IS
# SERVER-BROKEN (every pageNum returns the same 20 featured rows — total=897/maxPageNum=45 is a lie),
# so the full multi-year archive is NOT keyless-reachable. We take the featured JSON set + the homepage's
# dated decree links (RECENT-ONLY — captures the Oct-2025 rare-earth megacontrol, the largest ever, but
# misses the 2023 gallium/graphite actions) and refuse to fabricate the missing backfill. We keyword-type
# each doc to the cornered input (稀土 rare-earth, 镓/锗 Ga/Ge, 石墨 graphite, 锑 antimony, 钨 tungsten),
# net polarity (列入/加强 IMPOSES +1, 移出/删除 RELAXES −1), emit a monthly TTM-net decree-velocity series,
# LEADING (provider="mofcom_ec", NOT in LAG_PROVIDERS). HONEST STATUS: a forward-accumulating monitor —
# short today (the detector skips it as too-short until it grows), the seed of the live China-decree
# channel + the engine's record of the megacontrol. Deep backfill needs the un-paginable archive solved.
MOFCOM_EC_API = "http://exportcontrol.mofcom.gov.cn/edi_ecms_web_front/front/column/getColumnList"
CHINA_DECREE_INPUTS: list[tuple[str, tuple[str, ...]]] = [
    ("rare_earth_refining", ("稀土", "镝", "钐", "钕", "铽", "镨", "钆", "钷", "钬", "铒", "永磁")),
    ("gallium_germanium", ("镓", "锗")),
    ("graphite", ("石墨",)),
    ("antimony", ("锑",)),
    ("tungsten", ("钨",)),
]
CHINA_DECREE_ACTION = ("公告", "列入", "管控名单", "加强出口管制", "实施出口管制", "管制措施", "出口管制措施")
CHINA_DECREE_RELAX = ("移出", "予以删除", "解除管制", "不予列入")
CHINA_DECREE_MIN_MONTHS = 6  # young, recent-only feed (the archive is un-paginable — see _mofcom_decrees)
MOFCOM_EC_HOME = "http://exportcontrol.mofcom.gov.cn/"


def _mofcom_decrees(*, retries: int = 2, log=print) -> list[tuple[date, str]] | None:
    """Reachable dated export-control docs from China's Export Control Information Network →
    [(pub_date, title+content)], deduped. HONEST LIMITATION: the getColumnList endpoint's pagination
    is server-broken (every pageNum returns the same 20 featured rows), so the full 897-doc archive is
    NOT reachable keyless — we take the featured JSON set + the homepage's dated decree links (recent-
    only; misses pre-2025 actions). No fabricated backfill. None on persistent failure."""
    items: dict[str, tuple[date, str]] = {}
    # (1) featured JSON set — full title+content, real CJK via the charset header
    headers = {"User-Agent": UA, "Content-Type": "application/json",
               "Accept": "application/json;charset=utf-8"}
    for attempt in range(retries + 1):
        try:
            body = json.dumps({"columnID": 1, "pageNum": 1, "pageSize": 20}).encode()
            raw = urllib.request.urlopen(
                urllib.request.Request(MOFCOM_EC_API, data=body, headers=headers), timeout=20).read()
            for r in json.loads(raw.decode("utf-8", "ignore")).get("pageInfo", {}).get("rows", []):
                u = r.get("url")
                try:
                    d = date.fromisoformat((r.get("publishTimeStr") or "")[:10])
                except ValueError:
                    continue
                if u:
                    items[u] = (d, f"{r.get('title') or ''} {r.get('content') or ''}")
            break
        except Exception:  # noqa: BLE001 — network/parse: back off, retry
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    # (2) homepage dated decree links (title only; date = YYYYMM in the article path)
    try:
        hp = urllib.request.urlopen(
            urllib.request.Request(MOFCOM_EC_HOME, headers={"User-Agent": UA}), timeout=20
        ).read().decode("utf-8", "ignore")
        import re
        for url, ym, title in re.findall(
                r'href="(/article/[^"]+/(\d{6})/\d+\.html)"[^>]*title="([^"]{6,80})"', hp):
            if url not in items:  # prefer the JSON row's fuller blob when both have it
                items[url] = (date(int(ym[:4]), int(ym[4:6]), 1), title)
    except Exception:  # noqa: BLE001 — homepage optional; the JSON set already seeded items
        pass
    return sorted(items.values()) or None


def collect_china_decrees(conn: sqlite3.Connection | None = None, *, log=print) -> dict:
    """CHINA DECREES: per-input monthly TTM-net decree-velocity from China's Export Control Information
    Network. Idempotent. $0 keyless. The genuinely-LEADING China-decree channel (provider `mofcom_ec`,
    not LAG) — the mirror of `collect_decreed` (OFAC/BIS) for the China side."""
    from engine import db
    own = conn is None
    if own:
        conn = db.connect()
        db.init_db(conn)
    _log_cost(conn, "china_decrees_collect", "mofcom_ec", float(len(CHINA_DECREE_INPUTS)))
    docs = _mofcom_decrees(log=log)
    if not docs:
        log("  ! MOFCOM export-control network unreachable — 0 China-decree series.")
        conn.commit()
        if own:
            conn.close()
        return {"series": 0, "obs": 0}
    log(f"  · {len(docs)} export-control docs {min(d for d, _ in docs)}→{max(d for d, _ in docs)}")
    n_series = n_obs = 0
    for label, terms in CHINA_DECREE_INPUTS:
        events: list[tuple[date, int]] = []
        for d, blob in docs:
            if any(a in blob for a in CHINA_DECREE_ACTION) and any(t in blob for t in terms):
                pol = -1 if any(r in blob for r in CHINA_DECREE_RELAX) else 1
                events.append((d, pol))
        pts = _monthly_ttm_net(events)
        if len(pts) < CHINA_DECREE_MIN_MONTHS:
            log(f"  - skip {label!r} ({len(events)} decrees, {len(pts)} months)")
            continue
        payload = {p[0].isoformat(): p[1] for p in pts}
        src = Source(
            url=f"{MOFCOM_EC_API}#input={urllib.parse.quote(label)}",
            title=f"China export-control decree-velocity — {label}",
            pillar_id=GEO_PILLAR_ID, kind=SourceKind.filing, trust_score=80,
            trust_rationale=(
                "China's official Export Control Information Network (exportcontrol.mofcom.gov.cn, "
                "keyless JSON API): dated 公告 announcements that add a cornered input to a control list, "
                "keyword-typed to the input and polarity-netted (列入/加强 IMPOSES +1; 移出/删除 RELAXES "
                "−1), as a monthly trailing-12-month NET. The genuinely-LEADING China-decree channel "
                "(provider `mofcom_ec`, not LAG) — the decree is the scarcity-creating ACT, ahead of the "
                "price and of the Comtrade export-collapse footprint (`comtrade_china`, LAG). Mirror of "
                "the US OFAC/BIS `decreed` channel for China. Trust 80: official + dated, CJK keyword "
                "typing broad → rate-of-change is the signal. LIMITATION (disclosed, not faked): the "
                "archive endpoint's pagination is server-broken, so this is the RECENT-only reachable set "
                "(captures the Oct-2025 rare-earth megacontrol; misses pre-2025 actions) — a forward-"
                "accumulating monitor, short until it grows; no fabricated backfill."
            ),
            recency=pts[-1][0], content_hash=_content_hash(payload),
        )
        source_id = _upsert_source(conn, src)
        series = Series(
            pillar_id=GEO_PILLAR_ID, source_id=source_id, provider="mofcom_ec",
            external_id=label, label=f"{label} (China decrees)",
            metric="decree_scarcity_velocity", unit="net_decrees_ttm", domain="forces",
        )
        series_id = _upsert_series(conn, series)
        store.bulk_upsert_observations(conn, [
            Observation(series_id=series_id, as_of=d, value=v, unit="net_decrees_ttm",
                        uncertainty=max(0.5, abs(v) ** 0.5))
            for d, v in pts
        ])
        n_series += 1
        n_obs += len(pts)
        peak = max(pts, key=lambda p: p[1])
        log(f"  + {label:<22} {len(events):>3} decrees  TTM-net peak {peak[1]:.0f} @ {peak[0]}")
    conn.commit()
    if own:
        conn.close()
    return {"series": n_series, "obs": n_obs}

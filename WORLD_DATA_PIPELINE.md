# WORLD_DATA_PIPELINE.md — "Query the World"

**Status: TOP PRIORITY (Ruben, 2026-06-16).** This is the master plan. The narrower
`DATA_LAYER_PLAN.md` is the keyless foundation and is partly shipped; this document is the
scale-up to a continuous, LLM-structured, world-scale substrate. Read both.

---

## 0. Why this is the top priority (the defensibility argument)

The open question hanging over the whole project: *are we just a prompt layer on top of Opus?*
On the raw forecast, today, largely yes. The prompt is commoditized. Anyone can call Opus.

The data layer is the answer. It is the one thing that is **not** a prompt and that a competitor
cannot reproduce by copying our prompts:

1. A **leak-free, dated, scored record** nobody can fake retroactively. The credential.
2. A **decorrelated structural signal** the model does not already carry in its weights, mined
   from the whole world's leading indicators. The edge.

If we are judged on data, we win on data. If we are judged on prompts, we are one fine-tune away
from irrelevance. This pipeline is how we get judged on data. It is the moat, stated plainly.

The thesis the data serves (unchanged): *rent accrues to the binding constraint; the edge is
spotting where the constraint moves before it is priced in.* To see the constraint move you must
see the whole graph: research → patents → filings → capital → news → prices, linked by entity
and concept, dated, before consensus.

---

## 1. The vision

One queryable substrate of the world's leading indicators of where scarcity and value migrate.
You ask it a question in plain language and it returns the dated, structured evidence: who is
publishing, who is patenting, who is filing, where capital is flowing, what is being said, what is
priced. The human+AI loop reasons over that, not over Opus's memory.

"Query the world" = research PDFs + patents + filings + capital flows + news + policy + prices,
all extracted into entities, concepts, claims, and auto-minted signal series, continuously updated.

---

## 2. What already exists (do NOT rebuild — see DATA_LAYER_PLAN.md build log)

- **OpenAlex full snapshot** on S3 (`vaticinus-datalake-405844305300-us-east-1`), frozen dated vintage.
- **3,000,604,635 citation edges** as Parquet (35 GB), one $3.20 Athena scan, queryable forever.
- **~70k-entity global concept index** (L0–L5, per-year counts).
- Leading channels: citation velocity by field, cross-field bridge, sub-topic share, diffusion.
- **Patents** for 18 global topics on S3 (BigQuery extracts, within free tier).
- **Paper→patent linkage** via Marx-Fuegi Reliance on Science (47.8M citations → 35,560 concepts).
- **`engine/signals.py evidence_pack(topic)`** + `chat_bridge signals` seam: resolves a question to
  leading signals across all channels, LLM-readable, already grounding the scored Python forecasters.
- ~20 keyless feeds (Crossref, bioRxiv, Comtrade, Eurostat, FAOSTAT, World Bank, SEC EDGAR, GDELT,
  USGS minerals, V-Dem, UCDP, IMF, OECD, ILO, Polymarket, Metaculus ...) via `collect_all`.

**The gap:** these are thin cross-sections of a few hand-picked topics. The world is not covered,
the raw text is not LLM-extracted into structure, and nothing is continuous. That is what we build.

---

## 3. Architecture — five tiers

```
T0 INGEST     keyless-first + authenticated bulk loaders, scheduled, idempotent, DATED
                (real published date != fetched_at; leak discipline is non-negotiable)
                        |
T1 LAKE       raw corpus as Parquet in object storage, partitioned by source/date
                queryable in place (DuckDB / Athena). NEVER in foresight.db.
                        |
T2 EXTRACT    cheap-LLM map-reduce over raw text at scale -> structured rows:
                entities, concepts, claims, numbers, dates, sentiment, relationships
                + entity resolution (the most neglected, highest-value layer)
                        |
T3 GRAPH+SIGNALS   unified entity/concept dependency graph + auto-minted time-series per
                node (research velocity, patent HHI, capital inflow, talent flow, narrative
                saturation, commercialization intensity, price channel) -> foresight.db (derived only)
                        |
T4 QUERY      plain-language -> structured query over lake + signals + graph;
                wired into the forecast loop so every call is data-grounded (evidence_pack, scaled)
```

The seam already exists at T4 (`evidence_pack`). The build is mostly T0–T2 at world scale, then
auto-minting T3 over everything instead of 18 topics.

---

## 4. The sources (the world), mapped to the thesis spine

| Spine layer | Sources | Access | Scale | Cost posture |
|---|---|---|---|---|
| **Frontier / research** | OpenAlex (250M works), arXiv full text (LaTeX), Crossref, Semantic Scholar S2AG, PubMed/PMC, bioRxiv | S3 snapshots / dumps | ~hundreds GB | free snapshots; arXiv LaTeX egress small |
| **Capability / patents** | Google Patents (BigQuery, global incl. CN, ~150M), USPTO bulk XML (US-only, all-AWS), EPO OPS, reliance-on-science linkage | BQ metered / S3 bulk | 10–50 GB extracts | ~$20–50 BQ scans, or $0 USPTO-only |
| **Capital / corporate** | SEC EDGAR (10-K/Q, 8-K, S-1, 13F, Form 4) full text + XBRL; Companies House (UK); GLEIF LEI backbone | bulk / API | 20–50 GB | free |
| **Capital flows** | NIH RePORTER, NSF, EU CORDIS, SBIR (grants); USAspending + SAM.gov (gov contracts); UN Comtrade / BACI (trade); equity/FX/rates; prediction markets | API / flat files | <30 GB | free; premium VC (Crunchbase) is paid, deferred |
| **News / narrative** | GDELT (global event firehose, BigQuery), Common Crawl news (full article text), RSS firehoses, Perplexity Sonar (live) | BQ / S3 / API | extract events only | ~$5/TB BQ; Sonar metered |
| **Policy** | MOFCOM, BIS export controls, EUR-Lex, Federal Register, regulations.gov, FDA/EMA, central-bank comms | keyless / scrape | small | free (some CN via proxy) |
| **Physical / supply** | EIA/IEA energy, USGS minerals, commodity production, shipping AIS (later), satellite (later) | API / bulk | <20 GB | free core; alt-data paid, deferred |

Coverage rule: hoard the **leading** corpora (research, patents, filings — where the signal leads
price), sample the lagging macro series, extract-and-discard the firehoses (news, events).

---

## 5. The LLM extraction layer (the "even with LLM if needed" part — the real unlock)

This is the difference between "pipes" and "water." Raw text is useless until it is structured.
Run cheap LLMs map-reduce style over the lake to turn ~50M high-value documents into rows:

- **Entities** (companies, institutions, people, assets, places) + **resolution** to one canonical
  ID across every source. "TSMC" = "Taiwan Semiconductor" = ticker TSM = its LEI = its OpenAlex
  institution id. This is the join key for the whole graph and the most neglected layer.
- **Concepts / claims** ("X depends on Y", "company Z is scaling capacity for W"), each dated, with
  source provenance, becoming `depends_on` edges in the dependency graph.
- **Numbers** (capacity, lead time, funding, price, headcount) pulled into the signal series.
- **Sentiment / narrative saturation** per concept (the priced-vs-unpriced gate).

**Why the cost is genuinely minimal (Ruben is right):**
- ~50M docs x ~1.5k input + ~400 output tokens ≈ **~95B tokens** for a full one-time backfill.
- Cheap small model via batch API (~$0.10/M in, ~$0.30/M out) → **~$13k one-time**, OR
- Self-host a 7–8B extractor on rented GPUs → **~$4–8k one-time** over a few weeks.
- Incremental (new docs/day) is a tiny fraction → **low hundreds/month** thereafter.

Use the cheapest model that holds quality on a graded eval set; reserve Opus only for spot-checks
and the final forecast. Quality gate (GIGO) on every extractor: a labeled sample, precision/recall
tracked, before its output is trusted into the graph. We already hit one OpenAlex spam cluster;
assume more.

---

## 6. Storage + compute + cost model (honest, credits-rule-aware)

**HARD CONSTRAINT:** the lake bucket is on AWS account `405844305300`, which is **NOT
credit-covered** (see cloud-credits-only rule). Metered AWS there is real cash. Keep spend
column-pruned, partition-filtered, and logged. Prefer free snapshots and one-time scans.

- **Storage:** full world Parquet working set ~2–5 TB kept → ~$50–120/mo on S3 (+$16/mo existing
  OpenAlex). R2 (no egress) is the cheaper alt if we move off the non-credit account.
- **One-time backfill compute:** Athena scans (~$3 each, a handful) + LLM extraction $4–13k.
- **Continuous run:** ingestion is bandwidth (~free), incremental extraction low hundreds/mo,
  storage growth modest. **All-in steady state well under $1k/month.**

**Bottom line: building and proving v1 costs single-digit thousands one-time and <$1k/mo.** Ruben
is correct that this is minimal relative to the prize.

---

## 7. Build order (highest leverage first)

- **Phase 1 — Lake foundation (weeks, ~free).** Stand up DuckDB-over-S3 query. Bulk-load EDGAR full,
  GDELT events, USPTO/Google Patents global, grants (NIH/NSF/CORDIS/SBIR), USAspending, Comtrade/BACI,
  GLEIF + Companies House. Partition by source/date. Reconcile against the existing OpenAlex/Comtrade loads.
- **Phase 2 — Extraction + entity resolution (the core lift).** Graded extractor on a cheap model;
  run map-reduce over research + patents + filings + key news; resolve entities to one canonical id.
  Land structured rows + `depends_on` edges. This is where we stop being a prompt layer.
- **Phase 3 — Auto-mint signals over EVERYTHING.** Generalize the 18-topic channels to every concept
  in the 70k index: velocity, HHI, capital inflow, talent flow, saturation, commercialization, price
  channel. Land derived series in foresight.db.
- **Phase 4 — World query.** Plain-language → query over lake+graph+signals; scale `evidence_pack`
  from hand-picked topics to anything; wire into forecastbench + metaculus + pope prompt assembly.
- **Phase 5 — Continuous + premium.** Cron every collector; add paid feeds (real-time prices,
  Crunchbase, premium patent/alt-data, satellite) only where they beat free on a measured basis.
  This is what the raise funds.

**Proof gate (ties to the ablation):** the pipeline is validated when full-system-with-data-layer
beats raw Opus on a leak-free holdout (see system-vs-raw-opus-ablation). That delta is the moat,
measured.

---

## 8. The raise — how much, for what, when

**You do NOT need millions to build or prove v1.** The design is keyless-first and cheap:
~$50–150k of cloud + data + one-time LLM compute over ~12 months gets a world-scale v1 plus the
human+AI loop and a scored forward record. That is the "minimal" Ruben is right about.

**You raise a few million to turn the proven edge into a company, not to find the edge:**

| Use | Annual |
|---|---|
| 3–5 data/infra/ML engineers (loaded ~$150–200k each) | ~$0.75–1.0M |
| Compute + storage at continuous full scale | ~$0.2–0.4M |
| Premium proprietary feeds (real-time markets, Crunchbase, alt-data, satellite) | ~$0.2–0.5M |
| Founder/ops + buffer | ~$0.3–0.5M |
| **18–24 month runway total** | **~$1.5–3M seed** |

**Sequence that maximizes valuation and minimizes dilution:**
1. Build v1 cheap (single-digit $k one-time, <$1k/mo). Prove the data-layer edge with the ablation.
2. Accumulate the leak-free forward record (cannot be bought or faked; time is the moat).
3. Raise **$2–3M seed** on the back of (a working world-query demo + a scored record + a measured
   edge over raw frontier models). That is a fundable, defensible story.

Raising before the proof means raising to *find* the edge, which is weak and expensive on dilution.
Raising after means raising to *scale* a proven edge, which is strong. Build first. The data layer
is what makes the raise easy.

---

## 9. One-line summary

Build the world-query substrate cheaply now (it is cheap), prove it beats raw Opus on a leak-free
holdout, let the scored record compound, then raise ~$2–3M to scale the proven edge into a company.
The data layer is the moat, the answer to "are we a prompt layer", and the reason any of this is
defensible.

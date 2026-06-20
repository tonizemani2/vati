# DATA_LAYER_PLAN.md

**Status: TO DO. These are committed build items, not options.** Created 2026-06-15.

The data layer is the binding constraint right now. We have pipes but no water: arXiv metadata
is rich (2.77M rows) and almost everything else is a one-shot cross-section, the dependency graph
(17 nodes) and entity index (145) are effectively empty, patents are absent (12KB).

**Root cause:** our acquisition model (keyless + hand-rolled + one-collector-per-source +
snapshot-once) does not match the shape of the data that matters. The high-value global corpora
ship as **bulk dumps on S3 / BigQuery / large flat files**, not polite keyless REST endpoints.
The fix is a policy change: stop writing snapshot collectors, start writing **bulk loaders +
incremental updaters**, and let the cost gate approve metered BigQuery/S3 egress for the handful
of global sources below.

**Where it lands (per CLAUDE.md):** bulk corpus → Parquet in object storage (NOT SQLite). SQLite
holds only the derived signals, series, graph edges, resolved entities, cards.

---

## Current state (measured 2026-06-15)

| Layer | Rows | Verdict |
|---|---|---|
| `papers` (arXiv) | 2.77M | metadata + abstracts only (~600 B/row, no full text); arXiv-skewed, English |
| `series` / `observations` | 717 / 33k | thin derived signals |
| 14 feed `.jsonl` | ~80KB each | one-shot cross-sections, not histories (GDELT = 53KB of a 2.5TB firehose) |
| `google_patents.jsonl` | 12KB | patents absent |
| `entities` / `entity_links` | 145 / 399 | entity index barely exists |
| `graph_nodes` / `graph_edges` | 17 / 16 | dependency graph empty |

---

## Source plan: storage, access, keys, proxies, cost

Storage numbers are estimates. Two figures matter: **raw download** (transient, can delete after
extract) and **kept** (the Parquet/DB working set we actually hold).

### Tier 1 — full-corpus substrate (own it; leading indicators)

| Source | What it fills | Access | Raw download | Kept (Parquet) | Key | Proxy | Cost |
|---|---|---|---|---|---|---|---|
| **OpenAlex** snapshot | research (global, all-field) + **citation graph** + author/institution **entity index** | S3 open snapshot (`s3://openalex`) | ~330GB gz | 150–250GB | none (email "polite pool" optional) | **no** | $0 (free S3) |
| **Google Patents Public Data** | patents (global incl. CN) + citations + CPC + assignee → paper↔patent edges | BigQuery (`patents-public-data`) | query in place, ~3–4TB table | 10–50GB extract | GCP account + auth | **no** | ~$5/TB scanned (1TB/mo free); budget $20–50 for targeted extracts |
| **GLEIF LEI** | global legal-entity IDs (resolution backbone) | open daily file | ~3GB | ~3GB | none | **no** | $0 |
| **UK Companies House** | non-US company registry | free API + bulk product | ~5GB | ~5GB | free API key | **no** | $0 |
| **UN Comtrade / BACI** | physical trade flows → supply-dependency edges + HHI | Comtrade API (keyless preview works) / BACI flat files | BACI ~10–20GB | 10–20GB | free key raises limits | maybe (resi if scraping past preview limits) | $0 |
| **arXiv full text** (optional) | full paper bodies (only if abstracts insufficient) | S3 requester-pays (`s3://arxiv`) | PDFs ~2.7TB / LaTeX src ~1.1TB | keep src not PDF | AWS creds | **no** | requester-pays egress (~$0.09/GB out region-dependent); LaTeX path far cheaper |

### Tier 2 — full-history series (sample, do not hoard raw)

| Source | What it fills | Access | Kept | Key | Proxy | Cost |
|---|---|---|---|---|---|---|
| World Bank / IMF / OECD / Eurostat / FAO / IEA / EIA / BIS / FRED | macro + structural histories (backfill the snapshots) | REST / bulk | <20GB total | mostly none (FRED/EIA free key) | no | $0 |
| **SEC EDGAR** (full XBRL) | US capital/disclosure | bulk + XBRL frames | 20–50GB | none (UA header) | no | $0 |
| Crossref / Semantic Scholar / PubMed-PMC | research breadth + biomed full text | dumps / S2AG / NCBI FTP | Crossref ~200GB gz, PMC OA ~hundreds GB, keep extracts | free polite-pool / S2 key / NCBI key | no | $0 |
| **Markets (the GATE)** Polymarket, Metaculus, Kalshi, Manifold, equity/FX/rates | live price anchors for "already priced" check | APIs | small | some free keys | no | $0 |

### Tier 3 — rolling window + extract events (never hoard raw)

| Source | What it fills | Access | Kept | Key | Proxy | Cost |
|---|---|---|---|---|---|---|
| **GDELT** | global event firehose / conflict / policy signal | BigQuery (`gdelt-bq`) | extracted events only, <10GB | GCP | no | ~$5/TB scanned |
| ACLED / UCDP / V-Dem | conflict + governance | downloads | <5GB | ACLED free key | no | $0 |
| MOFCOM / EUR-Lex / Federal Register | decrees / export controls | keyless (MOFCOM noted) | small | none | maybe (CJK/geo) | $0 |
| ORCID / GH Archive / job postings | talent + labor flow (leading indicator) | dumps / BigQuery | <20GB | none / GCP | no | $0 / BQ scan |
| Non-Western research: SciELO, J-STAGE, ChinaXiv | de-bias from USA/English | scrape / OAI | small | none | **yes for CN** (resi) | $0 |
| CN patents/CNIPA | China filing signal | covered via Google Patents BQ (avoids scraping) | — | — | avoided | — |

---

## Storage totals (plan for)

- **Local SSD working set** (active extracts + DB): ~500GB–1TB.
- **Object-storage bulk archive** (Parquet, the kept corpus): ~500GB without arXiv full text,
  ~1.5–2TB if we keep arXiv LaTeX source. Cloudflare R2 is the natural home (we already use
  Cloudflare; R2 has **no egress fees**), Backblaze B2 as the cheap alternative.
- **Transient download scratch** (delete after extract): peak ~350GB (OpenAlex snapshot).

Rule: never put bulk corpus in `data/foresight.db`. The DB holds derived signals, series, graph
edges, resolved entities, cards. Bulk goes to Parquet in object storage.

## LOCAL DISK SAFETY — 2026-06-17

The Mac must stay as a thin working node, not the lake. As of this checkpoint,
`data/foresight.db` (~5.2GB) is the only large local data file kept hot. The former
`data/corpus/arxiv.parquet` local copy (~1.6GB) was uploaded to S3 and pruned from the laptop; restore
it from `data/_offload_manifest.jsonl` if a local corpus pass needs it.

Operational rules now enforced in code:
- `engine.feeds.collect_all` and `world-state-backfill-observations` refuse to run below the local
  disk guardrail unless explicitly overridden. Default floor is now 85GiB free via
  `PREDICT_FUTURE_MIN_FREE_GB` / `engine.disk_guard.DEFAULT_MIN_FREE_GB`.
- Use `python3 -m engine.cli data-offload --root data --min-size-mb 100` before any bulk run to see
  what can be moved.
- Use `python3 -m engine.cli data-offload --root data --min-size-mb 100 --dest s3://<bucket>/<prefix>`
  for an S3 dry-run plan. It uploads nothing by default.
- Add `--execute` only to upload; add `--delete-local --allow-critical-delete` only after confirming
  the remote copy and deciding a critical local DB/parquet can be removed.
- Use `python3 -m engine.cli data-offload --manifest-status` and `--restore-plan` to inspect uploaded
  objects and get exact restore commands.
- Do not resume broad collection/backfill on the laptop until the offload plan is checked and the
  disk guard shows adequate headroom.

## METACULUS API STATUS — 2026-06-17

`METACULUS_TOKEN` is present locally and authenticated API access to `/api/posts/` works, but the
community forecast aggregates sampled from current open/closed/resolved binary posts are hidden/null.
This matches Metaculus' 2026 API change: community predictions are no longer generally available via
the API and are visible only for a limited set of questions. The collector therefore stores real
Metaculus observations only when `question.aggregations.*.latest/history` exposes a value; otherwise
it writes no forecast rows. Treat this as an API-visibility limitation, not a missing-token problem.

## Proxies — when actually needed

The bulk path mostly does **not** need proxies (official S3/BigQuery/FTP endpoints, no IP
blocking, you authenticate or pay). Proxies (Floxy DC / Evomi resi, verified live 2026-06-03)
are only for: (1) Chinese/geo-blocked sources if we scrape them directly (CNIPA, ChinaXiv,
some CN preprints), (2) Comtrade if we push past the keyless preview rate limit by scraping.
Decodo is dead (407). Avoid CN scraping where Google Patents BQ already carries the data.

## Costs to approve (cost-gate "quick nod" items)

Everything keyless/$0 except:
- **Google Patents + GDELT BigQuery scans:** budget ~$20–50 total for targeted extracts (free
  1TB/month covers a lot if queries are column-pruned and partition-filtered).
- **arXiv full-text egress** (only if we decide we need bodies): use LaTeX source not PDF to cut
  it ~60%; defer until a forecast actually needs full text.
- **Object storage:** R2/B2 a few dollars/month at this scale.

## Build order (highest leverage first)

1. **OpenAlex full snapshot** — one free S3 load fills global research + citation graph + the
   institution/author entity index at once. Un-empties our two weakest tables (`graph_*`,
   `entities`). Start here.
2. **Google Patents (BigQuery)** — biggest absolute gap; global; gives paper→patent dependency
   edges. First metered-spend item.
3. **GLEIF + Companies House** — entity-resolution backbone so all sources merge into one graph.
4. **Comtrade / BACI** — physical supply-dependency edges + HHI concentration.
5. **Backfill the 14 snapshot feeds into real histories** — mechanical, cheap, high ROI.
6. **arXiv full text** — only if abstracts prove insufficient (LaTeX path).

## BUILD LOG — 2026-06-15 (keyless half shipped, one click away)

**One command runs everything:** `uv run python -m engine.feeds.collect_all`
(`--list` shows the registry, `--only <names>` for a subset, `--ingest-only` to re-land into the DB.)

Shipped this pass (all keyless, $0, urllib-only, no new deps, leak-discipline docstrings):
- **engine/feeds/openalex.py** — THE lever + the blind-spot fix. Three LEADING channels per concept:
  works/year, SHARE of world literature (ppm), cross-field DIFFUSION (# fields). 366 obs / 24 series.
  PROOF it catches the early move: deep-learning share 36→118 (2014)→482 (2016)→1,889 (2018)→9,119 ppm
  (2025); diffusion 18→26 fields. The share-acceleration at 2014-16 is exactly what the old
  single-channel detector was blind to.
- **engine/feeds/crossref.py** — works/year for 6 frontier terms (96 obs, leading).
- **engine/feeds/biorxiv.py** — bioRxiv/medRxiv preprints/year (18 obs, leading).
- **engine/feeds/eurostat.py** — EU macro via JSON-stat (141 obs, lag) — de-US-skews the macro pillar.
- **engine/feeds/faostat.py** — FAO crop production via the keyless bulk host (225 obs, lag).
- **engine/feeds/comtrade.py** — critical-commodity import flows, keyless preview (66 obs, lag).
- **engine/feeds/collect_all.py** — the one-click orchestrator (20 keyless feeds → ingest).
- **engine/feeds/ingest.py** — now honors a per-row `metric` (one feed can carry many metrics) + 6
  new FEED_META entries with trust rationales (the GIGO gate).

DB after this pass: sources 602→608, series 717→788, ~912 new observations from the 6 new feeds.

STILL TO DO (need the storage nod / BQ nod): OpenAlex full S3 snapshot (the citation graph + entity
index — the API channels above are the leading-signal layer, the snapshot is the graph layer),
Google Patents BigQuery, GLEIF + Companies House entity backbone, Comtrade/BACI full history.
NOTE: the DB already contains a separate pre-existing OpenAlex per-concept source set + an older
Comtrade per-commodity path — reconcile/dedupe against the new feeds before the snapshot load.

## STORAGE DECISION — RESOLVED 2026-06-15: keep it all AWS

Object store = **AWS S3**, not R2/B2. Bucket: `vaticinus-datalake-405844305300-us-east-1`
(us-east-1, public access blocked). Same region as the public `s3://openalex` bucket, so the
snapshot copy is **server-side and free of transfer**; storage ≈ $0.023/GB/mo (~$16/mo for the
full 710 GB snapshot). All compute stays on AWS too (Athena/Glue serverless, or in-region EC2).

Layout (Hive-style for future Athena/Glue):
```
s3://vaticinus-datalake-405844305300-us-east-1/
  openalex/pulled=2026-06-15/data/{works,authors,institutions,concepts,topics,...}/   # frozen raw snapshot
  openalex/derived/openalex_concept_index.jsonl                                        # derived artifacts
```

### AWS BUILD LOG — 2026-06-15
- **Bucket provisioned**, public access blocked.
- **Snapshot sync RUNNING** (server-side, in-region): entity index (authors 70GB + small dirs) +
  works/ (639GB citation graph) → `openalex/pulled=2026-06-15/`. Frozen dated vintage = leak-safe
  (OpenAlex overwrites its public bucket monthly).
- **engine/feeds/openalex_snapshot.py** — the all-AWS derive loop (read raw gz from S3 via the `aws`
  CLI, parse with stdlib, write derived back to S3; no boto3 dep). RAN on concepts+topics →
  **69,542-entity global concept index** (levels L0–L5, with per-year counts), landed locally +
  `s3://.../openalex/derived/`. Entity index went 145 → ~70k.

### CITATION GRAPH — DONE 2026-06-15 (all-AWS, Athena)
- **engine/feeds/athena.py** — thin Athena runner (aws-CLI subprocess, no boto3; logs GB scanned).
- Glue DB `vaticinus` + external table `openalex_works` over `s3://openalex/data/works/` (JsonSerDe).
- **CTAS → `citation_edges` Parquet** at `s3://.../openalex/derived/citation_edges/` partitioned by
  citing_year. ONE 639 GB scan = **$3.20** (logged). Result: **3,000,604,635 citation edges** (35 GB
  Parquet), queryable via Athena forever. Aggregates over it are ~free (Parquet stats).
- Derived **citations-made-per-year** series → DB (`openalex_citations`, 36 obs; 2025 ≈ 228M edges/yr).
- ARCHITECTURE NOTE: `graph_edges` is the hand-curated SUPPLY-dependency graph (`depends_on`), a
  different object — citation edges do NOT go there. The citation graph lives as Parquet on S3; the
  DB gets derived signals only (per CLAUDE.md: bulk→object store, SQLite→derived).

### LEADING CHANNELS — DONE 2026-06-15 (the recall lever the goal named)
- **work_attrs** Parquet (CTAS, one 639GB scan = $3.2): id → field + official `counts_by_year`.
- **Channel 1 — citation velocity by field** (`openalex_cite_velocity`, 364 obs): OFFICIAL
  counts_by_year by field-year, CLEAN of the spam (see below). Live read: Energy citations +2.30x,
  Environmental +1.89x, Engineering +1.87x (2018→2024). Rising slope leads commercialization.
- **Channel 2 — cross-field bridge** (`openalex_bridge`, 364 obs): per-field fraction of outgoing
  citations crossing into another field = the structural-hole signal. Bridges: decision-sciences /
  pharmacology / nursing (0.70). Insular: physics / medicine (0.26).
- DB: series 789→841, sources →610. All derived via cheap Athena scans (<$0.20 total) over the Parquet.

### DATA-QUALITY FINDING (GIGO gate) — OpenAlex spam cluster
Reconstructing citations from raw `referenced_works` is contaminated: a fusion-physics (LHD) cluster
shows ~1.3M edges vs an official `cited_by_count` of 8 — ~1.3M near-duplicate recently-ingested
records (W695… ids) citing it. NORMAL works are accurate (ResNet edges 213k vs official 221k; AlexNet
75.6k vs 75.7k). FIX APPLIED: citation velocity uses OpenAlex's official de-spammed `counts_by_year`,
not the raw edge list. The raw `citation_edges` Parquet is kept (valid for normal works); a despam
anti-join (edge-count >> official) is the follow-up before any structural-centrality use.

### AI BACKEND CONNECTION — DONE 2026-06-15 (the keystone)
The data layer was inert until the forecaster could use it. Built the seam:
- **engine/signals.py** — `evidence_pack(topic)` resolves a free-text topic/question to the relevant
  LEADING signals across ALL channels (sub-topic share, cross-field diffusion, citation velocity,
  talent inflow, works/preprint volume, patent HHI + leaders, trade) with dated trend stats (CAGR,
  accel) + the detector verdict (FIRED / σ / FDR-survived). `format_pack()` renders a compact,
  LLM-readable context block. Honest: empty pack says "none found, forecast from first principles".
- **engine/chat_bridge.py `signals` command** — the shell-out seam the AI backend calls:
  `echo '{"question":"..."}' | python -m engine.chat_bridge signals` → `{ok, context, series, patents}`.
  Verified: "deep learning" surfaces the takeoff through every channel (works +51%/yr, share
  36→9,119 ppm, diffusion 18→26 fields, frontier-compute 1350σ); "solid state battery" unifies
  Crossref + patents (HHI 118, Toyota/Panasonic) + citation velocity + talent + SEC mentions.
- WIRING NOTE: this grounds the PYTHON forecasters (forecastbench / metaculus deep-research council —
  the SCORED backend, which has foresight.db access). The edge chat app is card-only-by-decision and
  uses Neon, NOT the SQLite lake, so it would need a companion endpoint to call this seam — flagged,
  not built (respects that prior separation).
- HARDENED + TESTED 2026-06-15: whole-token matching (no substring noise: "a"/""/gibberish → empty,
  honest pack), slug-length guard, relevance cap (12) + leading-channel ordering, adaptive precision
  for small fractions. First-class CLI verb `engine.cli signals "<topic>" [--json]`. Regression suite
  `engine/test_signals.py` (16 invariants, ALL GREEN) guards the contract. END-TO-END LOOP PROVEN:
  `cli signals` → pack (e.g. SSB patents base 9,361, +30%/yr, 24.2σ) → grounded Fermi spec →
  `chat_bridge forecast` → P=0.103, median 12,013, 80% CI [9.6k,15k]. The probability falls out of the
  engine anchored to the measured series, not LLM guessing.

### LOADED THIS PASS
- **Patents → 18 global topics** (added humanoid robotics, gene therapy, mRNA, photonic computing,
  carbon capture, green hydrogen, fusion, GLP-1, autonomous driving, grid storage, wide-bandgap power,
  neuromorphic). 12×37.8 GB BigQuery = within the 1 TB/mo free tier = $0. Extract on S3 `patents/`.
- **World Bank → 24-country global basket** (G20 + key emerging; was US/CHN/WLD only).

### DEFERRED (with reasons — not skipped)
- **Talent-inflow from authors/**: the OpenAlex `authors` entity has EMPTY `topics` (scanned ~110k
  objects, none field-tagged), so field-level talent needs a works-authorship scan (639 GB) with
  distinct-author dedup. Deferred to that dedicated scan rather than a weak proxy. (NOTE: a
  `talent_inflow` series already exists in the DB from prior work and shows in packs.)
- **Despam `citation_edges`**: needs an official-count join (expensive 639 GB) and only matters for
  structural-centrality; citation VELOCITY already uses clean official `counts_by_year`. Deferred.

### NEXT (all-AWS, no GCP)
- Wire `evidence_pack` into the forecastbench / metaculus prompt assembly (ground the scored forecasts).
- The two deferred scans above, when a use case needs them. Google Patents Public Data lives ONLY on BigQuery (GCP). To
  keep it all-AWS we must use **USPTO bulk XML** (bulkdata.uspto.gov, keyless) → S3 → Athena, which
  is **US-only** (loses global incl. CN). Decision needed: accept US-only patents to stay all-AWS,
  OR allow one GCP touch for global Google Patents. (Everything else is already AWS-native.)
- arXiv full text is also on AWS S3 (`s3://arxiv`, requester-pays) — defer until a forecast needs bodies.

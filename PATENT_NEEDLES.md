# Patent-channel needles — session 2026-06-13

The original /needle mission: read patents + research for **niche, early, structurally-capped
booms** that are not yet priced. This session wired the patent channel and used it to surface and
gate real pre-consensus calls. Nothing here is promoted to a ForecastCard — promotion is Ruben's call.

## What is wired

- **`engine/feeds/google_patents.py`** — drives Google Patents Public Data on BigQuery
  (`patents-public-data.patents.publications`) through the authenticated `bq` CLI (no python dep).
- Auth: account `tonizemani921@gmail.com`, project **`credible-flag-378011`** (BigQuery API enabled).
  gcloud config persists, so a later session works without re-auth until the token expires
  (`gcloud auth login` to refresh).
- **Cost gate:** every query is dry-run-priced first; a run aborts above `--max-gb` (default 40).
  Free tier = 1000 GB scanned / month. This session scanned ~170 GB (feed runs logged to
  `data/_collect_logs/google_patents_cost.log`; direct discovery queries unlogged). A topic run ≈ 38 GB; a
  CPC-discovery scan ≈ 16–20 GB.

### Run it on a topic (confirmation)
```
uv run python -m engine.feeds.google_patents \
  --label "<thesis>" --terms "term1,term2,term3" --since 2014 --until 2026 --topn 25
```
Emits assignee concentration (HHI + top-N) + grant-year trend to `data/feeds/google_patents.jsonl`.

## The instrument is validated

It discriminates **IP-moats from manufacturing/trade-secret moats**:

| Field | HHI | Top-5 | #1 player | Cap type |
|---|---|---|---|---|
| Spatial transcriptomics | 1177 | 59% | 10x Genomics | IP moat |
| Cryo-infrastructure | 209 | 22% | Sumitomo (cryocoolers) | manufacturing / trade-secret |
| Ferroelectric memory | ~3735 (H10B51) | — | TSMC 38% | IP + foundry capability |

**Recurring lesson:** patent assignee-concentration measures IP moats well but MISSES
manufacturing/integration moats (Bluefors runs the cryo market on 7 patents; TSMC's ferroelectric
lead may be partly defensive). So **falsifiers should track shipping / capacity, not patent counts.**

## Discovery scan (the "find the next big thing" instrument)

CPC main-group, US primary-CPC, grants 2024-26 vs 2018-21. Two-factor screen (accelerating AND
concentrated) collapses onto emerging non-volatile memory:

| CPC | field | accel | HHI | read |
|---|---|---|---|---|
| **H10B51** | **ferroelectric memory (FeRAM)** | **4.66x** | **3735** | the needle |
| H10B53 | ferroelectric memory (FeFET) | 1.97x | 1629 | reinforces |
| H10B20 | emerging memory (MRAM/PCM-class) | 3.05x | 1378 | candidate, pre-consensus |
| H10B12 | DRAM | 2.03x | 1186 | the known HBM/AI supercycle (priced) |
| A43B11 | footwear lacing | 2.27x | 2893 | single-filer surge (Nike/BOA), not structural |
| H10K59 | OLED display | 1.46x | 1732 | mature / priced |
| B60L55 | vehicle-to-grid charging | 1.75x | 768 | DROPPED: saturation 0.72 (priced) |

Saturation gate ($0): ferroelectric 0.20–0.37, MRAM 0.24, phase-change 0.22 (all obscure /
pre-consensus); V2G 0.72 (priced, dropped).

## Gated calls now tracked (hypotheses, NOT cards)

1. **Cryo-infrastructure** `121c2fdf` — constraint_migration / layer_blindness, horizon 2028.
   Consensus prices the qubit race on count/fidelity; the binding constraint migrates to the cryo
   stack (cryocoolers / dilution fridges / He-3). Clean pre-consensus (sat 0.18, 0 forecasters).
   Skeptic panel 1/5 refute → SURVIVED. Patent read: Sumitomo = cryocooler chokepoint; Bluefors cap
   is manufacturing not IP. **Falsifier to tighten:** track fridge lead-times, not patent counts
   (He-3 leg weakened by closed-cycle recycling).

2. **Ferroelectric (HfO2) memory** `33925325` — constraint_migration / layer_blindness, horizon 2028.
   Consensus prices the AI-memory bottleneck as HBM/DRAM; the pre-consensus migration is to
   doped-HfO2 ferroelectric compute-in-memory, with rent at the foundry (TSMC 38%) + startups
   (Kepler Computing 8.3%, a pre-revenue firm out-filing Intel/IBM). PARTLY-priced (consensus-eye
   1 forecaster / 3 broad). Skeptic panel 2/5 refute → SURVIVED. Soft spot: the cap is integration
   capability, not a raw-material chokepoint (hafnium volumes are atomic-layer-tiny).

## Next candidates to gate (for a later session)

- **H10B20 emerging memory** (MRAM / phase-change class) — accel 3.05x, HHI 1378, pre-consensus.
  Confirm the exact CPC label, then run concentration + decompose the inelastic input.
- The broader **emerging-NVM cluster** (ferroelectric + MRAM + PCM) as a single structural call:
  the post-DRAM/NAND memory layer, foundry-captured.
- Re-run discovery with a LOWER HHI floor to catch manufacturing-moat fields (the cryo blind spot
  of the concentration screen), and add a citation pull to start filling the dependency graph
  (`graph_nodes` ~17).

## Resume command (paste into a clean session)

```
/needle Resume the patent-discovery thread (see PATENT_NEEDLES.md). The google_patents BigQuery feed
is wired (engine/feeds/google_patents.py; bq CLI; project credible-flag-378011; dry-run gated,
1000 GB/mo free tier). Two gated hypotheses already stand: cryo-infrastructure 121c2fdf and
ferroelectric-HfO2-memory 33925325. Run the CPC acceleration+HHI discovery query to mint MORE
structurally-capped, accelerating, pre-consensus candidates (lower the HHI floor to catch
manufacturing-moat fields the concentration screen misses); gate each survivor with saturation-topic
+ consensus-eye; decompose to the inelastic input; author survivors as gated hypotheses. Then
gate H10B20 (emerging memory) which is already queued. Do not promote to cards.
```

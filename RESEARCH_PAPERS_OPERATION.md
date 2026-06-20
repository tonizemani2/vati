# RESEARCH_PAPERS_OPERATION.md

Status: started 2026-06-18 as the `research_papers_global_lake` operation.

Goal: one worldwide research-paper lake for forecasting. The lake should hold global metadata for
everything we can legally/indexably cover, and full text where official access and license permit.
The Mac is only the control node. Bulk data goes to object storage.

## Non-negotiables

- Do not use Floxy for sources with official bulk/API access. arXiv, OpenAlex, PubMed/PMC,
  Crossref, and Semantic Scholar have official paths.
- Do not put bulk corpora into `data/foresight.db`. SQLite holds derived signals, entities, graph
  edges, extraction rows, and cards.
- Do not download multi-TB corpora onto the Mac. Use object storage plus cloud/remote workers.
- Do not start requester-pays, paid snapshots, BigQuery, or LLM extraction without a named budget.
- Store source, license, fetch time, content hash, and canonical IDs for every raw/full-text object.
- Prefer structured source/XML/LaTeX over PDF text extraction; OCR only when the document is scanned
  or has unusable embedded text.

## Current command

Safe bootstrap:

```bash
uv run python -m engine.cli research-papers-operation
```

Machine-readable manifest:

```bash
uv run python -m engine.cli research-papers-operation --json
```

The command writes:

```text
data/research_papers/operation_manifest.json
data/research_papers/run_log.jsonl
```

It downloads no bulk bytes. It records local DB coverage, source plans, rough scale, and blockers.

## Source plan

| Source | Role | Full text posture | Recurrence |
|---|---|---|---|
| OpenAlex | Global metadata, authors, institutions, citations, topics | Metadata/graph, not full text | Snapshot/incremental partitions |
| Crossref | DOI publisher metadata | Metadata and abstracts where allowed | REST plus monthly snapshot if paid |
| PubMed | Biomed citation metadata | Metadata/abstracts | Annual baseline plus daily updates |
| PMC OA | Biomed full text | OA XML/text/PDF by license | Baseline plus daily incrementals |
| Semantic Scholar S2AG | Metadata/citation enrichment | Metadata; S2ORC where available | Monthly releases |
| arXiv metadata | Preprint metadata/abstracts | Already in local `papers` table | OAI harvest |
| arXiv full text | Preprint PDFs/source | Official requester-pays S3, remote-only | Manifest-driven monthly growth |
| Regional OA/preprints | Non-Western and industry blind-spot coverage | Mixed by source/license | Source-specific |

## Execution shape

1. Bootstrap manifest locally.
2. Pick/confirm the remote prefix, e.g. `s3://vaticinus-datalake-405844305300-us-east-1/research-papers/`.
3. Inventory official source manifests remotely.
4. Mirror metadata/full-text shards to object storage.
5. Convert to partitioned Parquet plus raw content-hash objects.
6. Run cheap extractors into structured rows: entities, concepts, claims, numbers, dates,
   relationships, license/provenance.
7. Auto-mint derived signals into `data/foresight.db`.
8. Query via metadata filters + graph/signals + vector snippets + on-demand full text.

## EC2 path

Use EC2 for full-text mirroring and extraction. Keep it in `us-east-1` so it is close to the public
OpenAlex/arXiv S3 buckets.

Safe launch sequence:

1. Manifest inventory worker: copy official source manifests/file lists only.
2. One-shard pilot: one arXiv month/source shard plus one PMC OA package, then validate extracted
   rows and text quality.
3. Full backfill: only after pilot metrics and budget are accepted.

Recommended posture:

- Pilot: `c7i.large` / `c7g.large`, 1-3 hours, single-digit dollars excluding storage.
- Backfill: `c7i.2xlarge` / `r7i.2xlarge` or larger, with remote scratch/object storage.
- Do not attach a giant EBS volume unless the job explicitly needs local scratch; stream S3 to S3
  and write Parquet/raw outputs back to the lake.

The current command records an EC2 worker plan but does not launch. Launching paid compute still
requires a named dollar cap.

## Pilot run — 2026-06-18

Run id: `pilot-20260618T122753Z`

Instance: `i-0eddf977930ebfcf0`, `c7i.large`, `us-east-1`; terminated itself after completion.

Lake output:

```text
s3://vaticinus-datalake-405844305300-us-east-1/research-papers/
```

Artifacts written: 18 objects, 10.5 MiB total.

What worked:

- OpenAlex works/authors/institutions manifests copied.
- arXiv PDF and source manifests copied from official requester-pays S3.
- One bounded arXiv source shard selected: `src/arXiv_src_9107_001.tar`.
- Two sample source packages extracted and text-probed.
- PubMed updatefiles index copied.

Findings:

- EC2 + SSM + instance profile + S3 lake write path works.
- arXiv source archives are usable for text-first extraction; source contains TeX-like text, so OCR
  should remain a last resort.
- The old PMC `oa_file_list.csv` top-level URL now returns 404. The current file list is under
  `https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_file_list.csv` and is large, so future pilots
  should range-read or stream it.
- The first user-data attempt tried to install `curl` and hit an Amazon Linux package conflict; the
  worker now skips package installation when tools already exist.

## What "all papers" means

"All" means maximum lawful/official coverage. For paywalled publisher full text, store metadata,
identifiers, citations, links, and rights status; do not ingest or redistribute full text unless a
license grants that right. For OA/preprint/full-text official bulk sources, store the full object.

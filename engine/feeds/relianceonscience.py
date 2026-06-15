"""Paper -> patent linkage: the clean, OpenAlex-native commercialization overlay on our concepts.

WHY. The data plan named paper->patent linkage as a missing lever. Google Patents BQ only exposes raw
`citation.npl_text` free-text (fuzzy-matching that to OpenAlex = GIGO, the constitution's #1 sin), so the
clean source is the Marx & Fuegi "Reliance on Science" dataset (Zenodo 11461587, 2024-06-03). Its
`_pcs_oa.csv` is the WORLDWIDE patent->paper citation list (US/EP/CN/KR/WO, ~tens of millions of rows),
and its `oaid` column is simply the OpenAlex work-id integer (Wid = 'W' || oaid) -- so it joins to our
existing `work_primary_concept` Parquet with NO fuzzy match and NO id map. That gives, per OpenAlex
concept, how many distinct patents worldwide cite that concept's research = a measured paper->patent
RELIANCE / commercialization-intensity signal onto the exact concept nodes our dependency graph uses.

This is the "all patents" coverage Ruben asked for: the broad CITATION set (not the narrow 548k
patent-paper PAIRS), worldwide, every patent that draws on a cited paper.

PIPELINE (all-AWS, mirrors openalex_load):
  1. prepare  -- gzip the local _pcs_oa.csv, upload to s3://.../relianceonscience/pcs/, CREATE the
     Athena external table. (download is keyless/$0 from Zenodo; gzip cuts the scan ~3x.)
  2. build    -- Athena JOIN reliance_pcs.oaid -> work_primary_concept (primary concept per paper),
     GROUP BY concept: distinct patents, US vs non-US, applicant-cited (inventor-chosen, the stronger
     reliance) vs examiner-added. Lands data/feeds/openalex_concept_patents.jsonl (the derived signal
     signals.py reads) + the same as Parquet on S3. COST: ~$0.01-0.05 over gzip CSV + slim Parquet,
     logged to athena_cost.log; >$0 so cost-gated (a few cents, far under a nod).

HONEST CAVEATS carried downstream: (1) attribution uses each paper's PRIMARY concept (consistent with
how concept_flow was built) -- multi-concept reliance is undercounted. (2) Reliance-on-Science is
front-page + in-text citations through 2023; newer patents are absent. (3) examiner citations are
weaker reliance than applicant citations -- we keep both but report applicant separately.

LEAK DISCIPLINE: a citation is dated by the citing patent, which post-dates the paper -- this is a
backward-looking reliance measure (what has been commercialized), never a forward leak into a score.

USAGE
  uv run python -m engine.feeds.relianceonscience --prepare   # gzip+upload+create table
  uv run python -m engine.feeds.relianceonscience --build     # run the join, land the signal
  uv run python -m engine.feeds.relianceonscience --prepare --build
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from engine.feeds import athena

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "data" / "_scratch"
PCS_LOCAL = SCRATCH / "pcs_oa.csv"
OUT_JSONL = ROOT / "data" / "feeds" / "openalex_concept_patents.jsonl"
COST_LOG = ROOT / "data" / "_collect_logs" / "athena_cost.log"

BUCKET = athena.BUCKET
PCS_S3 = f"s3://{BUCKET}/relianceonscience/pcs/"
RELIANCE_S3 = f"s3://{BUCKET}/openalex/derived/concept_patent_reliance/"
MIN_PATENTS = 5  # keep a concept only if >=5 distinct patents cite it (drops noise, slims the artifact)


def _sh(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {proc.stderr.strip()[:300]}")


def prepare(log=print) -> None:
    """gzip the local PCS file, upload to S3, (re)create the Athena external table over it."""
    if not PCS_LOCAL.exists():
        raise SystemExit(f"missing {PCS_LOCAL} -- download _pcs_oa.csv from Zenodo 11461587 first")
    gz = Path(str(PCS_LOCAL) + ".gz")
    if not gz.exists():
        log(f"  gzip {PCS_LOCAL.name} (cuts the Athena scan ~3x) ...")
        _sh(["bash", "-c", f"gzip -c {PCS_LOCAL} > {gz}"])
    log(f"  upload {gz.name} -> {PCS_S3} ...")
    _sh(["aws", "s3", "cp", str(gz), PCS_S3, "--only-show-errors"])
    log("  [athena] (re)create external table reliance_pcs ...")
    athena.run_query("DROP TABLE IF EXISTS vaticinus.reliance_pcs", log=log)
    athena.run_query(
        "CREATE EXTERNAL TABLE vaticinus.reliance_pcs ("
        "  reftype string, confscore int, oaid string, patent string,"
        "  uspto int, wherefound string, self string)"
        " ROW FORMAT DELIMITED FIELDS TERMINATED BY ','"
        " STORED AS TEXTFILE"
        f" LOCATION '{PCS_S3}'"
        " TBLPROPERTIES ('skip.header.line.count'='1')", log=log)


def _paginate(qid: str) -> list[list[str]]:
    rows, token, first = [], None, True
    while True:
        args = ["athena", "get-query-results", "--query-execution-id", qid, "--max-items", "1000"]
        if token:
            args += ["--starting-token", token]
        res = athena._aws(args)
        page = res.get("ResultSet", {}).get("Rows", [])
        if first and page:
            page = page[1:]
            first = False
        for r in page:
            rows.append([c.get("VarCharValue", "") for c in r.get("Data", [])])
        token = res.get("NextToken")
        if not token:
            break
    return rows


def build(log=print) -> dict:
    """JOIN the worldwide citation list to each paper's primary concept; land per-concept reliance."""
    sql = f"""
    SELECT regexp_replace(w.concept_id, '.*/', '') AS cid,
           max(w.concept_name) AS cname,
           count(distinct p.patent) AS n_patents,
           count(distinct if(split_part(p.patent,'-',1)='us', p.patent)) AS n_us,
           count(distinct if(p.reftype='app', p.patent)) AS n_applicant
    FROM reliance_pcs p
    JOIN work_primary_concept w
      ON w.work_id = concat('https://openalex.org/W', p.oaid)
    GROUP BY regexp_replace(w.concept_id, '.*/', '')
    HAVING count(distinct p.patent) >= {MIN_PATENTS}
    """
    log("  [athena] join worldwide patent citations -> concept (primary) ...")
    res = athena.run_query(sql, log=log)
    rows = _paginate(res["id"])
    pulled = date.today().isoformat()
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for cid, cname, n_pat, n_us, n_app in rows:
            try:
                n_pat, n_us, n_app = int(n_pat), int(n_us), int(n_app)
            except (TypeError, ValueError):
                continue
            rec = {"cid": cid, "name": cname, "n_patents": n_pat, "n_us": n_us,
                   "n_nonus": n_pat - n_us, "n_applicant": n_app, "pulled": pulled}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    # also push the derived artifact to the S3 lake (bulk/derived -> object store, per CLAUDE.md)
    try:
        _sh(["aws", "s3", "cp", str(OUT_JSONL), RELIANCE_S3 + f"pulled={pulled}/concept_patent_reliance.jsonl",
             "--only-show-errors"])
    except RuntimeError as e:
        log(f"  ! S3 upload of derived artifact failed (kept locally): {e}")
    log(f"  concept_patent_reliance: {n:,} concepts (>= {MIN_PATENTS} patents), scanned "
        f"{res['gb']:.2f} GB (~${res['gb']/1000*5:.3f}) -> {OUT_JSONL.name}")
    return {"concepts": n, "gb": res["gb"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prepare", action="store_true", help="gzip+upload PCS + create Athena table")
    ap.add_argument("--build", action="store_true", help="run the join, land the per-concept reliance signal")
    a = ap.parse_args()
    if not (a.prepare or a.build):
        ap.error("pick --prepare and/or --build")
    if a.prepare:
        prepare()
    if a.build:
        build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

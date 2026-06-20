"""OpenAlex SNAPSHOT processor — the all-AWS derive loop (read raw from S3 → derive → write to S3).

WHY (2026-06-15). The keyless OpenAlex *API* collector (engine/feeds/openalex.py) mints leading
signals for a handful of watched concepts. This module is the other half: it processes the full
OpenAlex SNAPSHOT we froze into our own S3 bucket (a dated, leak-safe copy — OpenAlex overwrites
its public bucket monthly). Everything stays on AWS: raw gz lives in S3, we stream each entity
file down with the `aws` CLI (no boto3 dep, matching the repo's shell-out style in
google_patents.py), parse it with stdlib gzip+json, and write the DERIVED artifact back to S3
(+ a local jsonl for the DB).

WHAT IT DERIVES NOW (the small entity dirs — feasible without EC2):
  • concepts + topics → the GLOBAL CONCEPT INDEX: {id, name, level, works_count, cited_by_count}
    plus per-year counts (counts_by_year) = a dated structural signal of where research mass sits.
    This is tier-2 of the 3-tier data plan ("fine concept/actor index").

WHAT NEEDS EC2/ATHENA (the big dirs — see DATA_LAYER_PLAN.md):
  • works/ (639 GB) holds `referenced_works` = the CITATION GRAPH. Parsing it is an Athena CTAS
    (serverless, all-AWS, ~$5/TB scanned) or an EC2 in-region job, NOT a laptop job.
  • authors/ (70 GB) → talent/affiliation flows.

LEAK DISCIPLINE: `counts_by_year` carries the real year; we tag each derived row with the snapshot
pull date so a frozen vintage is reproducible. Nothing is interpolated.

USAGE
  uv run python -m engine.feeds.openalex_snapshot --entity concepts --limit-files 1   # smoke
  uv run python -m engine.feeds.openalex_snapshot --entity concepts topics            # full index
  # reads s3://openalex/data by default; --src can point at our frozen copy.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BUCKET = "vaticinus-datalake-405844305300-us-east-1"
DEFAULT_SRC = "s3://openalex/data"                       # public, in-region (free to read)
DERIVED_S3 = f"s3://{BUCKET}/openalex/derived"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "feeds"
PULL_DATE = "2026-06-15"


def _s3_ls_gz(src_prefix: str) -> list[str]:
    """List the .gz part files under an S3 entity prefix (full s3:// keys)."""
    proc = subprocess.run(["aws", "s3", "ls", src_prefix + "/", "--recursive"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"s3 ls failed: {proc.stderr.strip()}")
    bucket = src_prefix.split("/")[2]
    keys = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[-1].endswith(".gz"):
            keys.append(f"s3://{bucket}/{parts[-1]}")
    return keys


def _stream_objects(s3_key: str):
    """aws s3 cp the gz to a temp file, yield each JSON object, delete. Dependency-free."""
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=True) as tf:
        proc = subprocess.run(["aws", "s3", "cp", s3_key, tf.name, "--only-show-errors"],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"s3 cp failed for {s3_key}: {proc.stderr.strip()}")
        with gzip.open(tf.name, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue


def derive_concept_index(entities: list[str], src: str, limit_files: int | None, *, log=print) -> Path:
    """Build the global concept/topic index from the snapshot's small entity dirs."""
    out_path = OUT_DIR / "openalex_concept_index.jsonl"
    n = 0
    with out_path.open("w", encoding="utf-8") as out:
        for entity in entities:
            keys = _s3_ls_gz(f"{src}/{entity}")
            if limit_files:
                keys = keys[:limit_files]
            log(f"{entity}: {len(keys)} part file(s)")
            for k in keys:
                for o in _stream_objects(k):
                    cid = (o.get("id") or "").split("/")[-1]
                    if not cid:
                        continue
                    row = {
                        "entity": entity,
                        "id": cid,
                        "name": o.get("display_name"),
                        "level": o.get("level"),
                        "works_count": o.get("works_count"),
                        "cited_by_count": o.get("cited_by_count"),
                        "counts_by_year": {str(c["year"]): c.get("works_count")
                                           for c in (o.get("counts_by_year") or [])},
                        "pulled": PULL_DATE,
                    }
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
                log(f"  + {k.split('/')[-1]}  (running total {n})")
    log(f"\nwrote {n} index rows → {out_path}")
    return out_path


def _upload_derived(local: Path, *, log=print) -> None:
    dst = f"{DERIVED_S3}/{local.name}"
    proc = subprocess.run(["aws", "s3", "cp", str(local), dst, "--only-show-errors"],
                          capture_output=True, text=True)
    if proc.returncode == 0:
        log(f"uploaded derived → {dst}")
    else:
        log(f"! derived upload failed: {proc.stderr.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", nargs="+", default=["concepts"],
                    help="entity dirs to index (concepts topics ...)")
    ap.add_argument("--src", default=DEFAULT_SRC, help="S3 prefix of the snapshot data dir")
    ap.add_argument("--limit-files", type=int, default=None, help="cap part files per entity (smoke)")
    ap.add_argument("--no-upload", action="store_true", help="skip pushing derived back to S3")
    a = ap.parse_args()

    out = derive_concept_index(a.entity, a.src, a.limit_files)
    if not a.no_upload:
        _upload_derived(out)
    # quick shape report
    rows = [json.loads(l) for l in out.open(encoding="utf-8")]
    if rows:
        by_level: dict = {}
        for r in rows:
            by_level[r.get("level")] = by_level.get(r.get("level"), 0) + 1
        print(f"\nindexed {len(rows)} entities; by level: "
              + ", ".join(f"L{k}:{v}" for k, v in sorted(by_level.items(), key=lambda x: (x[0] is None, x[0]))))
        top = sorted(rows, key=lambda r: r.get("works_count") or 0, reverse=True)[:5]
        print("top by works_count: " + "; ".join(f"{r['name']} ({r['works_count']})" for r in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())

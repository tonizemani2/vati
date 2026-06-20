#!/bin/bash
set -Eeuo pipefail

export AWS_EC2_METADATA_DISABLED=false
REGION="${REGION:-us-east-1}"
LAKE_PREFIX="${LAKE_PREFIX:-s3://vaticinus-datalake-405844305300-us-east-1/research-papers}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
WORK="${WORK:-/mnt/research-papers-pilot}"
LOG="/var/log/research-papers-pilot.log"
MAX_ARXIV_TAR_MB="${MAX_ARXIV_TAR_MB:-700}"
DOWNLOAD_ARXIV_SHARD="${DOWNLOAD_ARXIV_SHARD:-1}"
MAX_RUNTIME_SECONDS="${MAX_RUNTIME_SECONDS:-7200}"
export REGION LAKE_PREFIX RUN_ID WORK MAX_ARXIV_TAR_MB DOWNLOAD_ARXIV_SHARD MAX_RUNTIME_SECONDS

mkdir -p "$WORK"/{manifests,pilot,logs}
exec > >(tee -a "$LOG") 2>&1

echo "research papers EC2 pilot starting"
date -u +"%Y-%m-%dT%H:%M:%SZ"
echo "run_id=$RUN_ID"
echo "lake_prefix=$LAKE_PREFIX"
echo "region=$REGION"

upload_logs() {
  set +e
  cp "$LOG" "$WORK/logs/research-papers-pilot.log" 2>/dev/null
  aws s3 cp "$WORK/logs/" "$LAKE_PREFIX/runs/$RUN_ID/logs/" --recursive --region "$REGION" --only-show-errors >/dev/null 2>&1
  set -e
}
trap upload_logs EXIT

(
  sleep "$MAX_RUNTIME_SECONDS"
  echo "watchdog reached ${MAX_RUNTIME_SECONDS}s; shutting down"
  upload_logs || true
  shutdown -h now
) &

missing_packages=()
command -v aws >/dev/null 2>&1 || missing_packages+=(awscli)
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
command -v tar >/dev/null 2>&1 || missing_packages+=(tar)
command -v gzip >/dev/null 2>&1 || missing_packages+=(gzip)
command -v find >/dev/null 2>&1 || missing_packages+=(findutils)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl-minimal)

if command -v dnf >/dev/null 2>&1 && [[ "${#missing_packages[@]}" -gt 0 ]]; then
  dnf install -y "${missing_packages[@]}" >/dev/null
fi

aws sts get-caller-identity --region "$REGION" > "$WORK/pilot/caller_identity.json"
python3 - <<'PY' > "$WORK/pilot/run_info.json"
import json, os, platform, time
print(json.dumps({
    "run_id": os.environ.get("RUN_ID"),
    "lake_prefix": os.environ.get("LAKE_PREFIX"),
    "region": os.environ.get("REGION"),
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host": platform.node(),
    "python": platform.python_version(),
}, sort_keys=True))
PY

echo "copying official manifests"
aws s3 cp s3://openalex/data/works/manifest "$WORK/manifests/openalex_works_manifest.json" \
  --no-sign-request --region "$REGION" --only-show-errors
aws s3 cp s3://openalex/data/authors/manifest "$WORK/manifests/openalex_authors_manifest.json" \
  --no-sign-request --region "$REGION" --only-show-errors || true
aws s3 cp s3://openalex/data/institutions/manifest "$WORK/manifests/openalex_institutions_manifest.json" \
  --no-sign-request --region "$REGION" --only-show-errors || true

aws s3 cp s3://arxiv/pdf/arXiv_pdf_manifest.xml "$WORK/manifests/arxiv_pdf_manifest.xml" \
  --request-payer requester --region "$REGION" --only-show-errors
aws s3 cp s3://arxiv/src/arXiv_src_manifest.xml "$WORK/manifests/arxiv_src_manifest.xml" \
  --request-payer requester --region "$REGION" --only-show-errors || true

curl -fsSL --max-time 120 https://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/ \
  -o "$WORK/manifests/pubmed_updatefiles_index.html" || true
curl -fsSL --max-time 120 -r 0-1048575 https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_file_list.csv \
  -o "$WORK/manifests/pmc_oa_file_list_head.csv" || true

python3 - <<'PY' "$WORK/manifests" > "$WORK/pilot/manifest_summary.json"
import csv, json, os, sys, xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1])
summary = {"files": {}, "arxiv_source_candidate": None, "pmc_oa_candidate": None}
for p in sorted(root.glob("*")):
    summary["files"][p.name] = {"bytes": p.stat().st_size}

src_manifest = root / "arxiv_src_manifest.xml"
if src_manifest.exists() and src_manifest.stat().st_size:
    tree = ET.parse(src_manifest)
    candidates = []
    for file_el in tree.findall(".//file"):
        filename = (file_el.findtext("filename") or "").strip()
        size_text = (file_el.findtext("size") or "0").strip()
        try:
            size = int(size_text)
        except ValueError:
            size = 0
        if filename.startswith("src/") and size:
            candidates.append((size, filename))
    max_bytes = int(float(os.environ.get("MAX_ARXIV_TAR_MB", "700")) * 1024 * 1024)
    under = [(size, name) for size, name in candidates if size <= max_bytes]
    if under:
        size, name = sorted(under)[0]
        summary["arxiv_source_candidate"] = {"filename": name, "size_bytes": size}

pmc_head = root / "pmc_oa_file_list_head.csv"
if pmc_head.exists() and pmc_head.stat().st_size:
    with pmc_head.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            path = row.get("File") or row.get("file") or row.get("AccessionID") or ""
            if ".tar.gz" in path:
                summary["pmc_oa_candidate"] = row
                break

print(json.dumps(summary, sort_keys=True, indent=2))
PY

echo "uploading manifests"
aws s3 cp "$WORK/manifests/" "$LAKE_PREFIX/manifests/$RUN_ID/" \
  --recursive --region "$REGION" --only-show-errors
aws s3 cp "$WORK/pilot/" "$LAKE_PREFIX/runs/$RUN_ID/pilot/" \
  --recursive --region "$REGION" --only-show-errors

if [[ "$DOWNLOAD_ARXIV_SHARD" == "1" ]]; then
  echo "running bounded arxiv source shard pilot"
  python3 - <<'PY' "$WORK/pilot/manifest_summary.json" > "$WORK/pilot/arxiv_selected_source.txt"
import json, sys
data = json.load(open(sys.argv[1]))
c = data.get("arxiv_source_candidate") or {}
print(c.get("filename", ""))
PY
  ARXIV_SRC_KEY="$(cat "$WORK/pilot/arxiv_selected_source.txt")"
  if [[ -n "$ARXIV_SRC_KEY" ]]; then
    echo "selected $ARXIV_SRC_KEY"
    aws s3 cp "s3://arxiv/$ARXIV_SRC_KEY" "$WORK/pilot/arxiv_source_sample.tar" \
      --request-payer requester --region "$REGION" --only-show-errors
    tar -tf "$WORK/pilot/arxiv_source_sample.tar" | head -200 > "$WORK/pilot/arxiv_source_tar_members_head.txt"
    mkdir -p "$WORK/pilot/arxiv_extract"
    tar -xf "$WORK/pilot/arxiv_source_sample.tar" -C "$WORK/pilot/arxiv_extract" \
      $(tar -tf "$WORK/pilot/arxiv_source_sample.tar" | head -20) || true
    find "$WORK/pilot/arxiv_extract" -type f -maxdepth 4 | head -50 > "$WORK/pilot/arxiv_extracted_files_head.txt"
    python3 - <<'PY' "$WORK/pilot/arxiv_extract" > "$WORK/pilot/arxiv_text_probe.json"
import gzip, json, os, sys
from pathlib import Path

root = Path(sys.argv[1])
out = {"files_seen": 0, "text_candidates": []}
for p in root.rglob("*"):
    if not p.is_file():
        continue
    out["files_seen"] += 1
    name = p.name.lower()
    try:
        if name.endswith(".gz"):
            data = gzip.open(p, "rb").read(8192)
        else:
            data = p.read_bytes()[:8192]
    except Exception:
        continue
    printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in data)
    if data and printable / max(1, len(data)) > 0.75:
        text = data.decode("utf-8", "replace")[:2000]
        out["text_candidates"].append({"path": str(p.relative_to(root)), "sample": text})
    if len(out["text_candidates"]) >= 3:
        break
print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
PY
    aws s3 cp "$WORK/pilot/" "$LAKE_PREFIX/runs/$RUN_ID/pilot/" \
      --recursive --exclude "arxiv_source_sample.tar" --region "$REGION" --only-show-errors
  else
    echo "no arxiv source candidate selected"
  fi
fi

cat > "$WORK/pilot/complete.json" <<EOF
{"run_id":"$RUN_ID","completed_at":"$(date -u +"%Y-%m-%dT%H:%M:%SZ")","status":"complete","lake_prefix":"$LAKE_PREFIX"}
EOF
aws s3 cp "$WORK/pilot/complete.json" "$LAKE_PREFIX/runs/$RUN_ID/complete.json" \
  --region "$REGION" --only-show-errors
upload_logs
echo "research papers EC2 pilot complete"
shutdown -h now

#!/bin/zsh
# Verify a built ForecastBench submission against the qset, manifest, and GCS.
set -e

export PATH="/opt/homebrew/bin:/Users/emizemani/.local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR=${0:A:h}
WORKDIR=${FORECASTBENCH_WORKDIR:-${SCRIPT_DIR:h:h}}
cd "$WORKDIR" || exit 1

DUE=${FORECASTBENCH_DUE:-2026-06-21}
DATA_DIR="data/forecastbench"
QSET="$DATA_DIR/q_${DUE}.json"
MANIFEST="$DATA_DIR/${DUE}.manifest.jsonl"
DONE_MARKER="$DATA_DIR/.uploaded_${DUE}"
DEFAULT_BUCKET=""
[ "$DUE" = "2026-06-21" ] && DEFAULT_BUCKET="forecastbench-submissions/2026-06-21/team26"
BUCKET_FROM_FILE=$(grep -E '^FORECASTBENCH_BUCKET=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' )
BUCKET=${FORECASTBENCH_BUCKET:-$BUCKET_FROM_FILE}
[ -z "$BUCKET" ] && BUCKET="$DEFAULT_BUCKET"
REQUIRE_REMOTE=${FORECASTBENCH_REQUIRE_REMOTE:-}
[ -z "$REQUIRE_REMOTE" ] && { [ -n "$BUCKET" ] && REQUIRE_REMOTE=1 || REQUIRE_REMOTE=0; }
REQUIRE_DONE=${FORECASTBENCH_REQUIRE_DONE:-$REQUIRE_REMOTE}
REQUIRE_PROOF=${FORECASTBENCH_REQUIRE_PROOF:-$REQUIRE_DONE}
REQUIRE_CURRENT_QSET=${FORECASTBENCH_REQUIRE_CURRENT_QSET:-$REQUIRE_REMOTE}

FAILED=0
fail() {
  echo "ERROR: $*" >&2
  FAILED=1
}

echo "forecastbench_verify $(date) due=$DUE workspace=$(pwd)"

[ -f "$QSET" ] || fail "missing question set $QSET"
FILES=($DATA_DIR/${DUE}.Vaticinus.[123].json(N))
[ "${#FILES[@]}" -gt 0 ] || fail "missing submission file(s) for $DUE"
[ -f "$MANIFEST" ] || fail "missing manifest $MANIFEST"
if [ "$REQUIRE_DONE" = "1" ]; then
  [ -f "$DONE_MARKER" ] || fail "missing done marker $DONE_MARKER"
fi

if [ "$FAILED" = "0" ]; then
  for FILE in "${FILES[@]}"; do
    /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.check_submission "$QSET" "$FILE" || FAILED=1
  done
fi

if [ "$FAILED" = "0" ] && [ "$REQUIRE_CURRENT_QSET" = "1" ]; then
  if /Users/emizemani/.local/bin/uv run python -m engine.forecastbench.submit --check-current "$DUE" "$QSET"; then
    :
  else
    CURRENT_QSET_RC=$?
    if [ "$CURRENT_QSET_RC" = "1" ]; then
      fail "local question set is stale versus the reachable official qset"
    elif [ "$CURRENT_QSET_RC" = "3" ]; then
      echo "WARNING: live question set freshness check unavailable; continuing with local/remote/proof verification"
    else
      fail "live question set freshness check failed with rc=$CURRENT_QSET_RC"
    fi
  fi
else
  [ "$REQUIRE_CURRENT_QSET" = "1" ] || echo "live qset freshness check skipped (FORECASTBENCH_REQUIRE_CURRENT_QSET=0 or remote verification skipped)"
fi

if [ "$FAILED" = "0" ] && [ "$REQUIRE_REMOTE" = "1" ]; then
  if [ -z "$BUCKET" ]; then
    fail "remote verification requested but FORECASTBENCH_BUCKET/default bucket is unset"
  elif ! command -v gsutil >/dev/null 2>&1; then
    fail "remote verification requested but gsutil is missing"
  else
    DEST="$BUCKET"
    case "$DEST" in gs://*) ;; *) DEST="gs://${DEST}" ;; esac
    for FILE in "${FILES[@]}"; do
      read LOCAL_SHA LOCAL_MD5 LOCAL_SIZE <<< "$(python3 - "$FILE" <<'PY'
import base64
import hashlib
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()
print(
    hashlib.sha256(data).hexdigest(),
    base64.b64encode(hashlib.md5(data).digest()).decode(),
    len(data),
)
PY
)"
      REMOTE="${DEST}/$(basename "$FILE")"
      REMOTE_STAT=$(gsutil stat "$REMOTE" 2>/dev/null || true)
      REMOTE_MD5=$(printf '%s\n' "$REMOTE_STAT" | awk -F': *' 'index($0, "Hash (md5)") {print $2; exit}')
      REMOTE_SIZE=$(printf '%s\n' "$REMOTE_STAT" | awk -F': *' 'index($0, "Content-Length") {print $2; exit}')
      if [ "$REMOTE_MD5" != "$LOCAL_MD5" ] || [ "$REMOTE_SIZE" != "$LOCAL_SIZE" ]; then
        fail "remote mismatch for $REMOTE local_md5=$LOCAL_MD5 remote_md5=${REMOTE_MD5:-missing} local_bytes=$LOCAL_SIZE remote_bytes=${REMOTE_SIZE:-missing}"
      else
        echo "remote OK $REMOTE sha256=$LOCAL_SHA md5=$LOCAL_MD5 bytes=$LOCAL_SIZE"
      fi
    done
    REMOTE_JSONS=("${(@f)$(gsutil ls "${DEST}/*.json" 2>/dev/null || true)}")
    EXPECTED_JSONS=()
    for FILE in "${FILES[@]}"; do
      EXPECTED_JSONS+=("$(basename "$FILE")")
    done
    if [ "${#REMOTE_JSONS[@]}" -eq 0 ]; then
      fail "remote JSON listing returned no files for ${DEST}/*.json; cannot exclude stale/stray forecast files"
    else
      for REMOTE_JSON in "${REMOTE_JSONS[@]}"; do
        [ -n "$REMOTE_JSON" ] || continue
        REMOTE_NAME=$(basename "$REMOTE_JSON")
        FOUND=0
        for EXPECTED_NAME in "${EXPECTED_JSONS[@]}"; do
          [ "$REMOTE_NAME" = "$EXPECTED_NAME" ] && FOUND=1
        done
        if [ "$FOUND" != "1" ]; then
          fail "unexpected remote JSON object in submission prefix: $REMOTE_JSON"
        fi
      done
    fi
  fi
else
  [ "$REQUIRE_REMOTE" = "1" ] || echo "remote verification skipped (bucket unset or FORECASTBENCH_REQUIRE_REMOTE=0)"
fi

if [ "$FAILED" = "0" ]; then
  python3 - "$MANIFEST" "$REQUIRE_REMOTE" "${FILES[@]}" <<'PY' || FAILED=1
import base64
import hashlib
import json
import sys
from pathlib import Path

manifest = Path(sys.argv[1])
require_remote = sys.argv[2] == "1"
files = [Path(p) for p in sys.argv[3:]]
rows = []
for line in manifest.read_text().splitlines():
    if line.strip():
        rows.append(json.loads(line))

by_name = {Path(str(row.get("file", ""))).name: row for row in rows}
errors = []
for path in files:
    name = path.name
    row = by_name.get(name)
    if row is None:
        errors.append(f"manifest missing {name}")
        continue
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
    size = len(data)
    if row.get("sha256") != sha:
        errors.append(f"manifest sha256 mismatch for {name}")
    if row.get("md5_base64") != md5:
        errors.append(f"manifest md5 mismatch for {name}")
    if row.get("bytes") != size:
        errors.append(f"manifest byte mismatch for {name}")
    if require_remote and not row.get("uploaded"):
        errors.append(f"manifest says not uploaded for {name}")
    if require_remote and not row.get("verified"):
        errors.append(f"manifest says not verified for {name}")
    if require_remote and row.get("remote_md5_base64") != md5:
        errors.append(f"manifest remote md5 mismatch for {name}")
    if require_remote and row.get("remote_bytes") != size:
        errors.append(f"manifest remote bytes mismatch for {name}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print(f"manifest OK: {len(files)} file(s), require_remote={require_remote}")
PY
fi

if [ "$FAILED" = "0" ] && [ "$REQUIRE_PROOF" = "1" ]; then
  python3 - "$DATA_DIR/proofs" "$DUE" "$QSET" "$MANIFEST" "$DONE_MARKER" "${FILES[@]}" <<'PY' || FAILED=1
import base64
import hashlib
import json
import sys
from pathlib import Path

proof_root = Path(sys.argv[1])
due = sys.argv[2]
current_paths = [Path(p) for p in sys.argv[3:]]
errors = []

proof_dirs = []
if proof_root.exists():
    proof_dirs = sorted(
        [p for p in proof_root.iterdir() if p.is_dir() and p.name.startswith(f"{due}_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

if not proof_dirs:
    errors.append(f"missing proof directory for {due} under {proof_root}")
else:
    def hashes(path: Path) -> tuple[str, str, int]:
        data = path.read_bytes()
        return (
            hashlib.sha256(data).hexdigest(),
            base64.b64encode(hashlib.md5(data).digest()).decode(),
            len(data),
        )

    def check_proof_dir(proof_dir: Path) -> list[str]:
        local_errors = []
        proof_json = proof_dir / "proof.json"
        if not proof_json.exists():
            local_errors.append(f"missing proof.json in {proof_dir}")
            proof = {}
        else:
            try:
                proof = json.loads(proof_json.read_text())
            except json.JSONDecodeError as exc:
                local_errors.append(f"bad proof.json in {proof_dir}: {exc}")
                proof = {}
        if proof.get("due") != due:
            local_errors.append(f"proof due mismatch in {proof_dir}: {proof.get('due')!r} != {due!r}")

        artifacts = proof.get("artifacts") if isinstance(proof, dict) else {}
        recorded = []
        if isinstance(artifacts, dict):
            for key in ("question_set", "manifest", "done_marker"):
                value = artifacts.get(key)
                if isinstance(value, dict):
                    recorded.append(value)
            submissions = artifacts.get("submissions")
            if isinstance(submissions, list):
                recorded.extend(v for v in submissions if isinstance(v, dict))

        by_name = {str(row.get("copied_basename")): row for row in recorded}

        for current in current_paths:
            name = current.name
            copied = proof_dir / name
            if not copied.exists():
                local_errors.append(f"proof copy missing {name} in {proof_dir}")
                continue
            current_sha, current_md5, current_size = hashes(current)
            copied_sha, copied_md5, copied_size = hashes(copied)
            if (copied_sha, copied_md5, copied_size) != (current_sha, current_md5, current_size):
                local_errors.append(f"proof copy differs from current artifact for {name} in {proof_dir}")
            row = by_name.get(name)
            if row is None:
                local_errors.append(f"proof.json missing artifact record for {name} in {proof_dir}")
                continue
            if row.get("sha256") != copied_sha:
                local_errors.append(f"proof sha256 mismatch for {name} in {proof_dir}")
            if row.get("md5_base64") != copied_md5:
                local_errors.append(f"proof md5 mismatch for {name} in {proof_dir}")
            if row.get("bytes") != copied_size:
                local_errors.append(f"proof byte mismatch for {name} in {proof_dir}")
        return local_errors

    checked = []
    for proof_dir in proof_dirs:
        proof_errors = check_proof_dir(proof_dir)
        if not proof_errors:
            print(f"proof OK: {proof_dir}")
            break
        checked.append((proof_dir, proof_errors))
    else:
        errors.append(f"no matching proof directory for {due} under {proof_root}; checked {len(checked)}")
        for proof_dir, proof_errors in checked:
            errors.append(f"{proof_dir}:")
            errors.extend(f"  {error}" for error in proof_errors)

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
PY
else
  [ "$REQUIRE_PROOF" = "1" ] || echo "proof verification skipped (FORECASTBENCH_REQUIRE_PROOF=0 or done marker not required)"
fi

if [ "$FAILED" != "0" ]; then
  exit 1
fi
echo "forecastbench upload verify OK for $DUE"

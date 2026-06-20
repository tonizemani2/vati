"""Disk-safe local data inventory and optional S3 offload helpers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

GIB = 1024 ** 3
MIB = 1024 ** 2
CRITICAL_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".parquet"}
DEFAULT_S3_USD_PER_GIB_MONTH = float(os.environ.get("PREDICT_FUTURE_S3_USD_PER_GIB_MONTH", "0.023"))


class DataOffloadError(RuntimeError):
    """Raised when an offload cannot be proven safe enough to continue."""


@dataclass(frozen=True)
class InventoryEntry:
    path: Path
    size_bytes: int
    critical: bool

    @property
    def size_gib(self) -> float:
        return self.size_bytes / GIB

    def as_dict(self, *, base: Path | None = None) -> dict[str, object]:
        p = self.path
        if base is not None:
            try:
                p = p.relative_to(base)
            except ValueError:
                pass
        return {
            "path": str(p),
            "size_bytes": self.size_bytes,
            "size_gib": round(self.size_gib, 3),
            "critical": self.critical,
        }


@dataclass(frozen=True)
class OffloadResult:
    local_path: Path
    remote_uri: str
    size_bytes: int
    sha256: str | None
    uploaded: bool
    deleted_local: bool
    estimated_storage_usd_month: float

    def as_dict(self) -> dict[str, object]:
        return {
            "local_path": str(self.local_path),
            "remote_uri": self.remote_uri,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "uploaded": self.uploaded,
            "deleted_local": self.deleted_local,
            "estimated_storage_usd_month": round(self.estimated_storage_usd_month, 10),
        }


@dataclass(frozen=True)
class ManifestEntry:
    ts: str
    local_path: str
    remote_uri: str
    size_bytes: int
    sha256: str | None
    uploaded: bool
    deleted_local: bool
    estimated_storage_usd_month: float = 0.0

    @property
    def size_gib(self) -> float:
        return self.size_bytes / GIB

    def as_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts,
            "local_path": self.local_path,
            "remote_uri": self.remote_uri,
            "size_bytes": self.size_bytes,
            "size_gib": round(self.size_gib, 3),
            "sha256": self.sha256,
            "uploaded": self.uploaded,
            "deleted_local": self.deleted_local,
            "estimated_storage_usd_month": round(self.estimated_storage_usd_month, 10),
        }


def is_critical(path: Path) -> bool:
    return path.suffix.lower() in CRITICAL_SUFFIXES


def iter_large_files(root: Path, *, min_size_mb: float = 100.0) -> list[InventoryEntry]:
    root = root.expanduser().resolve()
    threshold = int(min_size_mb * MIB)
    if not root.exists():
        raise DataOffloadError(f"{root} does not exist")
    paths: Iterable[Path]
    if root.is_file():
        paths = [root]
    else:
        paths = (p for p in root.rglob("*") if p.is_file())

    entries: list[InventoryEntry] = []
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= threshold:
            entries.append(InventoryEntry(path=path, size_bytes=size, critical=is_critical(path)))
    entries.sort(key=lambda e: e.size_bytes, reverse=True)
    return entries


def format_inventory(entries: list[InventoryEntry], *, base: Path | None = None) -> str:
    if not entries:
        return "No files matched the requested size threshold."
    total = sum(e.size_bytes for e in entries)
    lines = [f"large local files: {len(entries)} files, {total / GIB:.2f} GiB total"]
    for entry in entries:
        marker = " critical" if entry.critical else ""
        display = entry.as_dict(base=base)["path"]
        lines.append(f"{entry.size_gib:8.2f} GiB  {display}{marker}")
    return "\n".join(lines)


def inventory_summary(entries: list[InventoryEntry], *, base: Path | None = None) -> dict[str, object]:
    total = sum(e.size_bytes for e in entries)
    return {
        "entries": len(entries),
        "total_bytes": total,
        "total_gib": round(total / GIB, 3),
        "critical_entries": sum(1 for e in entries if e.critical),
        "estimated_storage_usd_month": round(
            sum(estimate_s3_storage_usd_month(e.size_bytes) for e in entries), 10
        ),
        "files": [e.as_dict(base=base) for e in entries],
    }


def estimate_s3_storage_usd_month(size_bytes: int, *, usd_per_gib_month: float = DEFAULT_S3_USD_PER_GIB_MONTH) -> float:
    return (size_bytes / GIB) * usd_per_gib_month


def s3_uri_for(local_path: Path, *, base: Path, dest_prefix: str) -> str:
    if not dest_prefix.startswith("s3://"):
        raise DataOffloadError("S3 destination must start with s3://")
    clean_prefix = dest_prefix.rstrip("/")
    local_path = local_path.resolve()
    base = base.resolve()
    try:
        rel = local_path.relative_to(base)
    except ValueError as exc:
        raise DataOffloadError(f"{local_path} is not under base {base}") from exc
    return clean_prefix + "/" + "/".join(rel.parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * MIB), b""):
            h.update(chunk)
    return h.hexdigest()


def aws_cp(local_path: Path, remote_uri: str) -> None:
    proc = subprocess.run(
        ["aws", "s3", "cp", str(local_path), remote_uri, "--only-show-errors"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise DataOffloadError(f"aws s3 cp failed for {local_path}: {detail}")


def aws_remote_size(remote_uri: str) -> int:
    proc = subprocess.run(
        ["aws", "s3", "ls", remote_uri],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise DataOffloadError(f"aws s3 ls failed for {remote_uri}: {detail}")
    parts = proc.stdout.strip().split()
    if len(parts) < 4:
        raise DataOffloadError(f"could not parse aws s3 ls output for {remote_uri}: {proc.stdout!r}")
    try:
        return int(parts[2])
    except ValueError as exc:
        raise DataOffloadError(f"could not parse remote size for {remote_uri}: {proc.stdout!r}") from exc


def append_manifest(manifest_path: Path, result: OffloadResult) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **result.as_dict(),
    }
    with manifest_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def read_manifest(manifest_path: Path) -> list[ManifestEntry]:
    manifest_path = manifest_path.expanduser()
    if not manifest_path.exists():
        return []
    entries: list[ManifestEntry] = []
    with manifest_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                entries.append(
                    ManifestEntry(
                        ts=str(row["ts"]),
                        local_path=str(row["local_path"]),
                        remote_uri=str(row["remote_uri"]),
                        size_bytes=int(row["size_bytes"]),
                        sha256=row.get("sha256"),
                        uploaded=bool(row.get("uploaded")),
                        deleted_local=bool(row.get("deleted_local")),
                        estimated_storage_usd_month=float(row.get("estimated_storage_usd_month") or 0.0),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise DataOffloadError(f"invalid manifest row {line_no} in {manifest_path}: {exc}") from exc
    return entries


def format_manifest(entries: list[ManifestEntry]) -> str:
    if not entries:
        return "No offload manifest entries found."
    summary = manifest_summary(entries)
    lines = [
        f"offload manifest: {summary['entries']} entries, "
        f"{float(summary['recorded_gib']):.2f} GiB recorded, "
        f"est ${float(summary['estimated_storage_usd_month']):.2f}/mo"
    ]
    for entry in entries:
        status = "uploaded" if entry.uploaded else "planned"
        if entry.deleted_local:
            status += ", local deleted"
        digest = f" sha256={entry.sha256[:12]}..." if entry.sha256 else ""
        lines.append(
            f"{entry.size_gib:8.2f} GiB  est ${entry.estimated_storage_usd_month:.2f}/mo  "
            f"{status}  {entry.local_path} <- {entry.remote_uri}{digest}"
        )
    return "\n".join(lines)


def manifest_summary(entries: list[ManifestEntry]) -> dict[str, object]:
    total_bytes = sum(e.size_bytes for e in entries)
    return {
        "entries": len(entries),
        "uploaded": sum(1 for e in entries if e.uploaded),
        "local_deleted": sum(1 for e in entries if e.deleted_local),
        "recorded_bytes": total_bytes,
        "recorded_gib": round(total_bytes / GIB, 3),
        "estimated_storage_usd_month": round(sum(e.estimated_storage_usd_month for e in entries), 4),
        "files": [e.as_dict() for e in entries],
    }


def restore_commands(entries: list[ManifestEntry]) -> list[str]:
    return [
        f"aws s3 cp {entry.remote_uri} {entry.local_path} --only-show-errors"
        for entry in entries
        if entry.uploaded
    ]


def format_restore_plan(entries: list[ManifestEntry]) -> str:
    commands = restore_commands(entries)
    if not commands:
        return "No uploaded manifest entries to restore."
    lines = ["restore plan:"]
    lines.extend(commands)
    lines.append("After restore, verify hashes with: shasum -a 256 <restored-file>")
    return "\n".join(lines)


def offload(
    entries: list[InventoryEntry],
    *,
    base: Path,
    dest_prefix: str,
    execute: bool = False,
    delete_local: bool = False,
    allow_critical_delete: bool = False,
    manifest_path: Path | None = None,
) -> list[OffloadResult]:
    results: list[OffloadResult] = []
    for entry in entries:
        remote = s3_uri_for(entry.path, base=base, dest_prefix=dest_prefix)
        deleted = False
        digest: str | None = None
        if execute:
            if delete_local and entry.critical and not allow_critical_delete:
                raise DataOffloadError(
                    f"refusing to delete critical local data file {entry.path}; "
                    "rerun with --allow-critical-delete after confirming the offload"
                )
            digest = sha256_file(entry.path)
            aws_cp(entry.path, remote)
            remote_size = aws_remote_size(remote)
            if remote_size != entry.size_bytes:
                raise DataOffloadError(
                    f"remote size mismatch for {remote}: {remote_size} != {entry.size_bytes}"
                )
            if delete_local:
                entry.path.unlink()
                deleted = True
        result = OffloadResult(
            local_path=entry.path,
            remote_uri=remote,
            size_bytes=entry.size_bytes,
            sha256=digest,
            uploaded=execute,
            deleted_local=deleted,
            estimated_storage_usd_month=estimate_s3_storage_usd_month(entry.size_bytes),
        )
        if execute and manifest_path is not None:
            append_manifest(manifest_path, result)
        results.append(result)
    return results


def format_offload_plan(results: list[OffloadResult], *, execute: bool, delete_local: bool = False) -> str:
    if not results:
        return "No files matched the requested offload threshold."
    mode = "uploaded" if execute else "dry-run plan"
    total = sum(r.size_bytes for r in results)
    monthly = sum(r.estimated_storage_usd_month for r in results)
    lines = [f"S3 offload {mode}: {len(results)} files, {total / GIB:.2f} GiB, est ${monthly:.2f}/mo"]
    for result in results:
        action = "uploaded" if result.uploaded else "would upload"
        if result.deleted_local:
            action += " + deleted local"
        lines.append(
            f"{result.size_bytes / GIB:8.2f} GiB  est ${result.estimated_storage_usd_month:.2f}/mo  "
            f"{action}: {result.local_path} -> {result.remote_uri}"
        )
    if not execute and delete_local:
        lines.append("Dry-run safety: --delete-local was ignored; no local files will be deleted without --execute.")
    return "\n".join(lines)

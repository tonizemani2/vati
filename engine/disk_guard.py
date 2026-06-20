"""Local disk-space guardrails for data collection and world-state rebuilds."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

DEFAULT_MIN_FREE_GB = float(os.environ.get("PREDICT_FUTURE_MIN_FREE_GB", "85"))
DEFAULT_MAX_USED_PCT = float(os.environ.get("PREDICT_FUTURE_MAX_USED_PCT", "92"))
GIB = 1024 ** 3


class DiskSpaceError(RuntimeError):
    """Raised before a local data job can push the machine into disk pressure."""


def usage(path: str | Path) -> dict[str, float]:
    total, used, free = shutil.disk_usage(Path(path))
    return {
        "total_gb": total / GIB,
        "used_gb": used / GIB,
        "free_gb": free / GIB,
        "used_pct": 100.0 * used / total if total else 0.0,
    }


def assert_safe(
    path: str | Path,
    *,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    max_used_pct: float = DEFAULT_MAX_USED_PCT,
    label: str = "data job",
    allow_low_disk: bool = False,
) -> dict[str, float]:
    stats = usage(path)
    if allow_low_disk:
        return stats
    failures: list[str] = []
    if stats["free_gb"] < min_free_gb:
        failures.append(f"free {stats['free_gb']:.1f}GiB < required {min_free_gb:.1f}GiB")
    if stats["used_pct"] > max_used_pct:
        failures.append(f"used {stats['used_pct']:.1f}% > allowed {max_used_pct:.1f}%")
    if failures:
        raise DiskSpaceError(
            f"Refusing {label}: " + "; ".join(failures) + ". "
            "Free disk or rerun with an explicit low-disk override."
        )
    return stats

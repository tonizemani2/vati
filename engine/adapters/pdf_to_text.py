"""PDF → text adapter — poppler's `pdftotext` (free, local, no network, no key).

The free baseline for PDF ingestion (plan §4). OCR (OpenRouter vision) is the paid
fallback for scanned/image PDFs and is deferred until something actually needs it. No
cost gate here: this is a local binary, $0.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PDFTOTEXT = "pdftotext"


def available() -> bool:
    """True if the poppler `pdftotext` binary is on PATH."""
    return shutil.which(PDFTOTEXT) is not None


def pdf_to_text(path: str | Path, *, layout: bool = False) -> str:
    """Extract text from a PDF. `-` makes pdftotext write to stdout.

    Raises FileNotFoundError if the binary is missing or the file doesn't exist — the
    caller should check `available()` / catch, rather than silently get empty text.
    """
    if not available():
        raise FileNotFoundError(
            f"{PDFTOTEXT} not found on PATH — install poppler (brew install poppler)"
        )
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"no such PDF: {src}")
    cmd = [PDFTOTEXT]
    if layout:
        cmd.append("-layout")
    cmd += [str(src), "-"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(f"{PDFTOTEXT} failed ({out.returncode}): {out.stderr.strip()}")
    return out.stdout

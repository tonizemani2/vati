#!/usr/bin/env python3
"""Publish Pope board assets for the Vaticinus site.

The /forecasts page is a real Next route in site/src/app/forecasts/page.tsx.
This script only refreshes the static files that route links to: board PDFs and
first-page PNG previews.

Usage: python3 -m engine.pope.publish_site
"""
from __future__ import annotations

import os
import shutil
import subprocess


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "site", "public", "forecasts")
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")
PREVIEW_VERSION = "memo"

BOARDS = [
    {
        "slug": "critical-minerals",
        "pdf_src": "research/pope/critical-minerals-2026-06-20.pdf",
        "pdf": "critical-minerals.pdf",
    },
    {
        "slug": "post-ai-world",
        "pdf_src": "research/pope/post-ai-world-2026-06-17.pdf",
        "pdf": "post-ai-world.pdf",
    },
    {
        "slug": "after-ai",
        "pdf_src": "research/pope/after-ai-2026-06-17.pdf",
        "pdf": "after-ai.pdf",
    },
    {
        "slug": "catalyst",
        "pdf_src": "research/pope/any-short-2026-06-15.pdf",
        "pdf": "catalyst.pdf",
    },
    {
        "slug": "structural",
        "pdf_src": "research/pope/any-long-2026-06-15.pdf",
        "pdf": "structural.pdf",
    },
    {
        "slug": "long-horizon",
        "pdf_src": "research/pope/long-horizon-2026-06-14.pdf",
        "pdf": "long-horizon.pdf",
    },
    {
        "slug": "inelastic-needles",
        "pdf_src": "research/pope/inelastic-needles-2026-06-15.pdf",
        "pdf": "inelastic-needles.pdf",
    },
    {
        "slug": "space",
        "pdf_src": "research/pope/space-2026-06-14.pdf",
        "pdf": "space.pdf",
    },
    {
        "slug": "chips",
        "pdf_src": "research/pope/chips-2026-06-14.pdf",
        "pdf": "chips.pdf",
    },
    {
        "slug": "biotech",
        "pdf_src": "research/pope/biotech-2026-06-14.pdf",
        "pdf": "biotech.pdf",
    },
]


def _preview_pdf(pdf_src: str, slug: str) -> str | None:
    if not os.path.exists(pdf_src) or not shutil.which("pdftoppm"):
        return None

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    out_prefix = os.path.join(PREVIEW_DIR, f"{slug}-{PREVIEW_VERSION}")
    out_path = out_prefix + ".png"
    try:
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-f",
                "1",
                "-l",
                "1",
                "-singlefile",
                "-scale-to-x",
                "720",
                "-scale-to-y",
                "-1",
                pdf_src,
                out_prefix,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        print(f"preview skipped for {slug}: {exc}")
        return None

    return out_path if os.path.exists(out_path) else None


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    stale_index = os.path.join(OUT_DIR, "index.html")
    if os.path.exists(stale_index):
        os.remove(stale_index)

    copied = []
    previews = []
    for board in BOARDS:
        pdf_src = os.path.join(REPO, board["pdf_src"])
        if not os.path.exists(pdf_src):
            print(f"skip {board['slug']}: missing {board['pdf_src']}")
            continue

        shutil.copy(pdf_src, os.path.join(OUT_DIR, board["pdf"]))
        copied.append(board["pdf"])
        if _preview_pdf(pdf_src, board["slug"]):
            previews.append(board["slug"])

    print(f"published {len(copied)} PDFs to {OUT_DIR}")
    print("pdfs:", ", ".join(copied))
    print(f"previews: {len(previews)} rendered")


if __name__ == "__main__":
    main()

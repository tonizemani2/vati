"""
SEC EDGAR Bulk Collector
========================
Collects structured XBRL financials + 8-K event indexes for a broad
large/mid-cap universe, stages gzipped JSON under /tmp/sec_stage/,
pushes to S3, then prunes local.

Usage:
    uv run python -m engine.sec_bulk_collect

Environment:
    EDGAR_IDENTITY  — override the SEC User-Agent (defaults to project value)
    SEC_MAX_CIK     — cap number of CIKs (0 = no cap)
    SEC_BATCH_SIZE  — flush/upload batch size (default 200)
"""

import gzip
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import httpx

# ── Config ──────────────────────────────────────────────────────────────────
IDENTITY = os.getenv(
    "EDGAR_IDENTITY",
    "predictthefuture research research@vaticinus.com",
)
S3_PREFIX = "s3://mining-terminal-research-405844305300-us-east-1/predict/filings/sec/"
STAGE_DIR = Path("/tmp/sec_stage")
MAX_STAGE_BYTES = 1_800_000_000        # 1.8 GB — flush before we hit 2 GB
RATE_SLEEP = 0.12                       # 10 req/s ceiling
MAX_CIK = int(os.getenv("SEC_MAX_CIK", "0"))   # 0 = no cap
BATCH_SIZE = int(os.getenv("SEC_BATCH_SIZE", "200"))
LOOKBACK_YEARS = 3                      # keep last 3 annual periods

KEY_CONCEPTS = [
    # Income statement
    "us-gaap/Revenues",
    "us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap/SalesRevenueNet",
    "us-gaap/NetIncomeLoss",
    "us-gaap/EarningsPerShareBasic",
    "us-gaap/EarningsPerShareDiluted",
    "us-gaap/GrossProfit",
    "us-gaap/OperatingIncomeLoss",
    "us-gaap/CostOfRevenue",
    "us-gaap/ResearchAndDevelopmentExpense",
    "us-gaap/SellingGeneralAndAdministrativeExpense",
    # Balance sheet
    "us-gaap/Assets",
    "us-gaap/Liabilities",
    "us-gaap/StockholdersEquity",
    "us-gaap/CashAndCashEquivalentsAtCarryingValue",
    "us-gaap/LongTermDebt",
    "us-gaap/CommonStockSharesOutstanding",
    # Cash flow
    "us-gaap/NetCashProvidedByUsedInOperatingActivities",
    "us-gaap/CapitalExpenditureDiscontinuedOperations",
    "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment",
    "us-gaap/FreeCashFlow",
    # DEI
    "dei/EntityPublicFloat",
    "dei/EntityCommonStockSharesOutstanding",
]

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sec_bulk")

STAGE_DIR.mkdir(parents=True, exist_ok=True)

# ── HTTP client (direct to SEC, NO proxy) ────────────────────────────────────
HEADERS = {
    "User-Agent": IDENTITY,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}
client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def sec_get(url: str, retries: int = 3) -> Optional[Any]:
    """Rate-limited GET to SEC with retry on 429/5xx."""
    for attempt in range(retries):
        try:
            time.sleep(RATE_SLEEP)
            r = client.get(url)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                log.warning("429 rate-limit — sleeping %ds", wait)
                time.sleep(wait)
            elif r.status_code == 404:
                return None
            else:
                log.debug("HTTP %d for %s", r.status_code, url)
                time.sleep(2)
        except Exception as exc:
            log.debug("Request error %s: %s", url, exc)
            time.sleep(2)
    return None


def padded_cik(cik: int) -> str:
    return str(cik).zfill(10)


def fetch_company_tickers() -> list[dict]:
    """Download full ~10k company ticker list from SEC."""
    log.info("Fetching company tickers index …")
    data = sec_get("https://www.sec.gov/files/company_tickers.json")
    if not data:
        raise RuntimeError("Could not fetch company_tickers.json")
    companies = [
        {"cik": int(v["cik_str"]), "ticker": v["ticker"], "name": v["title"]}
        for v in data.values()
    ]
    log.info("Universe: %d companies", len(companies))
    return companies


def extract_key_facts(facts_data: dict, cik: int, ticker: str, name: str) -> list[dict]:
    """
    Extract key line-item time series from raw companyfacts JSON.
    Returns list of flat dicts: one row per (concept, period).
    Only keeps annual (12-month) periods within the lookback window.
    """
    cutoff_year = date.today().year - LOOKBACK_YEARS
    rows = []
    facts = facts_data.get("facts", {})

    for taxonomy_concept in KEY_CONCEPTS:
        taxonomy, concept = taxonomy_concept.split("/", 1)
        concept_data = facts.get(taxonomy, {}).get(concept)
        if not concept_data:
            continue
        label = concept_data.get("label", concept)
        units = concept_data.get("units", {})

        for unit_key, periods in units.items():
            for period in periods:
                form = period.get("form", "")
                fp = period.get("fp", "")
                fy = period.get("fy", 0)

                # Annual only: FY or 12-month period, from 10-K or 10-K/A
                if fp != "FY":
                    continue
                if form not in ("10-K", "10-K/A"):
                    continue
                if fy and int(fy) < cutoff_year:
                    continue

                rows.append({
                    "cik": cik,
                    "ticker": ticker,
                    "name": name,
                    "taxonomy": taxonomy,
                    "concept": concept,
                    "label": label,
                    "unit": unit_key,
                    "value": period.get("val"),
                    "start": period.get("start"),
                    "end": period.get("end"),
                    "filed": period.get("filed"),
                    "accn": period.get("accn"),
                    "fiscal_year": fy,
                    "fiscal_period": fp,
                    "form": form,
                })
    return rows


def fetch_eightk_index(cik: int) -> list[dict]:
    """Fetch recent 8-K filing index entries for a CIK."""
    url = (
        f"https://data.sec.gov/submissions/CIK{padded_cik(cik)}.json"
    )
    data = sec_get(url)
    if not data:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    cutoff = str(date.today().year - LOOKBACK_YEARS)
    results = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        filing_date = dates[i] if i < len(dates) else ""
        if filing_date < cutoff:
            continue
        results.append({
            "cik": cik,
            "form": form,
            "filing_date": filing_date,
            "accession": accns[i] if i < len(accns) else "",
            "primary_doc": descriptions[i] if i < len(descriptions) else "",
        })
    return results


def stage_bytes() -> int:
    """Current staging directory size in bytes."""
    total = 0
    for p in STAGE_DIR.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def s3_sync_and_prune():
    """Sync staging dir to S3, then delete local staged files."""
    log.info("Syncing to S3 … (stage size: %.1f MB)", stage_bytes() / 1e6)
    result = subprocess.run(
        [
            "aws", "s3", "sync",
            str(STAGE_DIR),
            S3_PREFIX,
            "--no-progress",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error("S3 sync error: %s", result.stderr[:500])
        return False
    log.info("S3 sync OK. Pruning local stage …")
    # Delete only data files, keep directory structure
    for p in STAGE_DIR.glob("**/*.gz"):
        p.unlink()
    for p in STAGE_DIR.glob("**/*.jsonl"):
        p.unlink()
    log.info("Stage pruned. Remaining: %.1f MB", stage_bytes() / 1e6)
    return True


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("SEC EDGAR Bulk Collector — identity: %s", IDENTITY)

    companies = fetch_company_tickers()
    if MAX_CIK > 0:
        companies = companies[:MAX_CIK]
        log.info("Capped to %d CIKs", MAX_CIK)

    index_records = []
    flat_facts_path = STAGE_DIR / "fundamentals.jsonl"
    eightk_path = STAGE_DIR / "eightk_index.jsonl"

    covered_ciks = []
    skipped_ciks = []
    total_fact_rows = 0
    total_eightk_rows = 0
    batch_count = 0

    flat_ff = open(flat_facts_path, "a")
    eightk_ff = open(eightk_path, "a")

    start_ts = time.time()

    try:
        for idx, co in enumerate(companies):
            cik = co["cik"]
            ticker = co["ticker"]
            name = co["name"]

            if (idx + 1) % 100 == 0:
                elapsed = time.time() - start_ts
                rate = (idx + 1) / elapsed * 60
                log.info(
                    "[%d/%d] %.0f co/min | facts=%d 8K=%d stage=%.0fMB",
                    idx + 1, len(companies), rate,
                    total_fact_rows, total_eightk_rows,
                    stage_bytes() / 1e6,
                )

            # ── 1. Companyfacts (XBRL) ─────────────────────────────────
            cf_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik(cik)}.json"
            raw = sec_get(cf_url)

            periods_captured = []
            if raw:
                # Save gzipped raw JSON
                gz_path = STAGE_DIR / "raw" / f"CIK{padded_cik(cik)}.json.gz"
                gz_path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(gz_path, "wt", encoding="utf-8") as gz:
                    json.dump(raw, gz)

                # Flatten key facts
                fact_rows = extract_key_facts(raw, cik, ticker, name)
                for row in fact_rows:
                    flat_ff.write(json.dumps(row) + "\n")
                total_fact_rows += len(fact_rows)

                # Track periods
                periods_captured = sorted(
                    set(r["fiscal_year"] for r in fact_rows if r["fiscal_year"])
                )

            # ── 2. 8-K index (from submissions endpoint) ───────────────
            eightk_rows = fetch_eightk_index(cik)
            for row in eightk_rows:
                eightk_ff.write(json.dumps(row) + "\n")
            total_eightk_rows += len(eightk_rows)

            # ── 3. Index entry ─────────────────────────────────────────
            if raw:
                covered_ciks.append(cik)
                index_records.append({
                    "cik": cik,
                    "ticker": ticker,
                    "name": name,
                    "periods_captured": periods_captured,
                    "fact_rows": len(fact_rows) if raw else 0,
                    "eightk_events": len(eightk_rows),
                    "collected_at": datetime.utcnow().isoformat(),
                })
            else:
                skipped_ciks.append(cik)

            batch_count += 1

            # ── 4. Flush to S3 when stage gets large ───────────────────
            if stage_bytes() > MAX_STAGE_BYTES:
                flat_ff.flush()
                eightk_ff.flush()
                log.info("Stage limit hit — uploading batch %d …", batch_count)
                s3_sync_and_prune()
                # Re-open append handles (files may have been deleted)
                flat_ff.close()
                eightk_ff.close()
                flat_ff = open(flat_facts_path, "a")
                eightk_ff = open(eightk_path, "a")

    except KeyboardInterrupt:
        log.warning("Interrupted — flushing partial results …")
    finally:
        flat_ff.flush()
        flat_ff.close()
        eightk_ff.flush()
        eightk_ff.close()

    # ── Write index ────────────────────────────────────────────────────────
    index_path = STAGE_DIR / "index.jsonl"
    with open(index_path, "w") as f:
        for rec in index_records:
            f.write(json.dumps(rec) + "\n")

    coverage_path = STAGE_DIR / "coverage_log.json"
    with open(coverage_path, "w") as f:
        json.dump(
            {
                "run_date": date.today().isoformat(),
                "universe_size": len(companies),
                "covered": len(covered_ciks),
                "skipped_no_facts": len(skipped_ciks),
                "total_fact_rows": total_fact_rows,
                "total_eightk_events": total_eightk_rows,
                "covered_ciks": covered_ciks,
                "skipped_ciks": skipped_ciks[:500],  # truncate for size
            },
            f,
            indent=2,
        )

    # ── Final S3 push ──────────────────────────────────────────────────────
    log.info("Final S3 sync …")
    s3_sync_and_prune()

    # ── Summary ────────────────────────────────────────────────────────────
    elapsed_min = (time.time() - start_ts) / 60
    log.info("=" * 60)
    log.info("DONE in %.1f minutes", elapsed_min)
    log.info("  Companies in universe : %d", len(companies))
    log.info("  Covered (facts found) : %d", len(covered_ciks))
    log.info("  Skipped (no facts)    : %d", len(skipped_ciks))
    log.info("  Fact rows (flat JSONL): %d", total_fact_rows)
    log.info("  8-K index events      : %d", total_eightk_rows)
    log.info("  S3 prefix             : %s", S3_PREFIX)
    log.info("=" * 60)

    return {
        "covered": len(covered_ciks),
        "skipped": len(skipped_ciks),
        "fact_rows": total_fact_rows,
        "eightk_rows": total_eightk_rows,
    }


if __name__ == "__main__":
    main()

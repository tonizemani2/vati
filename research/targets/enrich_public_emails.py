#!/usr/bin/env python3
"""Conservative public-email enrichment for outreach rows.

Reads contactable_messages.csv and searches public web snippets/pages for
direct emails for the highest-ranked rows that do not already have an email.

Outputs:
  - public_email_enrichment_topN.csv: every attempted row with candidates/source.
  - email_ready_messages_enriched.csv: existing direct-email rows plus public
    emails found with high or possible confidence.

This does not send mail. It keeps a confidence/source field so humans can verify.
"""
import asyncio
import csv
import re
import sys
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import httpx

from engine.adapters._vendor.exa_search import DDGClient, ExaClient

HERE = Path(__file__).parent
CONTACTABLE = HERE / "contactable_messages.csv"
OUT_PREFIX = HERE / "public_email_enrichment"
EMAIL_READY_ENRICHED = HERE / "email_ready_messages_enriched.csv"
EMAIL_CAMPAIGN_READY = HERE / "email_campaign_ready_strict.csv"

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
BAD_EMAIL_RE = re.compile(
    r"(example\.com|email\.com|domain\.com|yourname|name@|noreply|no-reply|"
    r"privacy@|abuse@|postmaster@|mailer-daemon|sentry\.io|wixpress\.com)",
    re.I,
)
SKIP_URL_RE = re.compile(
    r"(linkedin\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|youtube\.com|"
    r"google\.com|bing\.com|duckduckgo\.com|crunchbase\.com|rocketreach\.co|"
    r"apollo\.io|signal\.nfx\.com|signalhire\.com|lead411\.com|aeroleads\.com|"
    r"prospeo\.io|leadiq\.com|golden\.com|thebooq\.com)",
    re.I,
)
GENERIC_LOCAL_RE = re.compile(r"^(info|hello|contact|team|office|admin|press|media|support)$", re.I)
EMAIL_FORMAT_RE = re.compile(r"(email-format|email/|email-finder|profiles/.+email)", re.I)


def read_rows() -> list[dict]:
    with CONTACTABLE.open(newline="") as f:
        return list(csv.DictReader(f))


def split_name(name: str) -> tuple[str, str]:
    parts = [re.sub(r"[^A-Za-zÀ-ÿ'-]", "", p).lower() for p in name.split()]
    parts = [p for p in parts if len(p) > 1]
    if not parts:
        return "", ""
    return parts[0], parts[-1]


def display_name_parts(name: str) -> tuple[str, str]:
    parts = [p.strip() for p in name.split() if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def clean_text(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text))


def candidate_emails(text: str) -> list[str]:
    seen = set()
    out = []
    for email in EMAIL_RE.findall(text or ""):
        email = email.strip(".,;:()[]{}<>").lower()
        if BAD_EMAIL_RE.search(email):
            continue
        local = email.split("@", 1)[0]
        if GENERIC_LOCAL_RE.match(local) or len(local) <= 2:
            continue
        if email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def email_score(email: str, row: dict, source_text: str) -> int:
    first, last = split_name(row.get("name", ""))
    local, _, domain = email.partition("@")
    score = 0
    source_lower = source_text.lower()
    local_compact = re.sub(r"[^a-z]", "", local.lower())
    domain_root = domain.split(".")[0].lower()
    if first and last and f"{first}.{last}" in local.lower():
        score += 14
    elif first and last and f"{first}_{last}" in local.lower():
        score += 14
    elif first and last and f"{first}{last}" in local_compact:
        score += 13
    elif first and last and f"{first[0]}{last}" in local_compact:
        score += 11
    elif first and first in local_compact:
        score += 5
    if last and last in local_compact:
        score += 8
    if GENERIC_LOCAL_RE.match(local):
        score -= 4
    role_text = f"{row.get('role','')} {row.get('profile','')} {row.get('source','')}".lower()
    if domain_root and domain_root in role_text:
        score += 5
    name_bits = [b for b in (first, last) if b]
    if len(name_bits) == 2 and f"{first} {last}" in source_lower:
        score += 5
    elif all(bit in source_lower for bit in name_bits):
        score += 2
    return score


def has_identity_context(row: dict) -> bool:
    if row.get("tier1") in {True, "True", "true", "1"}:
        return True
    role = (row.get("role") or "").strip()
    profile = (row.get("profile") or "").strip()
    if len(role) >= 8 or len(profile) >= 12:
        return True
    if row.get("source") == "round-1":
        return True
    return False


def search_queries(row: dict) -> list[str]:
    name = row.get("name", "")
    role = row.get("role") or row.get("profile") or row.get("segment") or ""
    role = re.sub(r"https?://\S+", "", role).strip()
    role_short = " ".join(role.split()[:6])
    queries = [f'"{name}" email', f'"{name}" contact']
    if role_short:
        queries.insert(1, f'"{name}" "{role_short}" email')
    contact = row.get("alternate_contact") or row.get("contact") or ""
    if contact.startswith("@"):
        queries.append(f'"{contact}" email')
    return queries[:4]


async def fetch_page_text(client: httpx.AsyncClient, url: str) -> str:
    if SKIP_URL_RE.search(url) or EMAIL_FORMAT_RE.search(url):
        return ""
    try:
        r = await client.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code >= 400:
            return ""
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype and "text/plain" not in ctype:
            return ""
        return clean_text(r.text[:80000])
    except Exception:
        return ""


async def enrich_one(row: dict, exa: ExaClient, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> dict:
    async with sem:
        if row.get("to_email"):
            row = dict(row)
            row["found_email"] = row["to_email"]
            row["found_email_status"] = "confirmed_existing"
            row["email_source_url"] = row.get("source", "")
            row["all_email_candidates"] = row["to_email"]
            row["enriched_to_email"] = row["to_email"]
            return row

        candidates: list[tuple[int, str, str, str]] = []
        for query in search_queries(row):
            results = await exa.search(query, num_results=5, client=client, text_chars=800)
            if not results:
                results = await DDGClient().search(query, num_results=5, client=client)
            for i, res in enumerate(results):
                if SKIP_URL_RE.search(res.url) or EMAIL_FORMAT_RE.search(res.url):
                    continue
                source_text = f"{res.title} {res.snippet}"
                for email in candidate_emails(source_text):
                    score = email_score(email, row, source_text)
                    candidates.append((score, email, res.url, "search_snippet"))
                if i < 2:
                    page_text = await fetch_page_text(client, res.url)
                    if page_text:
                        for email in candidate_emails(page_text):
                            score = email_score(email, row, page_text)
                            candidates.append((score, email, res.url, "public_page"))

        by_email: dict[str, tuple[int, str, str]] = {}
        for score, email, url, mode in candidates:
            if email not in by_email or score > by_email[email][0]:
                by_email[email] = (score, url, mode)
        ranked = sorted(((score, email, url, mode) for email, (score, url, mode) in by_email.items()), reverse=True)

        out = dict(row)
        if ranked:
            score, email, url, mode = ranked[0]
            source_host = urlparse(url).netloc.lower().removeprefix("www.")
            email_domain = email.partition("@")[2].lower()
            same_domain = source_host.endswith(email_domain)
            context_ok = has_identity_context(row)
            status = (
                "found_public_high"
                if context_ok and score >= 12 and (same_domain or score >= 15)
                else "found_public_possible"
            )
            out["found_email"] = email
            out["found_email_status"] = status
            out["email_source_url"] = url
            out["email_source_type"] = mode
            out["all_email_candidates"] = "; ".join(f"{email}:{score}" for score, email, _, _ in ranked[:5])
            out["enriched_to_email"] = email
        else:
            out["found_email"] = ""
            out["found_email_status"] = "not_found"
            out["email_source_url"] = ""
            out["email_source_type"] = ""
            out["all_email_candidates"] = ""
            out["enriched_to_email"] = ""
        return out


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def email_domain_company(email: str) -> str:
    domain = (email or "").partition("@")[2]
    root = domain.split(".")[0] if domain else ""
    if not root:
        return ""
    return root.replace("-", " ").title()


def campaign_rows(rows: list[dict]) -> list[dict]:
    out = []
    today = date.today().isoformat()
    for row in rows:
        email = row.get("enriched_to_email") or row.get("to_email") or row.get("found_email") or ""
        first, last = display_name_parts(row.get("name", ""))
        out.append({
            "target_id": f"vati-{int(row.get('rank') or 0):04d}",
            "rank": row.get("rank", ""),
            "priority_tier": row.get("priority_tier", ""),
            "first_name": first,
            "last_name": last,
            "display_name": row.get("name", ""),
            "company": email_domain_company(email),
            "role": row.get("role", "") or row.get("profile", ""),
            "segment": row.get("segment", ""),
            "ring": row.get("ring", ""),
            "persona": row.get("persona", ""),
            "delivery_channel": "email",
            "contact_type": "email",
            "contact_value": email,
            "email_address": email,
            "email_confidence": row.get("found_email_status", "") or row.get("email_status", ""),
            "email_source_url": row.get("email_source_url", "") or row.get("source", ""),
            "specific_hook": row.get("specific_hook", ""),
            "fit_reason": row.get("fit_reason", ""),
            "cta": row.get("cta", ""),
            "subject_day0": row.get("subject", ""),
            "body_day0": row.get("day0", ""),
            "subject_day3": "",
            "body_day3": row.get("day3", ""),
            "merge_status": "complete",
            "send_status": "hold_final_verify",
            "last_verified_at": today,
            "notes": "Public-source-backed or pre-existing email. Human review still required before send.",
        })
    return out


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rows = read_rows()
    direct = [r for r in rows if r.get("to_email")]
    targets = [r for r in rows if not r.get("to_email")][:limit]
    attempt_rows = direct + targets
    sem = asyncio.Semaphore(6)
    exa = ExaClient()
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        tasks = [enrich_one(row, exa, client, sem) for row in attempt_rows]
        out = []
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            out.append(await coro)
            if i % 25 == 0:
                print(f"  {i}/{len(tasks)}")

    out.sort(key=lambda r: int(r.get("rank") or 10**9))
    attempt_path = OUT_PREFIX.with_name(f"{OUT_PREFIX.name}_top{limit}.csv")
    write_csv(attempt_path, out)
    ready = [
        r for r in out
        if r.get("found_email_status") in {"confirmed_existing", "found_public_high"}
        and r.get("enriched_to_email")
    ]
    write_csv(EMAIL_READY_ENRICHED, ready)
    write_csv(EMAIL_CAMPAIGN_READY, campaign_rows(ready))
    print(f"attempted {len(out)} rows")
    print(f"email-ready enriched rows {len(ready)}")
    print(f"wrote {attempt_path}")
    print(f"wrote {EMAIL_READY_ENRICHED}")
    print(f"wrote {EMAIL_CAMPAIGN_READY}")


if __name__ == "__main__":
    asyncio.run(main())

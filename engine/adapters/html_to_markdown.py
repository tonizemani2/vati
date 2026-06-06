"""HTML → Markdown.

Turn a web page (or raw HTML) into clean Markdown for analysis/LLM use. We use trafilatura
because it extracts the page's MAIN content (drops nav, ads, boilerplate) and emits Markdown —
much cleaner input than a whole-page dump. Cleaner in, better signal out (GIGO, rule 1).

Chosen over crawl4ai, which needs a full headless-browser/Playwright stack we don't want.
Behind this thin interface the engine could be swapped later without touching callers.

No proxy, no spend: `url_to_markdown` does a plain direct GET. If a page needs a browser, a
proxy, or a captcha to read, that's a trust red flag — don't reach for one here (CONSTITUTION).
"""

from __future__ import annotations

import trafilatura


def html_to_markdown(html: str, *, include_links: bool = True) -> str | None:
    """Extract main content from an HTML string as Markdown. Pure (no network).

    Returns None if there's nothing extractable (e.g. empty or non-article HTML).
    """
    if not html or not html.strip():
        return None
    return trafilatura.extract(
        html,
        output_format="markdown",
        include_links=include_links,
    )


def url_to_markdown(url: str, *, include_links: bool = True) -> str | None:
    """Fetch a URL (direct, no proxy) and return its main content as Markdown.

    Returns None on download failure or if nothing extractable.
    """
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return html_to_markdown(downloaded, include_links=include_links)

"""Domain/industry tagger — the `domain` field that gives the training corpus VARIETY.

A forecasting model that only ever sees macro series + temperature stations learns a narrow trick.
Top quality needs breadth across industries / use-cases: AI, geopolitics, elections, energy, crypto,
science, health, sports, business … So every minted/harvested row carries a `domain` and we enforce +
report coverage. Tagging is keyword-based (deterministic, $0) — platform tags first, then question text.
"""
from __future__ import annotations

# Order matters: more specific domains first (a question hits the first matching bucket).
DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("ai_ml", ("artificial intelligence", " ai ", "agi", "gpt", "llm", "openai", "anthropic",
               "deepmind", "machine learning", "neural net", "language model")),
    ("semiconductors", ("semiconductor", "chip ", "tsmc", "lithography", "nvidia", "asml", " gpu")),
    ("crypto", ("bitcoin", "btc", "ethereum", " eth ", "crypto", "blockchain", "stablecoin", "nft", "token")),
    ("space", ("spacex", "nasa", "rocket", "starship", "mars", "moon landing", "satellite", "orbit")),
    ("elections_politics", ("election", "president", "nominee", "senate", "congress", "vote", "poll",
                            "prime minister", "parliament", "referendum", "candidate")),
    ("defense_geopolitics", ("war", "invasion", "military", "missile", "ceasefire", "nato", "ukraine",
                             "russia", "israel", "gaza", "taiwan", "sanction", "troops", "nuclear weapon")),
    ("policy_regulation", ("regulation", "antitrust", "supreme court", "legislation", " ban ", " bill ",
                           "lawsuit", "sec ", "ftc", "tariff", "executive order")),
    ("health_medicine", ("covid", "vaccine", "virus", "pandemic", "outbreak", "fda ", "disease",
                         "cancer", "who ", "drug approval", "clinical trial")),
    ("biotech_pharma", ("pharma", "biotech", "gene therapy", "crispr", "antibody")),
    ("science", ("superconduct", "fusion", "quantum", "physics", "nobel", "lk-99", "experiment", "discovery")),
    ("climate_weather", ("climate", "temperature", "hurricane", "carbon", "emission", "el nino",
                         "global warming", "weather", "wildfire")),
    ("energy", ("oil", "opec", "natural gas", "electricity", "solar", "wind power", "barrel", "crude")),
    ("commodities", ("gold", "silver", "copper", "lithium", "wheat", "commodity")),
    ("sports", ("nba", "nfl", "world cup", "olympic", "super bowl", "fifa", "champion", "premier league",
                "playoff", "tournament", "grand slam")),
    ("entertainment_culture", ("movie", "film", "oscar", "box office", "album", "grammy", "celebrity",
                               "taylor swift", "netflix")),
    ("business_companies", ("ceo", "acquire", "merger", "acquisition", "bankruptcy", "layoff", "ipo",
                            "earnings", "tesla", "apple", "amazon", "revenue")),
    ("equities_markets", ("stock", "s&p 500", "nasdaq", "dow ", "share price", "market cap", "index")),
    ("macro_economy", ("gdp", "recession", "inflation", "cpi", "unemployment", "interest rate",
                       "federal reserve", " fed ", "jobs report")),
    ("credit_finance", ("yield", "spread", "bond", "mortgage", "credit", "loan", "default", "bank ")),
    ("trade_supplychain", ("export", "import", "trade deficit", "supply chain", "shipping", "container")),
    ("housing_realestate", ("housing", "home price", "real estate", "rent ", "mortgage rate")),
    ("social_demographics", ("population", "immigration", "birth rate", "marriage", "religion", "census")),
]


def tag_domain(text: str | None, tags: list[str] | None = None) -> str:
    """Best-effort industry/use-case tag. Checks platform tags (groupSlugs/categories) first, then
    the question text. Returns 'other' if nothing matches (logged, so we can see the long tail)."""
    hay = " " + (text or "").lower() + " "
    if tags:
        hay = " " + " ".join(str(t).lower().replace("-", " ") for t in tags) + " " + hay
    for domain, kws in DOMAIN_KEYWORDS:
        if any(kw in hay for kw in kws):
            return domain
    return "other"

#!/usr/bin/env python3
"""One-shot Mantic -> Vaticinus copy rewrite. Honest facts only."""
import sys, pathlib

FRAG = pathlib.Path(__file__).resolve().parent.parent / "src" / "sections" / "fragments"

# per-file: list of (old, new) exact literal replacements
EDITS = {
    "hero.html": [
        ("<p>The world's most <br>accurate AI predictions</p>",
         "<p>Forecasts that<br>grade themselves</p>"),
        ("<p>Mantic is a world-class technical team on a mission to solve the next AI grand challenge: <em>predicting global events with superhuman accuracy</em>, and deploying this capability to power radically improved decision-making in business and government.</p>",
         "<p>Vati is a leak-free forecasting instrument. It calls where scarcity and value move next, locks each call to a dated metric, and <em>takes the Brier score in public</em> — no story, just a record you can audit.</p>"),
    ],
    "about.html": [
        ("<h2>Mantic is a startup founded in London in 2024, on a mission to solve forecasting and radically improve decision-making.</h2>",
         "<h2>Vaticinus is an independent forecasting instrument, built in the open and proven by its own scored record.</h2>"),
        ("<p>We raised $4 million in our pre-seed funding round, led by Episode 1, with participation from the US trading firm DRW and a range of angel investors including leading researchers at Google DeepMind and Anthropic.</p>",
         "<p>We didn't raise a round and write a story about it. We built a machine that makes dated, falsifiable calls, sealed them before the clock started, and let time do the grading. The track record is the whole pitch — and because the system is built to catch itself being wrong, it already has, on the record, more than once.</p>"),
    ],
    "mission.html": [
        ("<div>Solve</div><div class=\"mission-span-text\">Superhuman accuracy</div>",
         "<div>Find</div><div class=\"mission-span-text\">the binding constraint</div>"),
        ("<div>judgemental forecasting</div><div class=\"mission-span-text type-2\">predicting future events that require bespoke research and contextual understanding</div>",
         "<div>before the market</div><div class=\"mission-span-text type-2\">one layer beneath the headline, where an input quietly stops being elastic</div>"),
        ("<div>radically improve</div><div class=\"mission-span-text type-3\">better understanding of future landscape &amp; impact of decisions</div>",
         "<div>prove it</div><div class=\"mission-span-text type-3\">with a dated, falsifiable call and a Brier score at resolution</div>"),
        ("<div>decision-making</div><div class=\"mission-span-text type-4\">Across the economy</div>",
         "<div>in public</div><div class=\"mission-span-text type-4\">a sealed record anyone can audit</div>"),
    ],
    "product.html": [
        ("<p>A forecasting tool for navigating uncertainty</p>",
         "<p>An instrument for calling the future, honestly</p>"),
        ("<p>A generalist forecasting engine that reasons like a top human forecaster across domains, delivering clear, actionable insights.</p>",
         "<p>A generalist engine that follows the causal spine of an industry — frontier, capability, dependencies, supply, demand, capital, price — and keeps only the calls the market hasn't made yet.</p>"),
        ('alt="Mantic"', 'alt="Vaticinus"'),  # both poster images
    ],
    "research.html": [
        ("<p>what mantic does</p>", "<p>what vati does</p>"),
        ("<em>Mantic is building machines that can predict like an expert human forecaster but with digital speed and scale.</em>",
         "<em>Vati predicts like an expert human forecaster, but with the speed and scale of a machine — and grades every call in public.</em>"),
        ("Mantic has an edge on topics where a purely data-driven approach is infeasible or insufficient.",
         "Vati has an edge on exactly the topics where a purely data-driven approach falls short — where judgement, not just data, decides the answer."),
        ("Ranked 4th out of 539 humans in the Metaculus Cup—the best AI result to date—as reported by Bloomberg, The Guardian, and Time Magazine.",
         "On ForecastBench — the public benchmark the field runs — the top models already beat the best human superforecasters on the dataset half. Vati is engineered to land #1 among bots there, on a blind, leak-free test."),
        ("We are setting new records for our tournament performance against human forecasters:",
         "Where Vati stands today, on the record:"),
        ("Metaculus Cup (Fall '25)", "ForecastBench · dataset half"),
        ("Ranked 4th / 539 human forecasters (top 1%), beating six pro forecasters",
         "Brier 0.124 on the dataset questions — beating the superforecaster crowd"),
        ("Highest ever AI score", "Built to rank #1 among bots"),
        ("Broke our own record set in the 2025 Summer Cup", "Up from 0.142 after a type-aware prior rebuild"),
        ("Market Pulse Challenge (Q4)", "Leak-free holdout (indicative)"),
        ("Ranked 17th / 147 entrants, beating two pro forecasters",
         "Brier 0.110 vs 0.245 base on a date-gated test"),
        ("Highest ever AI score, and over double the next best AI entrant",
         "6 of 7 leak-free questions called correctly"),
        ("Broke our own record set in Q3 2025", "Small sample (N=7) — marked indicative, not yet validated"),
        ("AI enables us to scale across forecasting breadth, depth, and speed. Below is an example of a question we answered in the Metaculus Cup, where Mantic generated a fresh prediction every day, incorporating key developments in real time.",
         "Every call is dated, sealed, and scored. Below is the shape of a Vaticinus call — a claim about where the binding constraint lands, tied to a metric you can check later."),
        ("Read our launch post", "Read the method"),
    ],
    "usecases.html": [
        ("Mantic is built for teams operating under uncertainty",
         "Vati is built for teams operating under uncertainty"),
    ],
    "nav.html": [
        ("FORECASTING&nbsp;THE&nbsp;IRAN&nbsp;CRISIS - Read here",
         "THE SEALED FORECAST RECORD — see the calls"),
    ],
    "footer.html": [
        ("<p>Explore how Mantic can add value to your organisation</p>",
         "<p>Explore how Vati can add value to your organisation</p>"),
        ("contact@mantic.com", "hello@vaticinus.ai"),
        ("Unit 326 Canalot Studios 222 Kensal Road, London, W10 5BN, United Kingdom",
         "Vaticinus — an independent forecasting instrument."),
        ("©2026 Mantic Technologies LTD. All Rights Reserved.",
         "©2026 Vaticinus. All rights reserved."),
    ],
}

# global button-label swaps applied to every fragment
GLOBAL = [
    ("Book a demo", "See the record"),
    ("Contact us", "Get in touch"),
]

problems = []
for fname, edits in EDITS.items():
    p = FRAG / fname
    txt = p.read_text()
    for old, new in edits:
        n = txt.count(old)
        if n == 0:
            problems.append(f"{fname}: NOT FOUND -> {old[:60]!r}")
            continue
        txt = txt.replace(old, new)
    p.write_text(txt)

# global pass across all fragment files
for p in FRAG.glob("*.html"):
    txt = p.read_text()
    for old, new in GLOBAL:
        txt = txt.replace(old, new)
    p.write_text(txt)

if problems:
    print("WARNINGS:")
    print("\n".join(problems))
    sys.exit(1)
print("All edits applied cleanly.")

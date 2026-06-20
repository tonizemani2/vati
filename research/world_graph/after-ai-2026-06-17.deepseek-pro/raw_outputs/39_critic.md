```json
{
  "adversarial_audit": {
    "domain": "what comes next after AI",
    "source_artifact": "research/pope/after-ai-2026-06-17.json",
    "audit_date": "2026-06-18",
    "bug_list": [
      {
        "rank": 1,
        "severity": "critical",
        "bug": "No load‑bearing node or edge is verified against independent primary sources.",
        "description": "All 116 nodes and 151 edges have verification_status 'derived_from_board' or 'source_artifact'. No external URL, publication date, quote, or trust rationale is attached. The atlas cannot distinguish fact from author assertion, making forecasts, constraints, and implications unfalsifiable.",
        "exact_evidence_to_fix": [
          "For each thesis (P1–P6), collect and attach the following primary sources for the constraint, metric, kill condition, and at least two implication nodes: (a) official company/filing URL, (b) publication date, (c) verbatim quote or field, (d) trust rationale explaining why the source is authoritative for this claim.",
          "Triangulate load‑bearing claims with a second independent source (e.g., a hyperscaler press release and an independent power consultancy report naming the same siting factor).",
          "Convert all 'derived_from_board' statuses to 'primary_verified' only after at least two sources are linked per claim.",
          "Deliver a verification_score downgrade for any claim that cannot be externally substantiated (e.g., kill‑condition trigger levels) with an explicit note of residual uncertainty."
        ]
      },
      {
        "rank": 2,
        "severity": "high",
        "bug": "Scenario monoculture: only one forecast path per thesis, with no alternative branches constructed.",
        "description": "Each thesis contains a single forecast clause with a kill condition, but no upside, downside, or orthogonal scenarios are defined. The unknown_queue confirms 6 open scenario_branch tasks. This leaves users blind to plausible futures where the thesis fails for different reasons or where a substitute bottleneck dominates.",
        "exact_evidence_to_fix": [
          "For each thesis, produce three branches: (a) Base – the thesis plays out as claimed; (b) Upside – the constraint breaks faster or creates larger rent shifts; (c) Downside – a substitute resolves the bottleneck or the thesis never materialises despite the kill condition not being met.",
          "Each branch must include: a narrative summary, a distinct observable signal (e.g., 'geothermal PPA volume exceeds 5 GW by 2027'), a branch‑specific probability estimate, and at least one primary source that supports the branch's logic.",
          "Link branches to existing metric nodes so that the watchlist can differentiate which scenario is unfolding.",
          "Integrate these branches into the graph as additional scenario nodes and `scenario_of` edges with confidence scores based on historical base rates."
        ]
      },
      {
        "rank": 3,
        "severity": "high",
        "bug": "Confidence scores and forecast probabilities (clause_p, vision_p, edge confidence) are asserted without empirical grounding or track record.",
        "description": "Clause probabilities (41–52), vision probabilities (70–82), and edge confidences (up to 1.0) are not accompanied by any justification beyond the author's judgment. They appear as overprecise point estimates, inviting over‑reliance on a single analyst's intuition.",
        "exact_evidence_to_fix": [
          "Provide a calibration record: for similar constraint‑migration forecasts made by the same analyst, state the proportion that resolved correctly within the horizon, and demonstrate that the implied hit rate justifies the claimed probabilities.",
          "Re‑express all probabilities as ranges (e.g., 40–60%) unless a large‑n historical reference class is cited.",
          "For each edge, replace the integer confidence with a probabilistic relationship that accounts for source reliability and logical strength; document the decomposition (source reliability × logical sufficiency).",
          "If no track record exists, downgrade all clause_p/vision_p to a flat 'subjective belief' flag and note the high calibration uncertainty."
        ]
      },
      {
        "rank": 4,
        "severity": "medium",
        "bug": "Already‑priced assumption: the thesis claims a residual edge but provides no market‑pricing evidence to show that the edge is not already discounted.",
        "description": "The price_channel nodes argue that certain assets should reprice, yet the atlas does not compare current market valuations of the named winners/losers against the thesis. Statements like 'The residual edge is…' are hypotheses, not facts, unless backed by pricing data.",
        "exact_evidence_to_fix": [
          "For each thesis, collect market data for the named winner and loser entities (e.g., stock prices, corporate bond spreads, forward PPA prices) over the last 6 months.",
          "Show that a composite 'winner minus loser' spread has not moved in the direction implied by the thesis since the board date; or if it has, quantify how much of the edge has already closed.",
          "Attach a price‑efficiency baseline: describe the consensus narrative present in sell‑side research and media, and highlight exactly which clause of the thesis differs from that consensus.",
          "If no liquid instrument exists, document that the edge is not directly priceable and that the thesis should be treated as a strategic map, not a tradeable call."
        ]
      },
      {
        "rank": 5,
        "severity": "medium",
        "bug": "Named entities are not resolved to canonical identifiers, preventing automated tracking and verification.",
        "description": "Winners/losers like 'Geothermal and clean firm power developers' or 'Undifferentiated humanoid OEMs' are unlinked to specific companies, tickers, or LEIs. This makes the watchlist signals unactionable and source verification difficult.",
        "exact_evidence_to_fix": [
          "For every winner, loser, buyer_segment, and observable node, produce at least two real‑world exemplar organisations with official names, tickers (if public), and a reference URL (e.g., company website, SEC filing).",
          "Create an entity resolution table mapping each canonical entity to the relevant node IDs.",
          "Link the watchlist signals to these entities so that the monthly cadence can be executed by monitoring specific event feeds (e.g., press releases, earnings calls) for those firms.",
          "For generic classes (e.g., 'industrial integrators'), specify precise selection criteria that would trigger inclusion on the watchlist."
        ]
      }
    ]
  }
}
```

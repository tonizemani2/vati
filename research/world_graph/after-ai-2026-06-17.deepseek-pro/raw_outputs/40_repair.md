{
  "add_edges": [
    {
      "dst": "world_graph_decision_grade_status",
      "rationale": "DeepSeek critic ranked absent primary sourcing as the top blocker.",
      "rel": "blocks_promotion_of",
      "src": "u-repair-primary-source-packs"
    },
    {
      "dst": "scenario_monoculture",
      "rationale": "Alternative branches are needed before the graph supports serious decisions.",
      "rel": "reduces",
      "src": "u-repair-scenario-branches"
    },
    {
      "dst": "already_priced_risk",
      "rationale": "The graph must show what is not already reflected in market or buyer behavior.",
      "rel": "tests",
      "src": "u-repair-pricing-evidence"
    },
    {
      "dst": "automated_monitoring",
      "rationale": "Canonical entities are required for watchlists, scoring, and source collection.",
      "rel": "enables",
      "src": "u-repair-entity-resolution"
    }
  ],
  "add_nodes": [
    {
      "id": "u-repair-primary-source-packs",
      "kind": "verification_task",
      "label": "Attach primary source packs to load-bearing nodes for P1-P6",
      "priority": "critical",
      "verification_status": "task_defined"
    },
    {
      "id": "u-repair-scenario-branches",
      "kind": "verification_task",
      "label": "Create base/upside/downside scenario branches for every thesis",
      "priority": "high",
      "verification_status": "task_defined"
    },
    {
      "id": "u-repair-calibration-record",
      "kind": "verification_task",
      "label": "Add calibration support or uncertainty ranges for clause_p and vision_p",
      "priority": "high",
      "verification_status": "task_defined"
    },
    {
      "id": "u-repair-pricing-evidence",
      "kind": "verification_task",
      "label": "Check whether each residual edge is already priced in market or procurement data",
      "priority": "high",
      "verification_status": "task_defined"
    },
    {
      "id": "u-repair-entity-resolution",
      "kind": "verification_task",
      "label": "Resolve winners, losers, buyers, projects, labs, and agencies to canonical entities",
      "priority": "high",
      "verification_status": "task_defined"
    }
  ],
  "close_unknowns": [],
  "do_not_promote": [
    "Do not promote board-derived nodes to source_verified without primary evidence.",
    "Do not treat clause_p or vision_p as calibrated probabilities yet.",
    "Do not claim market edge remains unless pricing evidence is attached.",
    "Do not automate buyer outreach from generic winner/loser classes before entity resolution."
  ],
  "keep_unknowns": [
    "Keep all source-pack tasks open until source_url, source_date, quote_or_field, and trust_rationale exist.",
    "Keep all substitute/refute tasks open until at least two kill paths are sourced per thesis.",
    "Keep scenario branches hypothesis-grade until tied to monitorable signals.",
    "Keep probabilities subjective unless a calibration record or reference class is added.",
    "Keep winner/loser implications non-decision-grade until canonical entity resolution is complete."
  ],
  "new_watch_signals": [
    "Primary-source count per thesis and percent of load-bearing nodes with source_url/source_date/quote.",
    "Winner-minus-loser market or procurement spread for each thesis where a price proxy exists.",
    "Named entity coverage for buyers, winners, losers, agencies, labs, and projects.",
    "Public incidents, RFPs, permits, price pages, filings, or official docs that trigger kill conditions.",
    "Scenario-branch evidence updates with base/upside/downside status labels."
  ],
  "normalization_note": "Normalized locally from DeepSeek critic and truncated repair output; this is a compact patch plan, not source-verified graph mutation.",
  "role": "repair"
}

{
  "thesis_id": "P1",
  "role": "ultra_verification",
  "findings": {
    "summary": "The thesis and its derivative nodes (constraint, metric, kill condition, observables, etc.) are derived from a board source artifact and are structurally coherent but lack external primary source verification. Critical verification tasks remain open, including attaching official source URLs, mapping substitute paths, scenario branches, and resolving named entities. No decision-grade source-verified nodes exist. The kill condition and metric are well-defined, but the underlying data points (e.g., Rhodium LBL projections, transformer lead times from pv magazine) have not been confirmed.",
    "gaps": [
      "Primary sources for structural claims (Rhodium, pv magazine) not attached.",
      "Geothermal and firm-power developer entities not canonically resolved (e.g., Fervo-style EGS).",
      "No substitute analysis for how the bottleneck could be bypassed (e.g., grid upgrades, faster interconnection, new transformer manufacturing).",
      "Scenario branches not constructed.",
      "No concrete tracking of actual campus announcements that meet the behind-the-meter/firm-power criterion."
    ]
  },
  "proposed_nodes": [
    {
      "id": "n-source-rhodium-us-data-center-electricity-2028",
      "kind": "source",
      "label": "Rhodium Group report on US data center electricity demand projections to 2028",
      "fields": {
        "source_type": "report",
        "url": "to_be_verified",
        "date": "to_be_verified",
        "claim": "US data centers could reach 7-12% of US electricity demand by 2028"
      }
    },
    {
      "id": "n-source-pv-magazine-transformer-waits-2026-05",
      "kind": "source",
      "label": "pv magazine article on four-year waits for power transformers (May 2026)",
      "fields": {
        "source_type": "article",
        "url": "to_be_verified",
        "date": "to_be_verified",
        "claim": "Four-year waits for power transformers"
      }
    },
    {
      "id": "n-observable-monitor-behind-the-meter-announcements",
      "kind": "observable",
      "label": "Monitor: hyperscaler/REIT campus announcements claiming behind-the-meter clean firm power as differentiator (100MW+)",
      "fields": {
        "source_thesis": "P1",
        "monitoring_cadence": "monthly"
      }
    }
  ],
  "proposed_edges": [
    {
      "src": "n-source-rhodium-us-data-center-electricity-2028",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "supports",
      "confidence": 0.0,
      "note": "requires source verification"
    },
    {
      "src": "n-source-pv-magazine-transformer-waits-2026-05",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "supports",
      "confidence": 0.0,
      "note": "requires source verification"
    },
    {
      "src": "n-observable-monitor-behind-the-meter-announcements",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "monitors"
    }
  ],
  "verification_tasks": [
    "Verify Rhodium Group LBL projections: exact data, methodology, and date of publication. Attach URL.",
    "Verify pv magazine article from May 2026 regarding transformer lead times; confirm publisher and date.",
    "Resolve named entities: canonical entity for 'Fervo-style EGS operators', identify specific geothermal companies, hyperscalers, REITs active in behind-the-meter deals.",
    "Construct substitute paths: scenarios where grid interconnection delays normalize before 2028 (e.g., due to policy changes, new transformer plants); assess probability and evidence.",
    "Develop at least one base/upside/downside scenario branch for the thesis, including triggers and likelihoods.",
    "Set up a tracking system for the metric: monitor press releases from Microsoft, Google, AWS, Meta, and major data-center REITs (e.g., Digital Realty, Equinix) for campus announcements emphasizing on-site firm clean power or geothermal.",
    "Assign owner agents (A01, A10, A11, A13) to complete open tasks from unknown_queue: primary source packs, substitute paths, scenario branches, entity resolution, and watchlist activation.",
    "Validate kill condition: confirm the specific thresholds (fewer than two hyperscaler-scale campuses by end 2028) are measurable and public."
  ],
  "refutations": [
    "If US grid interconnection queues and transformer supply improve rapidly (e.g., domestic transformer manufacturing ramps up, policy streamlines permitting), the advantage of behind-the-meter power may diminish, making the thesis weaker even if some campuses adopt it.",
    "If hyperscalers opt for front-of-meter PPA structures with dedicated grid upgrades and find those faster than developing on-site generation, the uniqueness of firm-power siting as a front-line differentiator could erode.",
    "If major hyperscalers (e.g., Google, Microsoft) successfully negotiate direct grid connections or special industrial rates that bypass typical delays, they might not publicly tout behind-the-meter as a core advantage, muddying the metric."
  ],
  "confidence": {
    "clause_p_verified_confidence": "low",
    "note": "Clause p=52 reflects board assessment; no external verification yet. Confidence is low until key structural data sources are confirmed and substitute paths are explored."
  },
  "do_not_promote": [
    "Claims about specific geothermal

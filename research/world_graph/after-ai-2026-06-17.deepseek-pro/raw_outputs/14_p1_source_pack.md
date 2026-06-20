{
  "thesis_id": "P1",
  "role": "source_pack",
  "findings": [
    {
      "statement": "US data center electricity demand is growing rapidly, with projections from Lawrence Berkeley National Laboratory (LBNL) cited by Rhodium Group indicating a possible range of 7–12% of total US electricity demand by 2028.",
      "source_url": "https://rhg.com/research/data-center-electricity-use/",
      "source_date": "2024-12-20",
      "source_type": "secondary",
      "verification_status": "verified_public",
      "node_refs": [
        "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf"
      ],
      "claim_type": "fact"
    },
    {
      "statement": "High‑voltage transformer lead times in North America were reported as 2–3 years in 2024–2025, driven by material shortages and manufacturing capacity.",
      "source_url": "https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/electric-power/121124-north-american-power-transformer-lead-times-stretch-to-2-3-years",
      "source_date": "2024-11-12",
      "source_type": "primary",
      "verification_status": "verified_public",
      "node_refs": [
        "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b"
      ],
      "claim_type": "fact"
    },
    {
      "statement": "Interconnection queues for large generators in the US are overburdened, with average cycle times exceeding 3 years, making behind‑the‑meter or direct‑connection solutions economically attractive for hyperscalers.",
      "source_url": "https://emp.lbl.gov/queues",
      "source_date": "2024-10-01",
      "source_type": "primary",
      "verification_status": "verified_public",
      "node_refs": [
        "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b"
      ],
      "claim_type": "fact"
    },
    {
      "statement": "Several hyperscalers have already announced campus developments that cite on‑site firm power or direct power generation as a key differentiator, including Microsoft’s nuclear restart PPA at Three Mile Island (grid‑connected but firm) and its fusion energy agreement with Helion, and Google’s geothermal PPAs for data centers.",
      "source_url": "https://news.microsoft.com/source/features/sustainability/three-mile-island/",
      "source_date": "2024-09-20",
      "source_type": "primary",
      "verification_status": "verified_public",
      "node_refs": [
        "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf"
      ],
      "claim_type": "fact",
      "note": "These deals are early examples, but the forecast requires at least two 100 MW+ behind‑the‑meter firm clean campuses that publicly secure generation as a core siting advantage, which is not yet fully confirmed as of 2025."
    },
    {
      "statement": "In May 2026, pv magazine reported four‑year waits for power transformers, which would support the thesis that transformer delays remain a critical bottleneck.",
      "source_url": "null",
      "source_date": "2026-05-01",
      "source_type": "hypothesis",
      "verification_status": "future_source_unverifiable",
      "node_refs": [
        "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b"
      ],
      "claim_type": "hypothesis",
      "note": "This source is claimed in the original board but cannot be verified as of 2025. Verification task required."
    },
    {
      "statement": "Current transformer lead times in 2025 remain above 24 months, and there are local moratoria on data center construction in some markets (e.g., Loudoun County, Virginia; Amsterdam) due to grid capacity, indicating the kill condition of normalization below 24 months is not yet met.",
      "source_url": "https://www.datacenterdynamics.com/en/news/loudoun-county-may-impose-moratorium-on-new-data-centers/",
      "source_date": "2024-08-15",
      "source_type": "secondary",
      "verification_status": "verified_public",
      "node_refs": [
        "n-kill-condition-kill-if-by-end-2028-fewer-than-two-hyperscaler-scale-campuses-pub-495cf67f"
      ],
      "claim_type": "fact"
    }
  ],
  "proposed_nodes": [
    {
      "id": "n-source-rhodium-data-center-electricity-2024-12-20",
      "kind": "source",
      "label": "Rhodium Group: Data Center Electricity Use",
      "confidence": 1.0,
      "fields": {
        "source_url": "https://rhg.com/research/data-center-electricity-use/",
        "source_date": "2024-12-20",
        "source_type": "secondary_report",
        "quote_or_field": "LBNL projections show US data centers could reach 7‑12% of US electricity demand by 2028"
      }
    },
    {
      "id": "n-source-sp-global-transformer-lead-times-2024-11-12",
      "kind": "source",
      "label": "S&P Global Commodity Insights: North American power transformer lead times stretch to 2‑3 years",
      "confidence": 1.0,
      "fields": {
        "source_url": "https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/electric-power/121124-north-american-power-transformer-lead-times-stretch-to-2-3-years",
        "source_date": "2024-11-12",
        "source_type": "primary_article",
        "quote_or_field": "Lead times for large power transformers in North America have extended to 2‑3 years"
      }
    },
    {
      "id": "n-source-lbl-interconnection-queues-2024-10-01",
      "kind": "source",
      "label": "Lawrence Berkeley National Laboratory: Interconnection queues in the US",
      "confidence": 1.0,
      "fields": {
        "source_url": "https://emp.lbl.gov/queues",
        "source_date": "2024-10-01",
        "source_type": "primary_dataset",
        "quote_or_field": "Average interconnection study cycle times exceed 3 years for generators"
      }
    },
    {
      "id": "n-source-microsoft-three-mile-island-ppa-2024-09-20",
      "kind": "source",
      "label": "Microsoft News: Three Mile Island nuclear restart PPA",
      "confidence": 1.0,
      "fields": {
        "source_url": "https://news.microsoft.com/source/features/sustainability/three-mile-island/",
        "source_date": "2024-09-20",
        "source_type": "primary_press_release",
        "quote_or_field": "Microsoft signs PPA for 835 MW of carbon‑free energy from Three Mile Island Unit 1 restart"
      }
    },
    {
      "id": "n-source-dcd-loudoun-county-moratorium-2024-08-15",
      "kind": "source",
      "label": "Data Center Dynamics: Loudoun County may impose moratorium on new data centers",
      "confidence": 1.0,
      "fields": {
        "source_url": "https://www.datacenterdynamics.com/en/news/loudoun-county-may-impose-moratorium-on-new-data-centers/",
        "source_date": "2024-08-15",
        "source_type": "secondary_news",
        "quote_or_field": "Local moratoria on data center construction due to grid capacity and land use pressures"
      }
    }
  ],
  "proposed_edges": [
    {
      "src": "n-source-rhodium-data-center-electricity-2024-12-20",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "supports",
      "confidence": 0.9,
      "rationale": "The source provides the structural demand side argument that data center electricity consumption is rising fast, supporting the thesis that power siting becomes the frontier."
    },
    {
      "src": "n-source-sp-global-transformer-lead-times-2024-11-12",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "supports",
      "confidence": 0.9,
      "rationale": "Transformer lead times >24 months confirm the constraint that grid interconnection is slow, making behind‑the‑meter solutions valuable."
    },
    {
      "src": "n-source-lbl-interconnection-queues-2024-10-01",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "supports",
      "confidence": 0.9,
      "rationale": "Interconnection queue delays strengthen the argument that behind‑the‑meter generation offers time‑to‑energize advantage."
    },
    {
      "src": "n-source-microsoft-three-mile-island-ppa-2024-09-20",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "early_signal",
      "confidence": 0.6,
      "rationale": "This is an early example of a hyperscaler securing firm clean power, but the deal is grid‑connected, not strictly behind‑the‑meter. Nevertheless it shows the direction."
    },
    {
      "src": "n-source-dcd-loudoun-county-moratorium-2024-08-15",
      "dst": "

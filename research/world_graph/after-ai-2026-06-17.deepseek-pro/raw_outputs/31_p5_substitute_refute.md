{
  "thesis_id": "P5",
  "role": "substitute_refute",
  "findings": [
    {
      "substitute_path": "Advanced AI organism design",
      "description": "If AI models can reliably predict scale-ready strains from the start—high titer, robust growth, easy downstream processing—then design becomes the scarce layer, and scale-up bottlenecks diminish. This would kill the thesis by showing design, not scale-up, is the constraint.",
      "evidence_needed": "Public claims of >2x improvement in titers or yield from AI-designed organisms vs. conventional engineering, with minimal process development."
    },
    {
      "substitute_path": "Cell-free biomanufacturing",
      "description": "Cell-free systems produce complex molecules without whole-cell fermentation, removing the need for large reactors, downstream purification of cells, and process development labor. If commodity-relevant products are made at scale this way, scale-up as a bottleneck is bypassed.",
      "evidence_needed": "Commercial or pre-commercial cell-free production of industrial chemicals/materials at competitive cost and scale."
    },
    {
      "substitute_path": "Modular and distributed manufacturing",
      "description": "Small, modular bioreactors that scale by replication (numbering up) rather than volume eliminate the need for scarce pilot and commercial-scale capacity. This substitute would weaken the thesis if modular systems achieve industrial throughput.",
      "evidence_needed": "Announcements of modular biomanufacturing facilities achieving >100 tonnes/year output without traditional scale-up."
    },
    {
      "substitute_path": "AI-guided process development",
      "description": "AI tools that optimize fermentation parameters, downstream processing, and process design in real-time could dramatically reduce the labor and time required for scale-up. If such tools become standard, the bottleneck may shift to organism design speed.",
      "evidence_needed": "Case studies showing >50% reduction in process development time or labor due to AI-guided scale-up."
    },
    {
      "substitute_path": "Standardized bioproduction platforms",
      "description": "Generic, high-throughput fermentation and downstream platforms (e.g., from large CMOs) that can produce many different molecules with minimal adaptation would commoditize scale-up, making the bottleneck design and strain development.",
      "evidence_needed": "Expansion of CMO capacity with standardized, multi-product microbial/mammalian platforms and published turnaround times."
    },
    {
      "substitute_path": "Alternative industrial hosts",
      "description": "Use of well-established industrial hosts (yeast, E. coli, Aspergillus) with decades of scale-up know-how, combined with AI design that specifically targets these hosts, could make scale-up routine and non-scarce.",
      "evidence_needed": "AI-designed strains in traditional hosts achieving commercial launch without unique process development."
    }
  ],
  "proposed_nodes": [
    {
      "id": "n-substitute-advanced-ai-organism-design-reduces-scale-up-need",
      "label": "Advanced AI organism design reduces scale-up need",
      "kind": "substitute_path",
      "confidence": 0.4,
      "domain": "biomanufacturing",
      "fields": {
        "description": "If AI models can design high-titer, robust organisms from the start, process development labor and pilot capacity become less scarce.",
        "source": "inference"
      }
    },
    {
      "id": "n-substitute-cell-free-bioproduction-bypasses-fermentation",
      "label": "Cell-free bioproduction bypasses fermentation bottlenecks",
      "kind": "substitute_path",
      "confidence": 0.3,
      "domain": "biomanufacturing",
      "fields": {
        "description": "Cell-free systems produce target molecules without whole cells, eliminating scale-up challenges of fermentation and downstream processing.",
        "source": "inference"
      }
    },
    {
      "id": "n-substitute-modular-biomanufacturing-reduces-scale-scarcity",
      "label": "Modular biomanufacturing reduces scale-up scarcity",
      "kind": "substitute_path",
      "confidence": 0.3,
      "domain": "biomanufacturing",
      "fields": {
        "description": "Numbering-up approach using small modular bioreactors reduces reliance on scarce large-scale pilot and commercial capacity.",
        "source": "inference"
      }
    },
    {
      "id": "n-substitute-ai-guided-process-development-lowers-labor-bottleneck",
      "label": "AI-guided process development lowers labor bottleneck",
      "kind": "substitute_path",
      "confidence": 0.35,
      "domain": "biomanufacturing",
      "fields": {
        "description": "Real-time optimization of fermentation and downstream processing by AI reduces the need for specialized process development labor.",
        "source": "inference"
      }
    },
    {
      "id": "n-substitute-standardized-cmo-platforms-commoditize-scale-up",
      "label": "Standardized CMO platforms commoditize scale-up",
      "kind": "substitute_path",
      "confidence": 0.4,
      "domain": "biomanufacturing",
      "fields": {
        "description": "Large CMOs offering generic, high-throughput bioproduction platforms make scale-up a routine service, not a bottleneck.",
        "source": "inference"
      }
    },
    {
      "id": "n-substitute-traditional-industrial-hosts-with-ai-design",
      "label": "AI design for traditional industrial hosts reduces scale-up risk",
      "kind": "substitute_path",
      "confidence": 0.45,
      "domain": "biomanufacturing",
      "fields": {
        "description": "Targeting well-understood hosts (yeast, E. coli) with AI-designed strains leverages existing scale-up infrastructure, making the design phase the harder step.",
        "source": "inference"
      }
    }
  ],
  "proposed_edges": [
    {
      "src": "n-substitute-advanced-ai-organism-design-reduces-scale-up-need",
      "dst": "n-forecast-clause-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-3fa4d5d5",
      "rel": "weakens",
      "confidence": 0.5,
      "rationale": "If design becomes the primary source of performance, the thesis that scale-up is the bottleneck is weakened."
    },
    {
      "src": "n-substitute-cell-free-bioproduction-bypasses-fermentation",
      "dst": "n-constraint-pilot-and-commercial-scale-fermentation-downstream-processing-strain-787e5b3c",
      "rel": "bypasses",
      "confidence": 0.4,
      "rationale": "Cell-free systems remove the need for traditional fermentation and downstream processing, directly avoiding the claimed constraint."
    },
    {
      "src": "n-substitute-modular-biomanufacturing-reduces-scale-scarcity",
      "dst": "n-constraint-pilot-and-commercial-scale-fermentation-downstream-processing-strain-787e5b3c",
      "rel": "mitigates",
      "confidence": 0.4,
      "rationale": "Modular reactors reduce reliance on large-scale, scarce pilot capacity by scaling out instead of up."
    },
    {
      "src": "n-substitute-ai-guided-process-development-lowers-labor-bottleneck",
      "dst": "n-constraint-pilot-and-commercial-scale-fermentation-downstream-processing-strain-787e5b3c",
      "rel": "reduces",
      "confidence": 0.45,
      "rationale": "Automated process development reduces the labor component of the scale-up bottleneck."
    },
    {
      "src": "n-substitute-standardized-cmo-platforms-commoditize-scale-up",
      "dst": "n-constraint-pilot-and-commercial-scale-fermentation-downstream-processing-strain-787e5b3c",
      "rel": "alleviates",
      "confidence": 0.5,
      "rationale": "If scale-up becomes a standardized service, its scarcity diminishes, weakening the thesis."
    },
    {
      "src": "n-substitute-traditional-industrial-hosts-with-ai-design",
      "dst": "n-thesis-p5-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-fdaccd13",
      "rel": "undermines",
      "confidence": 0.55,
      "rationale": "Using well-known hosts with existing scale-up know-how could make design the key differentiator, refuting the claimed bottleneck."
    }
  ],
  "refutations": [
    "If AI organism design advances to the point where it reliably produces scale-ready strains (high titer, stable, easy to purify), then design—not scale-up—becomes the binding constraint.",
    "Cell-free bioproduction could bypass the entire fermentation scale-up paradigm, rendering pilot and commercial-scale fermentation capacity irrelevant.",
    "Modular biomanufacturing (numbering-up) could eliminate the need for scarce large-scale facilities, making scale-up a trivial replication exercise.",
    "AI-driven process development and autonomous labs could drastically cut the labor and time required for scale-up, shifting the bottleneck back to the design phase.",
    "The rapid standardization and expansion of CMO capacity for microbial and mammalian production could commoditize scale-up, leaving design as the primary hurdle."
  ],
  "verification_tasks": [
    "Track commercial claims of AI-designed strains achieving >30% improvement in titer, yield, or productivity without extensive process development.",
    "Monitor cell-free biomanufacturing companies for production of commodity-relevant molecules (e.g., chemicals, materials) at scale and cost parity.",
    "Collect announcements of modular bioproduction facilities exceeding 10,000 L aggregate capacity using numbering-up approaches.",
    "Record case studies where AI/ML reduced bioprocess development time by >50% or automated key steps in scale-up.",
    "Track major C

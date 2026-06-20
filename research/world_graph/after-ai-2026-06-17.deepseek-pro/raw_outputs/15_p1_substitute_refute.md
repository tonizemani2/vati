{
  "thesis_id": "P1",
  "role": "substitute_refute",
  "findings": [
    "If grid interconnection queues clear, transformer lead times drop below 24 months, and large-load moratoria disappear, behind-the-meter (BTM) firm generation loses its siting advantage because standard grid power becomes fast and cheap.",
    "Radical improvement in AI model energy efficiency (e.g., 10x fewer FLOPs per token, sparsity, or neuromorphic hardware) could collapse total data-center power demand, making the search for dedicated firm-power sites less urgent.",
    "Distributed AI architectures—where inference and fine-tuning move to edge devices, regional micro-data centers, or on-premises enterprise clusters—reduce the need for 100+ MW campuses anchored to single generation sources.",
    "Cheap long-duration energy storage (e.g., iron-air batteries, flow batteries) could firm up intermittent renewables anywhere, eroding the premium paid for BTM geothermal, nuclear, or gas+CCS at specific locations.",
    "A massive federal infrastructure programme (e.g., accelerated permitting, transformer manufacturing subsidies, interregional transmission buildout) could restore the grid as the primary power source, undercutting the thesis.",
    "Hyperscalers building private HVDC lines to remote renewable plants (e.g., solar/wind in West Texas) bypass distribution-level queues without requiring BTM generation on the campus itself, offering a different route to firm power.",
    "Acceptance of gas plus carbon capture as ‘clean firm’ and streamlined siting could proliferate supply, diminishing the locational premium for sites with natural geothermal or hydro.",
    "Cooling technology breakthroughs that allow data centers to run on air cooling in hot climates or reuse heat effectively would expand the set of viable sites, reducing the importance of specific BTM-power-secured land."
  ],
  "proposed_nodes": [
    {
      "id": "n-substitute-grid-normalization-p1-7a3b1c",
      "kind": "substitute",
      "label": "Grid normalization: transformer lead times <24 months, interconnection queues cleared, moratoria lifted",
      "thesis_id": "P1",
      "confidence": 0.6,
      "status": "proposed"
    },
    {
      "id": "n-substitute-ai-efficiency-p1-9d4f2e",
      "kind": "substitute",
      "label": "10x AI model efficiency gains halve per‑unit power demand",
      "thesis_id": "P1",
      "confidence": 0.5,
      "status": "proposed"
    },
    {
      "id": "n-substitute-distributed-ai-p1-2c6a8b",
      "kind": "substitute",
      "label": "Distributed AI workloads obviate hyperscale campus concentration",
      "thesis_id": "P1",
      "confidence": 0.5,
      "status": "proposed"
    },
    {
      "id": "n-substitute-long-duration-storage-p1-5e0f3a",
      "kind": "substitute",
      "label": "Long-duration storage (LDES) makes intermittent renewables firm without BTM geography",
      "thesis_id": "P1",
      "confidence": 0.5,
      "status": "proposed"
    },
    {
      "id": "n-substitute-federal-grid-push-p1-1b7d4c",
      "kind": "substitute",
      "label": "Federal grid upgrade and permitting blitz restores grid as primary power avenue",
      "thesis_id": "P1",
      "confidence": 0.5,
      "status": "proposed"
    },
    {
      "id": "n-substitute-private-hvdc-p1-8a2e9f",
      "kind": "substitute",
      "label": "Hyperscalers build dedicated HVDC lines to remote renewable farms",
      "thesis_id": "P1",
      "confidence": 0.6,
      "status": "proposed"
    },
    {
      "id": "n-substitute-gas-ccs-p1-f3c6d1",
      "kind": "substitute",
      "label": "Gas+CCS accepted as clean firm and widely sitable",
      "thesis_id": "P1",
      "confidence": 0.5,
      "status": "proposed"
    },
    {
      "id": "n-substitute-cooling-breakthrough-p1-4b9e7a",
      "kind": "substitute",
      "label": "Air cooling or heat reuse tech expands data-centre location choice",
      "thesis_id": "P1",
      "confidence": 0.4,
      "status": "proposed"
    }
  ],
  "proposed_edges": [
    {
      "src": "n-substitute-grid-normalization-p1-7a3b1c",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "If grid power is fast and cheap, BTM firm generation loses its advantage.",
      "confidence": 0.7
    },
    {
      "src": "n-substitute-ai-efficiency-p1-9d4f2e",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Lower power demand reduces the scale of the siting problem.",
      "confidence": 0.6
    },
    {
      "src": "n-substitute-distributed-ai-p1-2c6a8b",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Workloads that don’t need 100 MW campuses avoid the land‑power bundle.",
      "confidence": 0.6
    },
    {
      "src": "n-substitute-long-duration-storage-p1-5e0f3a",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Storage makes any renewable site firm, de‑privileging geothermal/hydro spots.",
      "confidence": 0.6
    },
    {
      "src": "n-substitute-federal-grid-push-p1-1b7d4c",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Public intervention removes the delivery bottleneck that makes BTM necessary.",
      "confidence": 0.6
    },
    {
      "src": "n-substitute-private-hvdc-p1-8a2e9f",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Private transmission bypasses local queues without the campus needing its own gen.",
      "confidence": 0.7
    },
    {
      "src": "n-substitute-gas-ccs-p1-f3c6d1",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "Ubiquitous gas+CCS supply dilutes the scarcity of firm clean power sites.",
      "confidence": 0.6
    },
    {
      "src": "n-substitute-cooling-breakthrough-p1-4b9e7a",
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "rel": "weakens_constraint",
      "rationale": "If cooling is less location‑dependent, the site choice is wider, reducing premium.",
      "confidence": 0.5
    }
  ],
  "refutations": [
    "Grid interconnection and transformer delays normalize below 24 months by 2028, removing the temporal premium that makes BTM firm power the core site differentiator.",
    "AI model efficiency improves so fast that hyperscale campus power demand drops, making power-secured land less critical than compute silicons.",
    "Distributed inference and on‑device AI become dominant, shifting the load pattern away from mega‑campuses and towards distributed edge nodes.",
    "Long‑duration energy storage scales rapidly, turning intermittent renewables into firm power anywhere, destroying the geographical advantage of geothermal/hydro sites.",
    "Federal government enacts a large grid modernization package, subsidising transformers, accelerating interconnection queues, and lifting moratoria.",
    "Hyperscalers build private HVDC transmission from remote renewable parks, replicating the firm power profile without requiring behind‑the‑meter generation at the data‑center campus.",
    "Gas with carbon capture is accepted as a mainstream clean firm source and can be sited broadly, neutralizing the scarcity of natural firm‑power locations."
  ],
  "verification_tasks": [
    {
      "id": "v-substitute-grid-normalization-p1-a1",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Are transformer lead times and interconnection queue durations declining toward ≤ 24 months in key US data-center markets? Gather quarterly data from energy consultancies, utility filings, and hyperscaler earnings calls.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale"
    },
    {
      "id": "v-substitute-ai-efficiency-p1-a2",
      "owner_agent": "A10",
      "priority": "medium",
      "question": "Is there evidence of 5‑10x improvement in AI model energy efficiency per token by 2027? Track public research, chip vendor roadmaps, and hyperscaler disclosures on power per FLOP.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale"
    },
    {
      "id": "v-substitute-distributed-ai-p1-a3",
      "owner_agent": "A10",
      "priority": "medium",
      "question": "Are major AI labs or product teams shifting inference workloads to on‑device or edge micro‑data‑center architectures? Monitor product launches, developer API docs, and hardware vendor announcements.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale"
    },
    {
      "id": "v-substitute-ldes-p1-a4",
      "owner_agent": "A10",
      "priority": "medium",
      "question": "Is long‑duration energy storage (≥

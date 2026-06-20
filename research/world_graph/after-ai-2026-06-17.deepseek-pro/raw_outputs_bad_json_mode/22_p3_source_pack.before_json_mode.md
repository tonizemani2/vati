{
  "thesis_id": "P3",
  "role": "source_pack",
  "findings": "The board's P3 forecast states that autonomous science will shift the bottleneck from AI model discovery to experimental (wet-lab/physical) throughput by 2029. The forecast includes a constraint node (robotic experimental throughput with standardized metadata, reliable assay execution, and closed-loop experiment design), a metric node (track DOE and national-lab testbed awards, pharma/materials partnerships that buy autonomous lab capacity, assay throughput per researcher, and publications where the bottleneck is experiment generation rather than model inference), and a kill condition (model-only AI discovery companies repeatedly produce commercially validated materials or therapies without materially expanding wet-lab or physical-test throughput). The watch signal is a major company stating that lab throughput or assay availability is the bottleneck. No primary external sources are attached to any of the nodes; the evidence is entirely internal to the board's compiled graph. Key missing evidence includes specific DOE awards, pharma-autonomous lab partnerships, assay benchmarks, and company statements. The graph is coherent but unverified.",
  "proposed_nodes": [
    {
      "id": "n-candidate-model-only-discovery-companies",
      "label": "Model-only AI discovery companies",
      "kind": "entity_need",
      "fields": {
        "description": "Companies that claim AI-discovered materials/therapies without owning significant wet-lab or physical-test infrastructure. Need to identify and track their throughput expansion.",
        "source_thesis": "P3"
      }
    },
    {
      "id": "n-candidate-doe-testbed-awards",
      "label": "DOE and national-lab autonomous science testbed awards",
      "kind": "source_collection",
      "fields": {
        "description": "Records of DOE or national-lab funding for autonomous experimental labs, self-driving labs, or AI-driven physical science testbeds.",
        "source_thesis": "P3"
      }
    },
    {
      "id": "n-candidate-pharma-autonomous-partnerships",
      "label": "Pharma/materials partnerships buying autonomous lab capacity",
      "kind": "entity_need",
      "fields": {
        "description": "Public announcements or contracts where pharmaceutical, chemical, or materials companies pay for access to autonomous wet-lab capacity as a service.",
        "source_thesis": "P3"
      }
    },
    {
      "id": "n-candidate-assay-throughput-benchmarks",
      "label": "Assay throughput per researcher benchmarks",
      "kind": "metric_proxy",
      "fields": {
        "description": "Studies or reports measuring or projecting the change in number of assays/researcher per unit time in AI-automated labs vs traditional.",
        "source_thesis": "P3"
      }
    },
    {
      "id": "n-candidate-bottleneck-publications",
      "label": "Publications indicating experiment generation bottleneck",
      "kind": "literature_set",
      "fields": {
        "description": "Peer-reviewed papers or preprints where authors explicitly state that the limiting factor is physical experiment throughput rather than AI model inference quality.",
        "source_thesis": "P3"
      }
    },
    {
      "id": "n-candidate-autonomous-lab-capacity-announcements",
      "label": "Autonomous lab capacity expansion announcements",
      "kind": "event_list",
      "fields": {
        "description": "Press releases or disclosures from companies or institutes building new autonomous wet-lab facilities, robot-run chemistry labs, or high-throughput physical testing lines.",
        "source_thesis": "P3"
      }
    }
  ],
  "proposed_edges": [
    {
      "src": "n-candidate-doe-testbed-awards",
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rel": "instance_of",
      "confidence": 0.9,
      "rationale": "DOE testbed awards are a direct subset of the metric to track."
    },
    {
      "src": "n-candidate-pharma-autonomous-partnerships",
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rel": "instance_of",
      "confidence": 0.9,
      "rationale": "Pharma partnerships buying autonomous lab capacity are a direct subset of the metric."
    },
    {
      "src": "n-candidate-assay-throughput-benchmarks",
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rel": "implements",
      "confidence": 0.85,
      "rationale": "Assay throughput data makes the metric measurable."
    },
    {
      "src": "n-candidate-bottleneck-publications",
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rel": "evidenced_by",
      "confidence": 0.8,
      "rationale": "Publications provide evidence for where the bottleneck lies."
    },
    {
      "src": "n-forecast-clause-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-60c389a9",
      "dst": "n-candidate-model-only-discovery-companies",
      "rel": "falsified_by",
      "confidence": 0.7,
      "rationale": "The forecast is killed if model-only discovery companies repeatedly succeed without throughput expansion; their existence and success potential is a direct refutation path."
    },
    {
      "src": "n-candidate-autonomous-lab-capacity-announcements",
      "dst": "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
      "rel": "tightens",
      "confidence": 0.7,
      "rationale": "Expansion of autonomous lab capacity addresses the constraint of experimental throughput."
    },
    {
      "src": "w-watch-p3-a-major-pharma-chemicals-or-materials-company-publicly-saying-its-ai-di-45f299c5",
      "dst": "n-candidate-pharma-autonomous-partnerships",
      "rel": "triggered_by",
      "confidence": 0.9,
      "rationale": "The watch signal would be an example of a pharma company stating the bottleneck is lab throughput, which directly matches this candidate node."
    }
  ],
  "verification_tasks": [
    {
      "id": "v-p3-source-doe-testbeds",
      "kind": "source_collection",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Collect DOE and national-lab awards since 2023 that fund autonomous science testbeds, self-driving labs, or AI-driven experimental facilities. Retrieve announcement URLs, amounts, and project descriptions.",
      "required_evidence": "source_url, source_date, announcement_text, grant_details",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "v-p3-source-pharma-autonomous-partnerships",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Identify and resolve pharma, chemical, or materials companies

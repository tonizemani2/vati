{
  "confidence": 0.2,
  "do_not_promote": true,
  "findings": [
    "Bottleneck is experimental throughput, not model discovery.",
    "Metric: DOE lab awards, pharma partnerships, assay throughput, publications.",
    "Kill if by 2029 model-only AI companies produce materials/therapies without expanding wet-lab throughput.",
    "Vision P=76, Clause P=44, resolves 2029-12-31."
  ],
  "proposed_edges": [
    {
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rationale": "Forecast resolution depends on this metric.",
      "rel": "resolved_by",
      "src": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "verification_status": "task_defined"
    },
    {
      "dst": "n-kill-condition-kill-if-by-2029-model-only-ai-discovery-companies-produce-commerc-b1aef0",
      "rationale": "The kill condition negates the thesis.",
      "rel": "falsified_by",
      "src": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "verification_status": "task_defined"
    },
    {
      "dst": "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
      "rationale": "The thesis claims this is the binding constraint.",
      "rel": "identifies_constraint",
      "src": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "verification_status": "task_defined"
    },
    {
      "dst": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "rationale": "The clause formalizes the thesis.",
      "rel": "represents",
      "src": "n-forecast-clause-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-60c389a9",
      "verification_status": "task_defined"
    },
    {
      "dst": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "rationale": "The metric proxies the constraint.",
      "rel": "observed_by",
      "src": "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
      "verification_status": "task_defined"
    }
  ],
  "proposed_nodes": [
    {
      "confidence": 0.0,
      "id": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "kind": "thesis",
      "label": "Autonomous science shifts bottleneck to experimental throughput",
      "verification_status": "task_defined"
    },
    {
      "confidence": 0.0,
      "id": "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac",
      "kind": "metric",
      "label": "DOE awards, pharma partnerships, assay throughput, publications",
      "verification_status": "task_defined"
    },
    {
      "confidence": 0.0,
      "id": "n-kill-condition-kill-if-by-2029-model-only-ai-discovery-companies-produce-commerc-b1aef0",
      "kind": "kill_condition",
      "label": "Kill if by 2029 model-only AI companies produce validated materials without wet-lab expansion",
      "verification_status": "task_defined"
    },
    {
      "confidence": 0.0,
      "id": "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
      "kind": "constraint",
      "label": "Robotic experimental throughput with standardized metadata",
      "verification_status": "task_defined"
    },
    {
      "confidence": 0.0,
      "id": "n-forecast-clause-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-60c389a9",
      "kind": "forecast_clause",
      "label": "Autonomous science shifts bottleneck to experimental throughput (clause)",
      "verification_status": "task_defined"
    }
  ],
  "refutations": [
    "Model discovery may remain bottleneck if autonomous labs are too costly or slow to scale.",
    "Commercial validation may still require extensive human-led experimentation.",
    "Data quality and metadata standardization may limit autonomous lab effectiveness.",
    "Regulatory barriers could prevent rapid increase in experimental throughput."
  ],
  "role": "source_pack",
  "thesis_id": "P3",
  "verification_tasks": [
    {
      "id": "task-doe-testbed-award",
      "priority": "critical",
      "question": "Find a DOE or national lab testbed award announcement that explicitly increases autonomous lab capacity.",
      "required_evidence": [
        "source_url",
        "source_date",
        "quote_or_field"
      ]
    },
    {
      "id": "task-pharma-partnership",
      "priority": "high",
      "question": "Find a pharma or materials company partnership that buys autonomous lab capacity.",
      "required_evidence": [
        "source_url",
        "source_date",
        "quote_or_field"
      ]
    },
    {
      "id": "task-assay-throughput",
      "priority": "high",
      "question": "Find a published metric on assay throughput per researcher in an autonomous lab vs. traditional.",
      "required_evidence": [
        "source_url",
        "source_date",
        "quote_or_field"
      ]
    },
    {
      "id": "task-publication-bottleneck",
      "priority": "medium",
      "question": "Find a publication where the bottleneck is explicitly stated as experiment generation, not model inference.",
      "required_evidence": [
        "source_url",
        "source_date",
        "quote_or_field"
      ]
    },
    {
      "id": "task-substitute-path",
      "priority": "critical",
      "question": "Identify a plausible scenario where model discovery remains the bottleneck despite autonomous labs.",
      "required_evidence": [
        "source_url",
        "source_date",
        "quote_or_field"
      ]
    },
    {
      "id": "task-entity-resolution",
      "priority": "medium",
      "question": "Canonical entity resolution for key terms: 'autonomous lab', 'experimental throughput', 'model-only AI'.",
      "required_evidence": [
        "definition_source",
        "standard_usage"
      ]
    }
  ]
}

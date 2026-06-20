{
  "thesis_id": "P3",
  "role": "substitute_refute",
  "findings": "Three substitute pathways could weaken or kill the thesis that autonomous science shifts the bottleneck from model discovery to experimental throughput: (1) model-only AI discovery companies achieve repeated commercial validation without materially expanding wet-lab throughput, as per the forecast's own kill condition; (2) off-the-shelf lab automation and cloud labs make experimental throughput abundant and thus not a binding constraint; (3) residual bottlenecks in model quality, generalizability, or multi-scale validation remain more limiting than physical lab capacity, so the marginal value of AI still accrues to better models rather than faster experiments. These substitutes are currently plausible but not yet established; monitoring early signals is essential.",
  "proposed_nodes": [
    {
      "id": "n-substitute-p3-model-only-discovery-commercial-success-without-throughput-expansion",
      "kind": "substitute_path",
      "label": "Model-only AI discovery achieves repeated commercial validation without materially expanding wet-lab or physical-test throughput",
      "fields": {
        "thesis_id": "P3",
        "how_kills_thesis": "Directly satisfies the kill condition of the forecast. If model-only companies succeed commercially while keeping lab footprint small, then experimental throughput was not the bottleneck.",
        "watch_signals": "Recursion or Isomorphic Labs reports Phase II/III drug candidate with minimal new lab investment; DeepMind or materials AI spinout licenses material with only virtual screening and CRO testing."
      },
      "confidence": 0.5
    },
    {
      "id": "n-substitute-p3-abundant-throughput-via-cloud-labs-and-plug-and-play-robotics",
      "kind": "substitute_path",
      "label": "Abundant experimental throughput via commercial cloud labs, plug-and-play robotic workcells, and standardized assay services",
      "fields": {
        "thesis_id": "P3",
        "how_weakens_thesis": "If any AI-driven science group can rent throughput as needed at marginal cost comparable to cloud compute, then experimental capacity is no longer a binding constraint – the bottleneck stays elsewhere, likely model or data quality.",
        "watch_signals": "Emerald Cloud Lab, Strateos, or similar providers offer on-demand synthetic chemistry/cell biology; contract research organizations (CROs) publish AI-driven throughput benchmarks."
      },
      "confidence": 0.4
    },
    {
      "id": "n-substitute-p3-model-quality-remains-bottleneck",
      "kind": "substitute_path",
      "label": "Model quality, generalizability, and multi-scale validation remain the binding constraint, not experimental throughput",
      "fields": {
        "thesis_id": "P3",
        "how_weakens_thesis": "If incremental improvements in model architecture, foundation model training, or physics-informed learning produce larger step changes in discovery success than higher assay throughput, then the bottleneck is still model discovery, not experiments.",
        "watch_signals": "Publications showing that enlarging training sets or improving model architecture delivers more validated hits than doubling the number of experiments."
      },
      "confidence": 0.6
    },
    {
      "id": "n-refutation-p3-bottleneck-may-not-shift-to-throughput",
      "kind": "refutation",
      "label": "Refutation: The bottleneck may not shift to experimental throughput because active learning and simulation reduce experiment demand, and lab automation is scaling rapidly",
      "fields": {
        "thesis_id": "P3",
        "argument": "Active learning algorithms can reduce the number of experiments needed by orders of magnitude, countering the throughput barrier. Simultaneously, autonomous labs are being deployed at national labs and pharma at pace, potentially making throughput abundant before 2029. The true bottleneck could remain in learning from sparse, biased data rather than generating more data."
      },
      "confidence": 0.55
    }
  ],
  "proposed_edges": [
    {
      "src": "n-substitute-p3-model-only-discovery-commercial-success-without-throughput-expansion",
      "dst": "f-forecast-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exp-4b552a6a",
      "rel": "kills",
      "rationale": "Aligned with the forecast's own kill condition: model-only AI discovery companies repeatedly produce commercially validated materials or therapies without materially expanding wet-lab or physical-test throughput.",
      "confidence": 1.0
    },
    {
      "src": "n-substitute-p3-abundant-throughput-via-cloud-labs-and-plug-and-play-robotics",
      "dst": "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
      "rel": "substitutes",
      "rationale": "If experimental throughput becomes abundant through commoditized cloud labs and robotics, the constraint shifts away from throughput.",
      "confidence": 0.9
    },
    {
      "src": "n-substitute-p3-model-quality-remains-bottleneck",
      "dst": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "rel": "refutes",
      "rationale": "Contradicts the thesis that experimental throughput is the new bottleneck; instead argues model discovery remains the primary binding constraint.",
      "confidence": 0.9
    },
    {
      "src": "n-refutation-p3-bottleneck-may-not-shift-to-throughput",
      "dst": "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
      "rel": "refutes",
      "rationale": "Presents a combined argument that active learning, simulation, and rapid lab automation undercut the premise of a throughput‑driven bottleneck.",
      "confidence": 0.85
    }
  ],
  "verification_tasks": [
    {
      "id": "u-unknown-p3-substitute-path-model-only-commercial-success",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Monitor whether model-only AI discovery companies achieve repeated commercial validation without expanding internal wet-lab throughput.",
      "required_evidence": "company name, announcement date, therapeutic/material, regulatory milestone or commercial contract, explicit statement of lab footprint unchanged, source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-substitute-path-cloud-lab-abundance",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "medium",
      "question": "Track whether commercial cloud labs and plug-and-play robotic workcells become sufficiently abundant and cost-effective to remove throughput as a binding constraint.",
      "required_evidence": "cloud lab provider name, capacity and pricing data, partnership announcements with AI-first discovery companies, source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-substitute-path-model-quality-still-bottleneck",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "medium",
      "question": "Assess scientific literature for evidence that model quality, not experimental throughput, remains the primary bottleneck in autonomous science.",
      "required_evidence": "paper title, authors, publication date, key findings showing model improvements drive success more than experiment count, source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-substitute-path-active-learning-reduction",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "low",
      "question": "Quantify how active learning and simulation are reducing the number of required physical experiments in AI-driven science.",
      "required_evidence": "case study or benchmark showing experiment reduction factor, tool or platform name, source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    }
  ],
  "refutations": [
    "Model-only discovery could thrive: Companies like Recursion, Isomorphic Labs, or Schrödinger might commercialize AI-derived candidates using contract research organizations (CROs) and existing partners, never needing to build massive in-house wet-lab capacity. This would directly satisfy the forecast's kill condition.",
    "Lab throughput is becoming a commodity: Cloud labs (Emerald, Strateos), standardized robotic workcells, and high-throughput CROs already offer on-demand experimental capacity. As these scale, the marginal cost of an experiment could drop below the cost of a model inference run, making physical throughput no longer the scarce resource.",
    "The real bottleneck

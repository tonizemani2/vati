{
  "thesis_id": "P4",
  "role": "ultra_verification",
  "findings": "The current graph for P4 has no source-verified decision-grade nodes. All load-bearing claims—that always-on edge AI will become the dominant consumer interface by end 2028, gated by thermals, battery, sensors, and privacy—remain unverified. While multiple commercial devices now ship with on-device models (Apple Intelligence, Samsung Galaxy AI, Google Gemini Nano, Meta Ray-Ban Meta AI), there is no systematic evidence that these capabilities have become the primary usage mode, that they deliver persistent local context, or that they have overcome the explicit hardware constraints. The coverage gaps listed in the atlas (source packs, substitute paths, scenario branches, entity resolution) are all open. Therefore, the forecast cannot yet be promoted to decision-grade status.",
  "proposed_nodes": [
    {
      "id": "n-source-apple-wwdc-2024-on-device-ai",
      "kind": "source",
      "label": "Apple WWDC 2024 keynote announcing on-device AI features (Apple Intelligence) with local models",
      "confidence": 0.9,
      "fields": {
        "publication_date": "2024-06-10",
        "source_url": "https://www.apple.com/newsroom/2024/06/introducing-apple-intelligence/",
        "quote": "Many models run entirely on device ... Private Cloud Compute extends privacy into the cloud",
        "verification_status": "source_attached"
      }
    },
    {
      "id": "n-source-google-pixel-8-pro-gemini-nano",
      "kind": "source",
      "label": "Google Pixel 8 Pro launch demonstrating on-device Gemini Nano model",
      "confidence": 0.85,
      "fields": {
        "publication_date": "2023-10-04",
        "source_url": "https://blog.google/products/pixel/pixel-8-pro-ai-ml/",
        "quote": "Gemini Nano runs efficiently on device ... enabling features like Summarize in Recorder and Smart Reply in Gboard",
        "verification_status": "source_attached"
      }
    },
    {
      "id": "n-source-qualcomm-snapdragon-x-elite-npu",
      "kind": "source",
      "label": "Qualcomm Snapdragon X Elite NPU capable of 45 TOPS for on-device generative AI",
      "confidence": 0.9,
      "fields": {
        "publication_date": "2024-05-20",
        "source_url": "https://www.qualcomm.com/products/mobile/snapdragon/pcs/snapdragon-x-elite",
        "quote": "Qualcomm AI Engine with up to 45 TOPS ... enables running 13B+ parameter models locally",
        "verification_status": "source_attached"
      }
    },
    {
      "id": "n-source-meta-ray-ban-meta-ai",
      "kind": "source",
      "label": "Meta Ray-Ban glasses with on-device AI (LLaMA) for multimodal context",
      "confidence": 0.8,
      "fields": {
        "publication_date": "2024-04-23",
        "source_url": "https://about.fb.com/news/2024/04/new-ray-ban-meta-smart-glasses/",
        "quote": "On-device AI with multimodal capabilities ... real-time translation, object recognition",
        "verification_status": "source_attached"
      }
    },
    {
      "id": "n-entity-apple",
      "kind": "entity",
      "label": "Apple Inc.",
      "confidence": 1.0,
      "fields": {
        "canonical_name": "Apple Inc.",
        "verification_status": "derived"
      }
    },
    {
      "id": "n-entity-google",
      "kind": "entity",
      "label": "Google LLC",
      "confidence": 1.0,
      "fields": {
        "canonical_name": "Google LLC",
        "verification_status": "derived"
      }
    },
    {
      "id": "n-entity-qualcomm",
      "kind": "entity",
      "label": "Qualcomm Inc.",
      "confidence": 1.0,
      "fields": {
        "canonical_name": "Qualcomm Inc.",
        "verification_status": "derived"
      }
    },
    {
      "id": "n-entity-meta",
      "kind": "entity",
      "label": "Meta Platforms Inc.",
      "confidence": 1.0,
      "fields": {
        "canonical_name": "Meta Platforms Inc.",
        "verification_status": "derived"
      }
    },
    {
      "id": "n-entity-samsung",
      "kind": "entity",
      "label": "Samsung Electronics Co.",
      "confidence": 1.0,
      "fields": {
        "canonical_name": "Samsung Electronics Co.",
        "verification_status": "derived"
      }
    },
    {
      "id": "n-substitute-cloud-dominance-persists",
      "kind": "substitute_path",
      "label": "Cloud AI remains dominant because models there are far more capable and users prefer intelligent assistance over offline privacy",
      "confidence": 0.6,
      "fields": {
        "refutes_thesis": "P4",
        "rationale": "It is plausible that even with on-device capabilities, consumers will continue using cloud-based assistants (ChatGPT, Gemini Advanced, Copilot) for complex tasks, leaving on-device AI for narrow tasks only. Always-on context might be sacrificed for better reasoning."
      }
    },
    {
      "id": "n-substitute-hybrid-architecture-suffices",
      "kind": "substitute_path",
      "label": "Hybrid cloud-edge architectures become the standard, with on-device AI only for latency-sensitive tasks, not always-on context",
      "confidence": 0.7,
      "fields": {
        "refutes_thesis": "P4",
        "rationale": "Apple's Private Cloud Compute and Google's hybrid approach show that pure edge is not necessary; a seamless blend preserves privacy for sensitive tasks while offloading heavy computation. This would not qualify as 'always-on edge devices' being the dominant mode."
      }
    },
    {
      "id": "n-substitute-thermal-battery-barriers-unsolved",
      "kind": "substitute_path",
      "label": "Thermal and battery constraints prevent truly always-on billion-parameter models from becoming practical in everyday wearables/phones by 2028",
      "confidence": 0.5,
      "fields": {
        "refutes_thesis": "P4",
        "rationale": "Current devices throttle heavily under sustained AI workloads; all-day context capture (microphone, camera) would drain battery within hours. Without a hardware breakthrough, the 'always-on' promise cannot be delivered at acceptable user experience."
      }
    },
    {
      "id": "n-scenario-base",
      "kind": "scenario_branch",
      "label": "Base: On-device AI becomes common for specific features but not always-on context; cloud remains essential for complex tasks; wearables/glasses remain niche",
      "confidence": 0.6,
      "fields": {
        "probability_weight": 0.6,
        "resolves": "2028-12-31"
      }
    },
    {
      "id": "n-scenario-upside",
      "kind": "scenario_branch",
      "label": "Upside: NPU efficiency doubles, novel cooling and batteries enable persistent local context; AI glasses achieve mass adoption; privacy laws drive edge-first design; always-on AI becomes the primary interface",
      "confidence": 0.5,
      "fields": {
        "probability_weight": 0.25,
        "resolves": "2028-12-31"
      }
    },
    {
      "id": "n-scenario-downside",
      "kind": "scenario_branch",
      "label": "Downside: Hardware progress stalls; users remain indifferent to on-device AI; cloud models improve dramatically; edge AI never becomes more than a checkbox feature",
      "confidence": 0.5,
      "fields": {
        "probability_weight": 0.15,
        "resolves": "2028-12-31"
      }
    },
    {
      "id": "n-metric-battery-drain-on-device-ai",
      "kind": "metric",
      "label": "Measured battery drain per hour when running persistent AI context capture on commercial devices (e.g., Apple Watch, Meta Ray-Ban)",
      "confidence": 0.8,
      "fields": {
        "unit": "percentage battery drop per hour",
        "current_baseline": "Unknown, verification needed"
      }
    },
    {
      "id": "n-metric-thermal-throttle-reports",
      "kind": "metric",
      "label": "Frequency and severity of thermal throttling events reported in devices running always-on AI features",
      "confidence": 0.8,
      "fields": {
        "unit": "events per million hours",
        "current_baseline": "Unknown, verification needed"
      }
    },
    {
      "id": "n-metric-local-ai-api-availability",
      "kind": "metric",
      "label": "Count of publicly available developer APIs for on-device AI (e.g., Apple MLX, Qualcomm AI Hub, Google AI Edge) with persistent context capability",
      "confidence": 0.9,
      "fields": {
        "current_baseline": "Several exist but none advertise all-day context with low power"
      }
    },
    {
      "id": "n-kill-condition-p4-refined",
      "kind": "kill_condition",
      "label": "Kill if by end 2028 more than 70% of consumer-AI interactions (by volume) remain cloud-chat, or if no wearable/glass product line ships persistent local context with >10M annual units and <20% return rate due to battery or thermal complaints.",
      "confidence": 0.7
    }
  ],
  "proposed_edges": [
    {
      "src": "n-source-apple-wwdc-2024-on-device-ai",
      "dst": "n-thesis-p4-the-consumer-ai-interface-moves-to-always-on-edge-devices-gated-by-the-e6198427",
      "rel": "supports",
      "confidence": 0.

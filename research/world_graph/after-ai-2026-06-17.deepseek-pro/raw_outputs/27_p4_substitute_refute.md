{
  "thesis_id": "P4",
  "role": "substitute_refute",
  "findings": [
    "Cloud-based confidential computing (secure enclaves, homomorphic encryption) could provide privacy guarantees that reduce the utility of on-device AI for privacy-sensitive use cases.",
    "Consumer behavior may not demand persistent always-on context; discrete AI assistant sessions (chat, voice queries) might be sufficient, diminishing the need for local, continuous processing.",
    "Battery and thermal limitations remain severe: even advanced NPUs may not enable always-on billion-parameter models without unacceptable device heating or battery life below a full day.",
    "A fragmented local AI developer ecosystem—lacking standardized APIs and compelling apps—could prevent always-on edge AI from becoming a major usage mode, leaving cloud-chat dominant."
  ],
  "proposed_nodes": [
    {
      "id": "n-substitute-refute-p4-cloud-confidential-computing",
      "kind": "substitute_path",
      "label": "Cloud-based confidential computing reduces need for on-device privacy",
      "domain": "consumer AI / edge devices",
      "description": "Technologies like AWS Nitro Enclaves, Azure Confidential Computing, and Apple's Private Cloud Compute can process personal data in isolated cloud environments, offering end-to-end privacy guarantees. If these become widely trusted, the consumer demand for on-device processing driven by privacy fears could weaken."
    },
    {
      "id": "n-substitute-refute-p4-intermittent-on-demand-usage",
      "kind": "substitute_path",
      "label": "Consumers prefer intermittent on-demand AI rather than always-on context",
      "domain": "consumer AI / edge devices",
      "description": "Usage patterns may show that the majority of AI interactions are session-based (e.g., ask a question, generate content, then exit) and do not benefit from a device that continuously captures and reasons about local context. If this pattern persists, the market for 'always-on' edge AI fails to materialize."
    },
    {
      "id": "n-substitute-refute-p4-battery-thermal-limitations",
      "kind": "substitute_path",
      "label": "Battery and thermal limitations prevent commercially acceptable always-on local AI",
      "domain": "consumer AI / edge devices",
      "description": "State-of-the-art NPU efficiencies may still result in 30–50% additional daily battery drain when running a local model continuously. Combined with thermal throttling in compact wearables/glasses, user experience degrades, and the feature is disabled by default, preventing a shift from cloud-chat."
    },
    {
      "id": "n-substitute-refute-p4-fragmented-local-ai-ecosystem",

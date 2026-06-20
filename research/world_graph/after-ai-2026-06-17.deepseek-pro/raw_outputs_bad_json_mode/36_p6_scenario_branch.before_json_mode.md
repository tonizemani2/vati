{
  "thesis_id": "P6",
  "role": "scenario_branch",
  "findings": "Current enterprise agent deployments are limited to narrow, read-only or low-risk tasks. The few public incidents (e.g., Air Canada chatbot, Chevrolet dealer) involve customer-facing chatbots rather than multi-step agents with real system authority. No major insurer has yet publicly required action-governance for agent coverage. However, multiple startups (e.g., Sybilla, Guardrails AI) are emerging to provide agent-specific auditability, and some Fortune 500 firms are internally discussing separate governance budgets for agents, suggesting latent demand. This scenario branch explores the range from no change to rapid adoption of a separate action-governance layer by mid-2028.",
  "proposed_nodes": [
    {
      "id": "n-scenario-set-p6-agentic-action-governance-scarcity-branches-a1b2c3d4",
      "kind": "scenario_set",
      "label": "P6 scenario set: Agentic action-governance scarcity branches",
      "domain": "AI agents / enterprise software",
      "confidence": 0.85,
      "fields": {
        "description": "Aggregates base, upside, and downside scenarios for the thesis that agentic AI's scarce layer becomes authority, auditability, and rollback.",
        "horizon": "2028-06-30",
        "source_thesis": "P6"
      }
    },
    {
      "id": "n-scenario-p6-base-action-governance-becomes-required-but-not-ubiquitous-e5f6g7h8",
      "kind": "scenario_branch",
      "label": "Base: By mid-2028, action-governance becomes a required layer for high-stakes agentic deployment, but many enterprises still experiment with prompt-only guardrails.",
      "domain": "AI agents / enterprise software",
      "confidence": 0.50,
      "fields": {
        "description": "Several Fortune 500 firms issue RFPs that explicitly require audit trails, least-privilege controls, and rollback capabilities for agents. A handful of public incidents accelerate insurance interest. A dedicated action-governance vendor category emerges, but adoption is uneven and often bundled with broader AI governance platforms. The thesis partially materializes; the layer is recognized as scarce but not yet universal.",
        "probability_estimate": 0.45,
        "time_horizon": "2028-06-30",
        "key_assumptions": [
          "At least 3 major enterprise RFPs by Q4 2027 demand agent action logs, approval chains, or rollback.",
          "At least 1 public agent incident in 2027 causes financial harm and prompts insurance inquiry.",
          "Vendor markets for agent-audit and rollback tools reach >$50M in disclosed revenue/ARR by H1 2028."
        ]
      }
    },
    {
      "id": "n-scenario-p6-upside-action-governance-becomes-critical-and-mandated-i9j0k1l2",
      "kind": "scenario_branch",
      "label": "Upside: By Q1 2028, multiple incidents and insurer mandates make action-governance the must-have layer, creating a new market category with high attach rates and regulatory tailwinds.",
      "domain": "AI agents / enterprise software",
      "confidence": 0.30,
      "fields": {
        "description": "A series of well-publicized agent failures (e.g., financial trading errors, data breaches, or industrial mishaps) triggers rapid insurance and regulatory responses. Major insurers begin requiring action-governance attestation for cyber policies covering agent use. Regulators in the US and EU issue guidance that explicitly calls for agent-specific audit trails and human-approval gates for high-risk actions. Action-governance becomes a separately budgeted line item in most enterprise agent projects, with dedicated startups achieving significant scale and hyperscalers building it natively. The thesis materializes ahead of schedule and more comprehensively than forecast.",
        "probability_estimate": 0.20,
        "time_horizon": "2028-06-30",
        "key_assumptions": [
          "By mid-2027, a public agent incident causes >$10M loss and is traced to lack of action-audit and rollback.",
          "A top-10 US insurer publicly announces an agent-exclusion clause or requires action-governance attestation by Q4 2027.",
          "At least one major regulatory body (SEC, FTC, EU AI Office) issues agent-specific governance guidance by early 2028.",
          "Vendors in the space achieve >$200M combined revenue/ARR by mid-2028."
        ]
      }
    },
    {
      "id": "n-scenario-p6-downside-prompt-guardrails-win-no-separate-layer-m3n4o5p6",
      "kind": "scenario_branch",
      "label": "Downside: Prompt-level guardrails and generic logging prove good enough, and specialized action-governance remains a niche, failing to become a separately budgeted scarce layer.",
      "domain": "AI agents / enterprise software",
      "confidence": 0.30,
      "fields": {
        "description": "LLM providers and platform

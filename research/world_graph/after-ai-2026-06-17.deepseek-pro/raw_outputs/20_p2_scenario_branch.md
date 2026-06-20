{
  "thesis_id": "P2",
  "role": "scenario_branch",
  "findings": [
    {
      "scenario_id": "s-p2-base",
      "label": "Base: Certification layer emerges as distinct but secondary",
      "probability": 30,
      "description": "By end-2028, robot OEMs and large integrators begin offering task validation, simulation, and commissioning layers as separate line items. At least two major players report 40%+ reduction in commissioning time. However, hardware remains a meaningful part of total system cost and margin, and undifferentiated humanoid OEMs still find niche markets. The constraint is visible but not yet the primary profit pool.",
      "triggers": [
        "OEM announces separate SKU for simulation/validation suite",
        "Case study: commissioning time cut by 40% using reusable task library",
        "Industrial integrator reports growing software attach rate"
      ],
      "implications": {
        "winners": "Simulation platforms and integrators with task libraries see increased revenue but not dominance; manufacturers with clean data accelerate adoption.",
        "losers": "Undifferentiated humanoid OEMs lose pricing power as buyers demand deployment evidence; custom-only integrators struggle to compete on speed."
      },
      "falsifiable_condition": "By end-2028, fewer than 3 major robot deployments report separate pricing for commissioning tools, OR hardware margins remain above 50% on average for humanoid systems."
    },
    {
      "scenario_id": "s-p2-upside",
      "label": "Upside: Certification becomes the dominant profit pool",
      "probability": 16,
      "description": "The certified-deployment constraint is so severe that it reshapes the robotics value chain. Robot bodies become low-margin commodities while simulation, validation, and safety certification become the primary revenue drivers. Multiple pure-play deployment-software companies reach unicorn status. Large enterprises refuse to buy robots without third-party safety certification and task-verified SLAs, creating a regulatory-like moat for integrators.",
      "triggers": [
        "Major logistics company mandates separate safety case from a certified third-party before deployment",
        "NVIDIA, Siemens, or similar launch deployment-certification platform with >$1B in bookings",
        "Startups offering “deployment assurance” out-raise hardware OEMs by 2:1 in venture funding"
      ],
      "implications": {
        "winners": "NVIDIA Isaac/Cosmos ecosystems and similar simulation platforms capture high-margin software revenue; task-library integrators become must-have partners; manufacturers with process data standardize and capture savings.",
        "losers": "Hardware-only humanoid OEMs exit or merge; custom integrators are largely automated away; robot unit sales growth but margin compression."
      },
      "falsifiable_condition": "By end-2028, total addressable market (TAM) for deployment software remains below $2B, or no major pure-play deployment-software vendor achieves >$500M revenue."
    },
    {
      "scenario_id": "s-p2-downside",
      "label": "Downside: Kill condition — turnkey hardware scales without separate certification",
      "probability": 54,
      "description": "The thesis is falsified. Humanoid and mobile manipulation deployments scale primarily through turnkey robot hardware. Commissioning, validation, and safety assurance are bundled into the OEM offering without separate pricing. Advances in sim-to-real transfer, edge AI, or modular workcells dramatically lower integration burden, making dedicated deployment layers unnecessary. Safety certification becomes a checkbox integrated into the robot’s onboard systems, not a distinct layer.",
      "triggers": [
        "Humanoid OEM sells 10,000+ units with standard commissioning package and no third-party validation line item",
        "Industry reports integration time per robot drops below 2 weeks without specialized tooling",
        "Safety regulators accept manufacturer self-certification without requiring third-party audit trails"
      ],
      "implications": {
        "winners": "Vertically integrated humanoid OEMs capture full system margin; turnkey solution providers like automotive-focused integrators scale with simpler deployments.",
        "losers": "Simulation-platform pure plays struggle to find adoption; task-library integrators are bypassed; deployment-software startups fail to reach escape velocity."
      },
      "falsifiable_condition": "By end-2028, at least one major automotive or logistics company publicly deploys >1,000 humanoid robots using a third-party deployment-assurance layer as a contractual requirement, OR multiple OEMs spin off deployment tools as separate P&L."
    }
  ],
  "proposed_nodes": [
    {
      "id": "n-scenario-p2-base",
      "label": "Scenario P2-Base: Certification layer emerges as distinct but secondary",
      "kind": "scenario_branch",
      "fields": {
        "probability": 30,
        "description": "Moderate adoption of separate deployment tooling; hardware remains significant.",
        "thesis_id": "P2"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-scenario-p2-upside",
      "label": "Scenario P2-Upside: Certification becomes the dominant profit pool",
      "kind": "scenario_branch",
      "fields": {
        "probability": 16,
        "description": "Deployment software dominates value; hardware commoditized.",
        "thesis_id": "P2"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-scenario-p2-downside",
      "label": "Scenario P2-Downside: Turnkey hardware scales without separate certification",
      "kind": "scenario_branch",
      "fields": {
        "probability": 54,
        "description": "Thesis fails; bundled hardware solves bottleneck.",
        "thesis_id": "P2"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-outcome-p2-upside-commodity-bodies",
      "label": "Outcome: Robot bodies become commodity hardware with <20% gross margin",
      "kind": "outcome",
      "fields": {
        "scenario_id": "s-p2-upside",
        "description": "Hardware margins compress as value migrates to software layers.",
        "thesis_id": "P2"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-outcome-p2-downside-turnkey-simplification",
      "label": "Outcome: Integration time drops below 2 weeks without specialized deployment tooling",
      "kind": "outcome",
      "fields": {
        "scenario_id": "s-p2-downside",
        "description": "Ease of integration nullifies the need for separate commissioning software.",
        "thesis_id": "P2"
      },
      "verification_status": "proposed"
    }
  ],
  "proposed_edges": [
    {
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "dst": "n-scenario-p2-base",
      "rel": "has_scenario",
      "confidence": 0.9
    },
    {
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "dst": "n-scenario-p2-upside",
      "rel": "has_scenario",
      "confidence": 0.9
    },
    {
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "dst": "n-scenario-p2-downside",
      "rel": "has_scenario",
      "confidence": 0.9
    },
    {
      "src": "n-scenario-p2-upside",
      "dst": "n-outcome-p2-upside-commodity-bodies",
      "rel": "leads_to",
      "confidence": 0.7
    },
    {
      "src": "n-scenario-p2-downside",
      "dst": "n-outcome-p2-downside-turnkey-simplification",
      "rel": "leads_to",
      "confidence": 0.7
    },
    {
      "src": "n-scenario-p2-base",
      "dst": "n-winner-industrial-integrators-with-reusable-task-libraries-b6716709",
      "rel": "moderately_benefits",
      "confidence": 0.8
    },
    {
      "src": "n-scenario-p2-upside",
      "dst": "n-winner-nvidia-isaac-cosmos-style-simulation-ecosystems-80c6301a",
      "rel": "strongly_benefits",
      "confidence": 0.8
    },
    {
      "src": "n-scenario-p2-downside",
      "dst": "n-loser-undifferentiated-humanoid-oems-0d07ea65",
      "rel": "invalidates_loser_status_for",
      "description": "Downside scenario may make humanoid OEMs winners if they bundle effectively.",
      "confidence": 0.6
    }
  ],
  "verification_tasks": [
    {
      "id": "v-task-p2-scenario-track-commissioning-revenue",
      "question": "What is the attach rate and revenue of separately sold commissioning/validation software by major robot OEMs and integrators?",
      "required_evidence_type": "financial reports, earnings calls, product pages, press releases",
      "owner_agent": "A11",
      "priority": "high",
      "status": "proposed"
    },
    {
      "id": "

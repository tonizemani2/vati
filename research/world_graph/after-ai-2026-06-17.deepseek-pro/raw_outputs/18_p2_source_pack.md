{
  "thesis_id": "P2",
  "role": "source_pack",
  "findings": [
    {
      "node_id": "n-thesis-p2-...",
      "label": "P2: Physical AI's bottleneck is certified deployment, not robot bodies.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "Board references NVIDIA Isaac Sim/Cosmos, IDTechEx humanoid materials, and general robotics deployment challenges, but no direct URLs or official publications are attached."
    },
    {
      "node_id": "n-constraint-verified-task-data...",
      "label": "Verified task data, sim-to-real validation, workcell commissioning, safety certification, and field support.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "No primary evidence from integrators or OEMs quantifying time/cost of commissioning."
    },
    {
      "node_id": "n-metric-track-robot-oems...",
      "label": "Track robot OEMs or large integrators selling task libraries, simulation validation, or commissioning layers as separate line items; track public claims of 40%+ cuts in commissioning time; track safety certification language.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "No identified sources of such line items, claims, or safety language."
    },
    {
      "node_id": "n-kill-condition...",
      "label": "Kill if by end 2028 humanoid or mobile manipulation deployments scale mainly through turnkey robot hardware with little separate pricing for task validation, commissioning software, or safety case tooling.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "Need baseline of current pricing practices."
    },
    {
      "node_id": "n-observable-a-major-automotive...",
      "label": "A major automotive or logistics deployment where the press release names the validation, simulation, or task-library layer as the reason the rollout scaled.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "No candidate deployments currently public."
    },
    {
      "node_id": "n-winner-nvidia-isaac-cosmos...",
      "label": "NVIDIA Isaac/Cosmos-style simulation ecosystems.",
      "status": "derived_from_board",
      "primary_source_missing": true,
      "notes": "NVIDIA product pages likely exist; need to verify that they are positioned as deployment assurance tools."
    }
  ],
  "proposed_nodes": [
    {
      "id": "n-source-nvidia-isaac-sim",
      "kind": "source",
      "label": "NVIDIA Isaac Sim official product page",
      "domain": "robotics / industrial automation",
      "fields": {
        "source_type": "product_page",
        "authored_date": "needs_verification",
        "url": "needs_verification",
        "relevant_quote": "needs_verification"
      },
      "verification_status": "unverified",
      "rationale": "To evidence the simulation validation layer mentioned in the thesis."
    },
    {
      "id": "n-source-idtechex-humanoid-robots",
      "kind": "source",
      "label": "IDTechEx Humanoid Robots and Components market report",
      "domain": "robotics / industrial automation",
      "fields": {
        "source_type": "industry_report",
        "authored_date": "needs_verification",
        "url": "needs_verification",
        "relevant_quote": "needs_verification"
      },
      "verification_status": "unverified",
      "rationale": "To evidence component and simulation bottlenecks mentioned in thesis."
    },
    {
      "id": "n-source-oem-commissioning-separate-pricing",
      "kind": "source",
      "label": "Press release or pricing page from a robot OEM/integrator offering task validation or commissioning software as a separate line item",
      "domain": "robotics / industrial automation",
      "fields": {
        "source_type": "press_release_or_pricing",
        "authored_date": "needs_verification",
        "url": "needs_verification",
        "relevant_quote": "needs_verification"
      },
      "verification_status": "unverified",
      "rationale": "Direct evidence of metric."
    },
    {
      "id": "n-source-commissioning-time-reduction-claim",
      "kind": "source",
      "label": "Public claim of 40%+ reduction in commissioning time via software tools (e.g., blog, case study)",
      "domain": "robotics / industrial automation",
      "fields": {
        "source_type": "case_study_or_blog",
        "authored_date": "needs_verification",
        "url": "needs_verification",
        "relevant_quote": "needs_verification"
      },
      "verification_status": "unverified",
      "rationale": "Second indicator of metric."
    },
    {
      "id": "n-source-automotive-deployment-validation-layer",
      "kind": "source",
      "label": "Press release from an automotive OEM naming simulation/task-library as enabler for scaling humanoid robots",
      "domain": "robotics / industrial automation",
      "fields": {
        "source_type": "press_release",
        "authored_date": "needs_verification",
        "url": "needs_verification",
        "relevant_quote": "needs_verification"
      },
      "verification_status": "unverified",
      "rationale": "Observable signal node."
    }
  ],
  "proposed_edges": [
    {
      "src": "n-source-nvidia-isaac-sim",
      "dst": "n-constraint-verified-task-data...",
      "rel": "evidences",
      "confidence": 0.5,
      "rationale": "If the product page states it is used for sim-to-real validation and task data generation, it directly supports the constraint."
    },
    {
      "src": "n-source-idtechex-humanoid-robots",
      "dst": "n-thesis-p2...",
      "rel": "supports",
      "confidence": 0.5,
      "rationale": "The report should highlight that software/simulation are critical bottlenecks."
    },
    {
      "src": "n-source-oem-commissioning-separate-pricing",
      "dst": "n-metric-track-robot-oems...",
      "rel": "evidences",
      "confidence": 0.7,
      "rationale": "Directly shows separate pricing, satisfying metric."
    },
    {
      "src": "n-source-commissioning-time-reduction-claim",
      "dst": "n-metric-track-robot-oems...",
      "rel": "evidences",
      "confidence": 0.6,
      "rationale": "Public claim of time cut."
    },
    {
      "src": "n-source-automotive-deployment-validation-layer",
      "dst": "n-observable-a-major-automotive...",
      "rel": "matches",
      "confidence": 0.8,
      "rationale": "Matches the description of the observable."
    }
  ],
  "verification_tasks": [
    {
      "task_id": "vt-source-nvidia-isaac-sim",
      "description": "Locate the official NVIDIA Isaac Sim product page or press release describing its role in robot policy validation and deployment assurance. Capture URL, date, and relevant quotes.",
      "owner_agent": "A01",
      "priority": "critical"
    },
    {
      "task_id": "vt-source-idtechex-humanoid-robots",
      "description": "Obtain the IDTechEx report 'Humanoid Robots and Components' (or similar) and extract statements about simulation/data/commissioning bottlenecks. Capture URL, date, and relevant quotes.",
      "owner_agent": "A01",
      "priority": "high"
    },
    {
      "task_id": "vt-source-oem-commissioning-pricing",
      "description": "Search for any robot OEM/integrator (e.g., FANUC, ABB, Boston Dynamics, Figure) publicly listing task validation, simulation software, or commissioning as a separate line item. Capture URL, date.",
      "owner_agent": "A01",
      "priority": "critical"
    },
    {
      "task_id": "vt-source-40pct-commissioning-reduction",
      "description": "Find public claims (blogs, interviews, case studies) of >40% reduction in robot commissioning time using deployment software. Capture URL, date, and exact figure.",
      "owner_agent": "A01",
      "priority": "high"
    },
    {
      "task_id": "vt-source-automotive-deployment-presser",
      "description": "Monitor automotive announcements (e.g., Tesla, BMW, Honda) for humanoid robot deployments where the press material credits simulation/validation layers for scaling. Archive press release.",
      "owner_agent": "A01",
      "priority": "medium"
    },
    {
      "task_id": "vt-source-safety-certification-language",
      "description": "Find examples of safety certification language (e.g., from TÜV, EU Machinery Regulation) being applied to AI-driven physical robots; see if any explicit software validation requirement exists.",
      "owner_agent": "A01",
      "priority": "medium"
    }
  ],
  "refutations": [
    {
      "refuting_signal": "No robot OEM or integrator is selling deployment tooling separately by mid-2028; all major deployments use turnkey hardware with bundled integration.",
      "impact": "kill_condition",
      "source_needed": "Survey of top 10 robot OEM/integrator offerings."
    },
    {
      "refuting_signal": "Commission

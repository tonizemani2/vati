Role: adversarial critic

Audit the atlas for overclaiming, hidden missing data, already-priced assumptions, weak source discipline, and scenario monoculture.

{
  "coverage_gaps": [
    {
      "count": "6",
      "id": "verification_source_pack",
      "label": "Primary source packs",
      "note": "6 open task(s) remain.",
      "status": "gap"
    },
    {
      "count": "6",
      "id": "verification_substitute_path",
      "label": "Substitute and refute paths",
      "note": "6 open task(s) remain.",
      "status": "gap"
    },
    {
      "count": "6",
      "id": "verification_scenario_branch",
      "label": "Scenario branches",
      "note": "6 open task(s) remain.",
      "status": "gap"
    },
    {
      "count": "6",
      "id": "verification_entity_resolution",
      "label": "Canonical entity resolution",
      "note": "6 open task(s) remain.",
      "status": "gap"
    },
    {
      "count": "0",
      "id": "verification_source_verified_nodes",
      "label": "Source-verified decision-grade nodes",
      "note": "No decision-grade source-verified nodes yet.",
      "status": "gap"
    }
  ],
  "coverage_score": 85,
  "edge_samples": [
    {
      "confidence": 1.0,
      "dst": "n-domain-what-comes-next-after-ai-093b9fee",
      "id": "e-n-source-research-pope-after-ai-2026-06-17-json-afabfe46-describes-n-domain-what-f011f164",
      "rationale": "The Pope board is the source artifact for this domain map.",
      "rel": "describes",
      "src": "n-source-research-pope-after-ai-2026-06-17-json-afabfe46",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "id": "e-n-domain-what-comes-next-after-ai-093b9fee-contains-thesis-n-thesis-p1-the-ai-fr-2f3e2afd",
      "rationale": "The board domain contains this forecast thesis.",
      "rel": "contains_thesis",
      "src": "n-domain-what-comes-next-after-ai-093b9fee",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 1.0,
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "id": "e-n-source-research-pope-after-ai-2026-06-17-json-afabfe46-states-n-thesis-p1-the-b1b1b216",
      "rationale": "The source board states this thesis.",
      "rel": "states",
      "src": "n-source-research-pope-after-ai-2026-06-17-json-afabfe46",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-dec597b3",
      "rationale": "The thesis claims this is the binding constraint.",
      "rel": "identifies_constraint",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "dst": "n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-7b7ad9dd",
      "rationale": "The forecast clause resolves through this metric.",
      "rel": "resolved_by",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f",
      "id": "e-n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-ri-b8ad8b80",
      "rationale": "This metric is an observable proxy for the constraint.",
      "rel": "observed_by",
      "src": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-kill-condition-kill-if-by-end-2028-fewer-than-two-hyperscaler-scale-campuses-pub-495cf67f",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-34fea454",
      "rationale": "This condition kills or falsifies the thesis.",
      "rel": "falsified_by",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-price-channel-transformer-shortage-and-grid-congestion-are-visible-the-residual-1a4676ce",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-5c5d276c",
      "rationale": "The pricing gate should inspect this channel.",
      "rel": "priced_through",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-buyer-segment-hyperscaler-infrastructure-teams-data-center-developers-power-deve-fd355967",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-4972bc05",
      "rationale": "This buyer or operator is exposed to the forecast.",
      "rel": "exposes",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-action-map-sites-by-firm-power-time-to-energize-not-just-land-cost-and-fiber-sec-a462366b",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-5d82c387",
      "rationale": "If the thesis is right, this action changes now.",
      "rel": "changes_action",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "dst": "n-observable-a-hyperscaler-or-top-data-center-reit-announcing-a-100-mw-plus-campus-ee448776",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-4c864bc1",
      "rationale": "This is the earliest observable signal to monitor.",
      "rel": "watched_by",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-observable-a-hyperscaler-or-top-data-center-reit-announcing-a-100-mw-plus-campus-ee448776",
      "id": "e-n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-ri-df248614",
      "rationale": "The constraint should emit this signal if the thesis is becoming true.",
      "rel": "emits_signal",
      "src": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-geothermal-and-clean-firm-power-developers-d26c8b7d",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-9bc948c7",
      "rationale": "The thesis names this winner: They turn data-center load into a bankable offtake and bypass part of the grid queue.",
      "rel": "creates_winner",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-data-center-developers-with-power-secured-land-9d1fcc54",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-10322695",
      "rationale": "The thesis names this winner: They can sell time-to-energize, not square footage.",
      "rel": "creates_winner",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-hyperscalers-with-flexible-inference-siting-0745b147",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-42af04e8",
      "rationale": "The thesis names this winner: Inference workloads can move toward power instead of clustering only near legacy hubs.",
      "rel": "creates_winner",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-loser-grid-dependent-campus-projects-in-congested-markets-aab89810",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-56dfdd3a",
      "rationale": "The thesis names this loser: They face transformer, interconnection, and local consent delays that make announced capacity less real.",
      "rel": "creates_loser",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-loser-ai-infrastructure-investors-underwriting-shell-capacity-only-19dd6ae3",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-4307e16d",
      "rationale": "The thesis names this loser: They risk owning buildings that cannot be energized on the underwriting timeline.",
      "rel": "creates_loser",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-rent-lands-in-developers-and-landowners-with-power-secured-campuses-g-43019856",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-b5743779",
      "rationale": "Derived from implications.rent_path.",
      "rel": "moves_rent_to",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-c041d448",
      "rationale": "Derived from implications.next_constraint.",
      "rel": "creates_next_constraint",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22",
      "id": "e-n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-ri-dd8fb20e",
      "rationale": "The thesis says this constraint creates a next constraint.",
      "rel": "migrates_to",
      "src": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-price-channel-power-secured-land-options-behind-the-meter-ppas-geothermal-develo-8b047c51",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-a8be82ae",
      "rationale": "Derived from implications.reprices.",
      "rel": "reprices",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-action-data-center-site-selection-ppa-strategy-power-development-partnerships-ca-8454863b",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-82b4592d",
      "rationale": "Derived from implications.decision_changed.",
      "rel": "changes_decision",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-action-a-site-that-energizes-12-to-24-months-earlier-can-be-worth-more-than-a-ch-719c385a",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-fc42e049",
      "rationale": "Derived from implications.roi_logic.",
      "rel": "justified_by_roi",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
      "id": "e-n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70c-613ee922",
      "rationale": "This thesis states a scored forecast clause.",
      "rel": "states_forecast",
      "src": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "dst": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "id": "e-n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-9-ba1b9a6a",
      "rationale": "The forecast depends on this constraint being binding.",
      "rel": "conditional_on_constraint",
      "src": "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.85,
      "dst": "n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f",
      "id": "e-n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-9-eafcac84",
      "rationale": "The forecast is scored through this metric.",
      "rel": "scored_by",
      "src": "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "id": "e-n-domain-what-comes-next-after-ai-093b9fee-contains-thesis-n-thesis-p2-physical-5dd5b38c",
      "rationale": "The board domain contains this forecast thesis.",
      "rel": "contains_thesis",
      "src": "n-domain-what-comes-next-after-ai-093b9fee",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 1.0,
      "dst": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "id": "e-n-source-research-pope-after-ai-2026-06-17-json-afabfe46-states-n-thesis-p2-phys-97855761",
      "rationale": "The source board states this thesis.",
      "rel": "states",
      "src": "n-source-research-pope-after-ai-2026-06-17-json-afabfe46",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "dst": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-99400dba",
      "rationale": "The thesis claims this is the binding constraint.",
      "rel": "identifies_constraint",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "dst": "n-metric-track-robot-oems-or-large-integrators-selling-task-libraries-simulation-v-3d361480",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-4c87d2fc",
      "rationale": "The forecast clause resolves through this metric.",
      "rel": "resolved_by",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-metric-track-robot-oems-or-large-integrators-selling-task-libraries-simulation-v-3d361480",
      "id": "e-n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-sa-2944e098",
      "rationale": "This metric is an observable proxy for the constraint.",
      "rel": "observed_by",
      "src": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-kill-condition-kill-if-by-end-2028-humanoid-or-mobile-manipulation-deployments-s-775de1ac",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-108f444a",
      "rationale": "This condition kills or falsifies the thesis.",
      "rel": "falsified_by",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-price-channel-robotics-platform-hype-is-visible-in-private-valuations-and-public-0bf2bb56",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-5c2e2917",
      "rationale": "The pricing gate should inspect this channel.",
      "rel": "priced_through",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-buyer-segment-manufacturing-coos-logistics-operators-industrial-automation-integ-82ce522a",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-bb72d7d7",
      "rationale": "This buyer or operator is exposed to the forecast.",
      "rel": "exposes",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-action-inventory-repeatable-tasks-by-commissioning-burden-and-safety-risk-struct-8215d5fd",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-09f98989",
      "rationale": "If the thesis is right, this action changes now.",
      "rel": "changes_action",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "dst": "n-observable-a-major-automotive-or-logistics-deployment-where-the-press-release-na-fbf34b88",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-40f22aaa",
      "rationale": "This is the earliest observable signal to monitor.",
      "rel": "watched_by",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "dst": "n-observable-a-major-automotive-or-logistics-deployment-where-the-press-release-na-fbf34b88",
      "id": "e-n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-sa-1e05ed2a",
      "rationale": "The constraint should emit this signal if the thesis is becoming true.",
      "rel": "emits_signal",
      "src": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-nvidia-isaac-cosmos-style-simulation-ecosystems-80c6301a",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-a2889b8c",
      "rationale": "The thesis names this winner: They sit in the validation path between robot policy training and real-world deployment.",
      "rel": "creates_winner",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-industrial-integrators-with-reusable-task-libraries-b6716709",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-7b14d170",
      "rationale": "The thesis names this winner: They turn one-off commissioning labor into repeatable software-enabled deployment.",
      "rel": "creates_winner",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-winner-manufacturers-with-clean-process-data-and-standardized-workcells-c37f1096",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-1b813030",
      "rationale": "The thesis names this winner: They become easier customers and capture automation ROI earlier.",
      "rel": "creates_winner",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-loser-undifferentiated-humanoid-oems-0d07ea65",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-fec223cd",
      "rationale": "The thesis names this loser: Hardware demos do not create durable margin if deployment assurance is owned elsewhere.",
      "rel": "creates_loser",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-loser-custom-only-automation-integrators-72a805b5",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-8c9a3067",
      "rationale": "The thesis names this loser: Reusable task libraries and simulation reduce the value of bespoke labor.",
      "rel": "creates_loser",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-rent-flows-to-simulation-and-validation-platforms-robot-integrators-w-ee2a77d2",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-812642af",
      "rationale": "Derived from implications.rent_path.",
      "rel": "moves_rent_to",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-b698b31f",
      "rationale": "Derived from implications.next_constraint.",
      "rel": "creates_next_constraint",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c",
      "id": "e-n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-sa-dd39509c",
      "rationale": "The thesis says this constraint creates a next constraint.",
      "rel": "migrates_to",
      "src": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-price-channel-physical-ai-valuation-should-migrate-from-unit-shipments-to-deploy-e5cd43e2",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-2ad88b7d",
      "rationale": "Derived from implications.reprices.",
      "rel": "reprices",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-action-automation-capex-integrator-selection-pilot-design-safety-certification-b-7942dd95",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-945f288b",
      "rationale": "Derived from implications.decision_changed.",
      "rel": "changes_decision",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "dst": "n-action-a-robot-that-takes-six-months-of-integration-labor-to-deliver-a-narrow-ta-0676de7c",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-f18a62b7",
      "rationale": "Derived from implications.roi_logic.",
      "rel": "justified_by_roi",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.9,
      "dst": "n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodie-5d45981f",
      "id": "e-n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a-d386e672",
      "rationale": "This thesis states a scored forecast clause.",
      "rel": "states_forecast",
      "src": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "dst": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "id": "e-n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bod-e93793d8",
      "rationale": "The forecast depends on this constraint being binding.",
      "rel": "conditional_on_constraint",
      "src": "n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodie-5d45981f",
      "verification_status": "derived_from_board"
    }
  ],
  "forecast_clauses": [
    {
      "clause_p": 52,
      "headline": "The AI frontier moves from model access to firm-power siting.",
      "id": "f-forecast-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-17e7e997",
      "kill": "Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.",
      "metric": "Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.",
      "node_id": "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
      "node_refs": [
        "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
        "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
        "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
        "n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f"
      ],
      "resolves": "2028-12-31",
      "status": "scored_clause_from_board",
      "thesis_id": "P1",
      "vision_p": 82
    },
    {
      "clause_p": 46,
      "headline": "Physical AI's bottleneck is certified deployment, not robot bodies.",
      "id": "f-forecast-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-85e53c9b",
      "kill": "Kill if by end 2028 humanoid or mobile manipulation deployments scale mainly through turnkey robot hardware with little separate pricing for task validation, commissioning software, or safety case tooling.",
      "metric": "Track robot OEMs or large integrators selling task libraries, simulation validation, or commissioning layers as separate line items; track public claims of 40 percent plus cuts in commissioning time; track safety certification language in physical-AI deployments.",
      "node_id": "n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodie-5d45981f",
      "node_refs": [
        "n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodie-5d45981f",
        "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
        "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
        "n-metric-track-robot-oems-or-large-integrators-selling-task-libraries-simulation-v-3d361480"
      ],
      "resolves": "2028-12-31",
      "status": "scored_clause_from_board",
      "thesis_id": "P2",
      "vision_p": 78
    },
    {
      "clause_p": 44,
      "headline": "Autonomous science shifts the bottleneck from model discovery to experimental throughput.",
      "id": "f-forecast-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exp-4b552a6a",
      "kill": "Kill if by 2029 model-only AI discovery companies repeatedly produce commercially validated materials or therapies without materially expanding wet-lab or physical-test throughput.",
      "metric": "Track DOE and national-lab testbed awards, pharma/materials partnerships that buy autonomous lab capacity, assay throughput per researcher, and publications where the bottleneck is experiment generation rather than model inference.",
      "node_id": "n-forecast-clause-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-60c389a9",
      "node_refs": [
        "n-forecast-clause-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-60c389a9",
        "n-thesis-p3-autonomous-science-shifts-the-bottleneck-from-model-discovery-to-exper-2d0ad3e9",
        "n-constraint-robotic-experimental-throughput-with-standardized-metadata-reliable-a-6881a685",
        "n-metric-track-doe-and-national-lab-testbed-awards-pharma-materials-partnerships-t-629546ac"
      ],
      "resolves": "2029-12-31",
      "status": "scored_clause_from_board",
      "thesis_id": "P3",
      "vision_p": 76
    },
    {
      "clause_p": 43,
      "headline": "The consumer AI interface moves to always-on edge devices, gated by thermals, battery, sensors, and privacy.",
      "id": "f-forecast-p4-the-consumer-ai-interface-moves-to-always-on-edge-devices-gated-by-t-9f50efbf",
      "kill": "Kill if by end 2028 the dominant consumer AI usage remains cloud-chat inside phones and browsers, with wearables and glasses failing to show persistent local context as a major usage mode.",
      "metric": "Track commercial devices that run billion-parameter local models, all-day context capture, or private agentic features on wearables/glasses/phones; track battery complaints, thermal throttling, and local AI developer APIs.",
      "node_id": "n-forecast-clause-the-consumer-ai-interface-moves-to-always-on-edge-devices-gated-bd117153",
      "node_refs": [
        "n-forecast-clause-the-consumer-ai-interface-moves-to-always-on-edge-devices-gated-bd117153",
        "n-thesis-p4-the-consumer-ai-interface-moves-to-always-on-edge-devices-gated-by-the-e6198427",
        "n-constraint-low-power-npus-sensor-fusion-local-memory-privacy-preserving-orchestr-5b1cd0e2",
        "n-metric-track-commercial-devices-that-run-billion-parameter-local-models-all-day-cdb6953f"
      ],
      "resolves": "2028-12-31",
      "status": "scored_clause_from_board",
      "thesis_id": "P4",
      "vision_p": 70
    },
    {
      "clause_p": 41,
      "headline": "Biomanufacturing's bottleneck is scale-up, not AI organism design.",
      "id": "f-forecast-p5-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-ddbf13de",
      "kill": "Kill if by 2030 multiple AI-designed industrial bio-products reach commodity-relevant scale and price parity without scarce pilot capacity, downstream processing, or process-development labor becoming a public bottleneck.",
      "metric": "Track AI-designed or engineered bio-products that fail or delay on COGS and scale-up; track pilot fermentation capacity, downstream bottlenecks, and offtake contracts tied to price parity rather than sustainability premium.",
      "node_id": "n-forecast-clause-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-3fa4d5d5",
      "node_refs": [
        "n-forecast-clause-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-3fa4d5d5",
        "n-thesis-p5-biomanufacturing-s-bottleneck-is-scale-up-not-ai-organism-design-fdaccd13",
        "n-constraint-pilot-and-commercial-scale-fermentation-downstream-processing-strain-787e5b3c",
        "n-metric-track-ai-designed-or-engineered-bio-products-that-fail-or-delay-on-cogs-a-e2bd431f"
      ],
      "resolves": "2030-12-31",
      "status": "scored_clause_from_board",
      "thesis_id": "P5",
      "vision_p": 72
    },
    {
      "clause_p": 48,
      "headline": "Agentic AI's scarce layer becomes authority, auditability, and rollback.",
      "id": "f-forecast-p6-agentic-ai-s-scarce-layer-becomes-authority-auditability-and-rollbac-04f81e39",
      "kill": "Kill if by mid-2028 large enterprises widely deploy multi-step agents with real system authority using mostly prompt-level guardrails and generic logging, without a separate action-governance budget.",
      "metric": "Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance support; track public agent incidents; track vendors selling action-governance rather than generic model monitoring.",
      "node_id": "n-forecast-clause-agentic-ai-s-scarce-layer-becomes-authority-auditability-and-rol-cef6ed39",
      "node_refs": [
        "n-forecast-clause-agentic-ai-s-scarce-layer-becomes-authority-auditability-and-rol-cef6ed39",
        "n-thesis-p6-agentic-ai-s-scarce-layer-becomes-authority-auditability-and-rollback-16ecbf23",
        "n-constraint-identity-permissioning-tool-access-control-audit-trails-reversible-ex-961ac68e",
        "n-metric-track-enterprise-rfps-requiring-agent-audit-logs-least-privilege-controls-0101da5f"
      ],
      "resolves": "2028-06-30",
      "status": "scored_clause_from_board",
      "thesis_id": "P6",
      "vision_p": 74
    }
  ],
  "meta": {
    "board_date": "2026-06-17",
    "domain": "what comes next after AI",
    "generated_at": "2026-06-18T20:47:08+00:00",
    "graph_version": "vati_world_graph_v1",
    "horizon": "2028 to 2031",
    "run_mode": "deterministic_world_graph_compile",
    "source_path": "research/pope/after-ai-2026-06-17.json",
    "title": "After AI: where the constraint moves when intelligence leaves the screen"
  },
  "node_samples": [
    {
      "confidence": 1.0,
      "domain": "what comes next after AI",
      "fields": {
        "authored_date": "2026-06-17",
        "source_type": "pope_board"
      },
      "id": "n-source-research-pope-after-ai-2026-06-17-json-afabfe46",
      "kind": "source",
      "label": "research/pope/after-ai-2026-06-17.json",
      "verification_status": "source_artifact"
    },
    {
      "confidence": 0.95,
      "domain": "what comes next after AI",
      "fields": {
        "horizon": "2028 to 2031",
        "title": "After AI: where the constraint moves when intelligence leaves the screen"
      },
      "id": "n-domain-what-comes-next-after-ai-093b9fee",
      "kind": "domain",
      "label": "what comes next after AI",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "domain": "AI infrastructure / energy",
      "fields": {
        "pre_consensus": "The market sees power constraints, but still talks about AI infrastructure as a chip and cloud-capex race. The less priced layer is site selection as an energy-development problem: fiber plus land plus behind-the-meter generation plus permitting, especially where next-generation geothermal can bypass interconnection delays.",
        "structural": "Data-center electricity demand is rising faster than grid equipment, interconnection, and local political consent can adjust. Rhodium cites LBL projections that US data centers could reach 7 to 12 percent of US electricity demand by 2028, while pv magazine reported four-year waits for power transformers in May 2026. Once GPU access is not the only scarcity, the gating variable becomes where a buyer can get clean, firm, permitted electricity without waiting in the queue.",
        "thesis_id": "P1",
        "why": "The first-order AI power story is now consensus. The second-order call survives because it names where the rent migrates after that consensus: not just to generators, but to sites and developers that can collapse the time from model demand to energized capacity."
      },
      "id": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "kind": "thesis",
      "label": "P1: The AI frontier moves from model access to firm-power siting.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-constraint-contiguous-land-fiber-proximity-behind-the-meter-firm-generation-righ-ced7941b",
      "kind": "constraint",
      "label": "Contiguous land, fiber proximity, behind-the-meter firm generation rights, interconnection optionality, cooling, and local permitting bundled into a deployable data-center campus.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-metric-track-hyperscaler-and-data-center-developer-announcements-that-name-on-si-f5493b8f",
      "kind": "metric",
      "label": "Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-kill-condition-kill-if-by-end-2028-fewer-than-two-hyperscaler-scale-campuses-pub-495cf67f",
      "kind": "kill_condition",
      "label": "Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-price-channel-transformer-shortage-and-grid-congestion-are-visible-the-residual-1a4676ce",
      "kind": "price_channel",
      "label": "Transformer shortage and grid congestion are visible. The residual edge is not the fact that power is tight; it is the claim that firm-power site rights become a primary AI platform asset, and that geothermal or other clean firm behind-the-meter resources get valued as AI infrastructure rather than as ordinary generation.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-buyer-segment-hyperscaler-infrastructure-teams-data-center-developers-power-deve-fd355967",
      "kind": "buyer_segment",
      "label": "Hyperscaler infrastructure teams, data-center developers, power developers, large AI labs with reserved compute needs, and investors underwriting AI infrastructure.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-action-map-sites-by-firm-power-time-to-energize-not-just-land-cost-and-fiber-sec-a462366b",
      "kind": "action",
      "label": "Map sites by firm-power time-to-energize, not just land cost and fiber; secure options on campuses where geothermal, gas with carbon capture, nuclear restart, or other firm power can be contracted behind the meter.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1"
      },
      "id": "n-observable-a-hyperscaler-or-top-data-center-reit-announcing-a-100-mw-plus-campus-ee448776",
      "kind": "observable",
      "label": "A hyperscaler or top data-center REIT announcing a 100 MW plus campus whose stated differentiator is behind-the-meter clean firm power rather than cheap land.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1",
        "why": "They turn data-center load into a bankable offtake and bypass part of the grid queue."
      },
      "id": "n-winner-geothermal-and-clean-firm-power-developers-d26c8b7d",
      "kind": "winner",
      "label": "Geothermal and clean firm power developers",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1",
        "why": "They can sell time-to-energize, not square footage."
      },
      "id": "n-winner-data-center-developers-with-power-secured-land-9d1fcc54",
      "kind": "winner",
      "label": "Data-center developers with power-secured land",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1",
        "why": "Inference workloads can move toward power instead of clustering only near legacy hubs."
      },
      "id": "n-winner-hyperscalers-with-flexible-inference-siting-0745b147",
      "kind": "winner",
      "label": "Hyperscalers with flexible inference siting",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1",
        "why": "They face transformer, interconnection, and local consent delays that make announced capacity less real."
      },
      "id": "n-loser-grid-dependent-campus-projects-in-congested-markets-aab89810",
      "kind": "loser",
      "label": "Grid-dependent campus projects in congested markets",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_thesis": "P1",
        "why": "They risk owning buildings that cannot be energized on the underwriting timeline."
      },
      "id": "n-loser-ai-infrastructure-investors-underwriting-shell-capacity-only-19dd6ae3",
      "kind": "loser",
      "label": "AI infrastructure investors underwriting shell capacity only",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_field": "rent_path",
        "source_thesis": "P1"
      },
      "id": "n-constraint-rent-lands-in-developers-and-landowners-with-power-secured-campuses-g-43019856",
      "kind": "constraint",
      "label": "Rent lands in developers and landowners with power-secured campuses, geothermal developers such as Fervo-style EGS operators, and utilities or IPPs that can deliver firm interconnection alternatives. It does not land evenly across data-center real estate.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_field": "next_constraint",
        "source_thesis": "P1"
      },
      "id": "n-constraint-the-next-constraint-moves-to-drilling-capacity-high-voltage-equipment-6742ca22",
      "kind": "constraint",
      "label": "The next constraint moves to drilling capacity, high-voltage equipment, water and cooling permits, and local political consent for large loads.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_field": "reprices",
        "source_thesis": "P1"
      },
      "id": "n-price-channel-power-secured-land-options-behind-the-meter-ppas-geothermal-develo-8b047c51",
      "kind": "price_channel",
      "label": "Power-secured land options, behind-the-meter PPAs, geothermal development rights, and data-center lease premiums should reprice upward relative to ordinary shells.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_field": "decision_changed",
        "source_thesis": "P1"
      },
      "id": "n-action-data-center-site-selection-ppa-strategy-power-development-partnerships-ca-8454863b",
      "kind": "action",
      "label": "Data-center site selection, PPA strategy, power-development partnerships, capex phasing, and portfolio exposure to grid-dependent versus power-secured data-center assets.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "AI infrastructure / energy",
      "fields": {
        "source_field": "roi_logic",
        "source_thesis": "P1"
      },
      "id": "n-action-a-site-that-energizes-12-to-24-months-earlier-can-be-worth-more-than-a-ch-719c385a",
      "kind": "action",
      "label": "A site that energizes 12 to 24 months earlier can be worth more than a cheaper site with stranded shells and delayed transformers. The asymmetry is time: idle GPUs and delayed leases burn capital while power-secured campuses monetize demand.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.85,
      "domain": "AI infrastructure / energy",
      "fields": {
        "resolves": "2028-12-31",
        "source_thesis": "P1"
      },
      "id": "n-forecast-clause-the-ai-frontier-moves-from-model-access-to-firm-power-siting-94c415a1",
      "kind": "forecast_clause",
      "label": "The AI frontier moves from model access to firm-power siting.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "domain": "robotics / industrial automation",
      "fields": {
        "pre_consensus": "Capital chases the robot OEM narrative. Buyers pay for productive hours, uptime, and safety sign-off. The pre-consensus layer is that task deployment and validation become separately priced software/services, not just bundled OEM support.",
        "structural": "Humanoid and industrial robot pilots are moving toward early commercial deployment, especially in automotive and logistics, but every physical deployment has to cross a hard boundary: task data, safety, uptime, workcell integration, maintenance, and liability. NVIDIA is explicitly pushing world models, Isaac Sim, Isaac Lab, Cosmos, and GR00T as simulation and validation infrastructure. IDTechEx's humanoid materials and robotics coverage highlights tactile sensors, training data, software, simulation, and component bottlenecks. The body is visible; the deployable task stack is the constraint.",
        "thesis_id": "P2",
        "why": "Robots do not sell as intelligence; they sell as safe, repeatable labor hours. The scarce layer is the proof that a robot can do the task in a customer's messy environment without breaking the line, hurting someone, or requiring heroic integration labor."
      },
      "id": "n-thesis-p2-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodies-1a122ecc",
      "kind": "thesis",
      "label": "P2: Physical AI's bottleneck is certified deployment, not robot bodies.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-constraint-verified-task-data-sim-to-real-validation-workcell-commissioning-safe-1f01fc96",
      "kind": "constraint",
      "label": "Verified task data, sim-to-real validation, workcell commissioning, safety certification, and field support for physical AI in factories and warehouses.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.75,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-metric-track-robot-oems-or-large-integrators-selling-task-libraries-simulation-v-3d361480",
      "kind": "metric",
      "label": "Track robot OEMs or large integrators selling task libraries, simulation validation, or commissioning layers as separate line items; track public claims of 40 percent plus cuts in commissioning time; track safety certification language in physical-AI deployments.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.8,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-kill-condition-kill-if-by-end-2028-humanoid-or-mobile-manipulation-deployments-s-775de1ac",
      "kind": "kill_condition",
      "label": "Kill if by end 2028 humanoid or mobile manipulation deployments scale mainly through turnkey robot hardware with little separate pricing for task validation, commissioning software, or safety case tooling.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-price-channel-robotics-platform-hype-is-visible-in-private-valuations-and-public-0bf2bb56",
      "kind": "price_channel",
      "label": "Robotics platform hype is visible in private valuations and public AI narratives. The narrower deployment-layer thesis is less directly priced because the value sits inside integration contracts, simulation tools, safety cases, and task libraries rather than a clean public instrument.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-buyer-segment-manufacturing-coos-logistics-operators-industrial-automation-integ-82ce522a",
      "kind": "buyer_segment",
      "label": "Manufacturing COOs, logistics operators, industrial automation integrators, robot OEMs, and investors in physical AI companies.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.65,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-action-inventory-repeatable-tasks-by-commissioning-burden-and-safety-risk-struct-8215d5fd",
      "kind": "action",
      "label": "Inventory repeatable tasks by commissioning burden and safety risk; structure pilots around validated productive hours and time-to-commission, not robot count or demo quality.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.7,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2"
      },
      "id": "n-observable-a-major-automotive-or-logistics-deployment-where-the-press-release-na-fbf34b88",
      "kind": "observable",
      "label": "A major automotive or logistics deployment where the press release names the validation, simulation, or task-library layer as the reason the rollout scaled.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2",
        "why": "They sit in the validation path between robot policy training and real-world deployment."
      },
      "id": "n-winner-nvidia-isaac-cosmos-style-simulation-ecosystems-80c6301a",
      "kind": "winner",
      "label": "NVIDIA Isaac/Cosmos-style simulation ecosystems",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2",
        "why": "They turn one-off commissioning labor into repeatable software-enabled deployment."
      },
      "id": "n-winner-industrial-integrators-with-reusable-task-libraries-b6716709",
      "kind": "winner",
      "label": "Industrial integrators with reusable task libraries",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2",
        "why": "They become easier customers and capture automation ROI earlier."
      },
      "id": "n-winner-manufacturers-with-clean-process-data-and-standardized-workcells-c37f1096",
      "kind": "winner",
      "label": "Manufacturers with clean process data and standardized workcells",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2",
        "why": "Hardware demos do not create durable margin if deployment assurance is owned elsewhere."
      },
      "id": "n-loser-undifferentiated-humanoid-oems-0d07ea65",
      "kind": "loser",
      "label": "Undifferentiated humanoid OEMs",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_thesis": "P2",
        "why": "Reusable task libraries and simulation reduce the value of bespoke labor."
      },
      "id": "n-loser-custom-only-automation-integrators-72a805b5",
      "kind": "loser",
      "label": "Custom-only automation integrators",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_field": "rent_path",
        "source_thesis": "P2"
      },
      "id": "n-constraint-rent-flows-to-simulation-and-validation-platforms-robot-integrators-w-ee2a77d2",
      "kind": "constraint",
      "label": "Rent flows to simulation and validation platforms, robot integrators with reusable task libraries, and OEMs that can prove uptime and safety. Commodity bodies get squeezed unless they own the deployment layer.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_field": "next_constraint",
        "source_thesis": "P2"
      },
      "id": "n-constraint-the-next-constraint-becomes-high-quality-real-world-task-data-tactile-762add0c",
      "kind": "constraint",
      "label": "The next constraint becomes high-quality real-world task data, tactile sensing, safety certification labor, and maintenance networks.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_field": "reprices",
        "source_thesis": "P2"
      },
      "id": "n-price-channel-physical-ai-valuation-should-migrate-from-unit-shipments-to-deploy-e5cd43e2",
      "kind": "price_channel",
      "label": "Physical-AI valuation should migrate from unit shipments to deployment software attach rate, commissioning margin, and validated task-hour economics.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_field": "decision_changed",
        "source_thesis": "P2"
      },
      "id": "n-action-automation-capex-integrator-selection-pilot-design-safety-certification-b-7942dd95",
      "kind": "action",
      "label": "Automation capex, integrator selection, pilot design, safety certification budgets, and whether to invest in robot OEMs or deployment-layer tooling.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.55,
      "domain": "robotics / industrial automation",
      "fields": {
        "source_field": "roi_logic",
        "source_thesis": "P2"
      },
      "id": "n-action-a-robot-that-takes-six-months-of-integration-labor-to-deliver-a-narrow-ta-0676de7c",
      "kind": "action",
      "label": "A robot that takes six months of integration labor to deliver a narrow task has poor ROI even if the body is cheap. Deployment tooling pays by converting demos into billable productive hours faster.",
      "verification_status": "derived_from_board"
    },
    {
      "confidence": 0.85,
      "domain": "robotics / industrial automation",
      "fields": {
        "resolves": "2028-12-31",
        "source_thesis": "P2"
      },
      "id": "n-forecast-clause-physical-ai-s-bottleneck-is-certified-deployment-not-robot-bodie-5d45981f",
      "kind": "forecast_clause",
      "label": "Physical AI's bottleneck is certified deployment, not robot bodies.",
      "verification_status": "derived_from_board"
    }
  ],
  "summary": {
    "edge_count": 151,
    "forecast_count": 6,
    "node_count": 116,
    "unknown_count": 24,
    "watch_count": 6
  },
  "unknown_queue": [
    {
      "id": "u-unknown-p1-source-pack-attach-primary-official-source-urls-and-publication-dates-0d464a7b",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P1"
    },
    {
      "id": "u-unknown-p1-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-d1790b30",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P1"
    },
    {
      "id": "u-unknown-p1-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-73f41b1e",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P1"
    },
    {
      "id": "u-unknown-p1-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-b9bed82a",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P1"
    },
    {
      "id": "u-unknown-p2-source-pack-attach-primary-official-source-urls-and-publication-dates-c307c5d6",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P2"
    },
    {
      "id": "u-unknown-p2-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-8fa7996e",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P2"
    },
    {
      "id": "u-unknown-p2-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-abdea055",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P2"
    },
    {
      "id": "u-unknown-p2-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-a38baf06",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P2"
    },
    {
      "id": "u-unknown-p3-source-pack-attach-primary-official-source-urls-and-publication-dates-16a7677b",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-2938fdec",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-dabc5dff",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p3-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-cf5bcda4",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P3"
    },
    {
      "id": "u-unknown-p4-source-pack-attach-primary-official-source-urls-and-publication-dates-3178d8ce",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P4"
    },
    {
      "id": "u-unknown-p4-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-4ddc0cfe",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P4"
    },
    {
      "id": "u-unknown-p4-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-bd61c0c9",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P4"
    },
    {
      "id": "u-unknown-p4-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-66a04ea2",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P4"
    },
    {
      "id": "u-unknown-p5-source-pack-attach-primary-official-source-urls-and-publication-dates-226ac745",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P5"
    },
    {
      "id": "u-unknown-p5-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-54f63573",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P5"
    },
    {
      "id": "u-unknown-p5-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-10425e1c",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P5"
    },
    {
      "id": "u-unknown-p5-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-44a8af16",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P5"
    },
    {
      "id": "u-unknown-p6-source-pack-attach-primary-official-source-urls-and-publication-dates-f70b80f5",
      "kind": "source_pack",
      "owner_agent": "A01",
      "priority": "critical",
      "question": "Attach primary/official source URLs and publication dates to every load-bearing node.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P6"
    },
    {
      "id": "u-unknown-p6-substitute-path-map-substitutes-that-would-kill-or-weaken-the-bottlen-807b30a0",
      "kind": "substitute_path",
      "owner_agent": "A10",
      "priority": "high",
      "question": "Map substitutes that would kill or weaken the bottleneck.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P6"
    },
    {
      "id": "u-unknown-p6-scenario-branch-create-at-least-one-base-upside-downside-scenario-bra-87cd1016",
      "kind": "scenario_branch",
      "owner_agent": "A11",
      "priority": "medium",
      "question": "Create at least one base/upside/downside scenario branch around this thesis.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P6"
    },
    {
      "id": "u-unknown-p6-entity-resolution-resolve-named-entities-to-canonical-companies-agenc-42bc9157",
      "kind": "entity_resolution",
      "owner_agent": "A01",
      "priority": "high",
      "question": "Resolve named entities to canonical companies, agencies, labs, materials, and projects.",
      "required_evidence": "source_url, source_date, quote_or_field, trust_rationale, verification_status",
      "status": "open",
      "thesis_id": "P6"
    }
  ],
  "watchlist": [
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p1-a-hyperscaler-or-top-data-center-reit-announcing-a-100-mw-plus-campus-w-e28b84f7",
      "kill": "Kill if by end 2028 fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, or if transformer and interconnection delays normalize below roughly 24 months in the main US AI data-center markets.",
      "metric": "Track hyperscaler and data-center developer announcements that name on-site firm power, geothermal, or interconnection bypass as the reason for site selection; count 100 MW plus campuses with direct power-development partnerships; track transformer lead times and local moratoria.",
      "owner_agent": "A13",
      "resolves": "2028-12-31",
      "status": "unverified_source_needed",
      "thesis_id": "P1",
      "watch_signal": "A hyperscaler or top data-center REIT announcing a 100 MW plus campus whose stated differentiator is behind-the-meter clean firm power rather than cheap land."
    },
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p2-a-major-automotive-or-logistics-deployment-where-the-press-release-name-f3d2c000",
      "kill": "Kill if by end 2028 humanoid or mobile manipulation deployments scale mainly through turnkey robot hardware with little separate pricing for task validation, commissioning software, or safety case tooling.",
      "metric": "Track robot OEMs or large integrators selling task libraries, simulation validation, or commissioning layers as separate line items; track public claims of 40 percent plus cuts in commissioning time; track safety certification language in physical-AI deployments.",
      "owner_agent": "A13",
      "resolves": "2028-12-31",
      "status": "unverified_source_needed",
      "thesis_id": "P2",
      "watch_signal": "A major automotive or logistics deployment where the press release names the validation, simulation, or task-library layer as the reason the rollout scaled."
    },
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p3-a-major-pharma-chemicals-or-materials-company-publicly-saying-its-ai-di-45f299c5",
      "kill": "Kill if by 2029 model-only AI discovery companies repeatedly produce commercially validated materials or therapies without materially expanding wet-lab or physical-test throughput.",
      "metric": "Track DOE and national-lab testbed awards, pharma/materials partnerships that buy autonomous lab capacity, assay throughput per researcher, and publications where the bottleneck is experiment generation rather than model inference.",
      "owner_agent": "A13",
      "resolves": "2029-12-31",
      "status": "unverified_source_needed",
      "thesis_id": "P3",
      "watch_signal": "A major pharma, chemicals, or materials company publicly saying its AI discovery bottleneck is lab throughput or assay availability, not model quality."
    },
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p4-a-google-samsung-apple-or-meta-product-launch-where-the-lead-ai-feature-cb095912",
      "kill": "Kill if by end 2028 the dominant consumer AI usage remains cloud-chat inside phones and browsers, with wearables and glasses failing to show persistent local context as a major usage mode.",
      "metric": "Track commercial devices that run billion-parameter local models, all-day context capture, or private agentic features on wearables/glasses/phones; track battery complaints, thermal throttling, and local AI developer APIs.",
      "owner_agent": "A13",
      "resolves": "2028-12-31",
      "status": "unverified_source_needed",
      "thesis_id": "P4",
      "watch_signal": "A Google, Samsung, Apple, or Meta product launch where the lead AI feature runs persistently on device and is marketed around private context rather than a bigger cloud model."
    },
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p5-a-well-funded-ai-bio-or-synbio-company-delaying-launch-because-pilot-ca-5270803e",
      "kill": "Kill if by 2030 multiple AI-designed industrial bio-products reach commodity-relevant scale and price parity without scarce pilot capacity, downstream processing, or process-development labor becoming a public bottleneck.",
      "metric": "Track AI-designed or engineered bio-products that fail or delay on COGS and scale-up; track pilot fermentation capacity, downstream bottlenecks, and offtake contracts tied to price parity rather than sustainability premium.",
      "owner_agent": "A13",
      "resolves": "2030-12-31",
      "status": "unverified_source_needed",
      "thesis_id": "P5",
      "watch_signal": "A well-funded AI-bio or synbio company delaying launch because pilot capacity, downstream recovery, or COGS fails despite successful lab design."
    },
    {
      "cadence": "monthly until a source-specific cadence is verified",
      "id": "w-watch-p6-a-fortune-500-rfp-insurance-policy-or-regulator-explicitly-requiring-ag-2fa2b413",
      "kill": "Kill if by mid-2028 large enterprises widely deploy multi-step agents with real system authority using mostly prompt-level guardrails and generic logging, without a separate action-governance budget.",
      "metric": "Track enterprise RFPs requiring agent audit logs, least-privilege controls, rollback, or insurance support; track public agent incidents; track vendors selling action-governance rather than generic model monitoring.",
      "owner_agent": "A13",
      "resolves": "2028-06-30",
      "status": "unverified_source_needed",
      "thesis_id": "P6",
      "watch_signal": "A Fortune 500 RFP, insurance policy, or regulator explicitly requiring agent action logs, approval chains, and rollback for production deployment."
    }
  ]
}

Return a ranked bug list and what exact evidence would fix each issue.
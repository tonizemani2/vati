{
  "thesis_id": "P1",
  "role": "scenario_branch",
  "findings": [
    {
      "scenario": "base (minimum threshold)",
      "narrative": "By end-2028, exactly two hyperscaler-scale campuses (e.g., from Microsoft, Google, Amazon, or a top data-centre REIT like Digital Realty/Equinix) publicly announce that behind-the-meter firm clean generation (geothermal, nuclear, or gas with CCS) was a decisive site-selection factor. Transformer lead times remain elevated (>24 months) in major US markets, and interconnection delays persist, making firm-power sites a visible competitive advantage. The market begins to slowly reprice power-secured land, though most capital still flows to conventional grid-dependent campuses. This meets the forecast's minimum condition and keeps the thesis alive but not over-earning.",
      "probability": 0.30,
      "assumptions": [
        "Current transformer backlog and queue congestion do not materially improve.",
        "At least two large players execute BTM geothermal or nuclear partnerships.",
        "No federal or regulatory intervention drastically simplifies grid interconnection."
      ],
      "timeline": "Key announcements appear between mid-2026 and late 2028. The metric crosses the threshold by 2028-12-31.",
      "reflexivity_triggers": [
        "A major utility filing to expedite interconnection substantially",
        "A hyperscaler walking away from a BTM project citing cost overruns"
      ]
    },
    {
      "scenario": "upside (strong re‑rating)",
      "narrative": "More than two hyperscalers, plus multiple data-center developers, publicly tie 100 MW+ campus decisions to behind-the-meter firm clean power. Geothermal developers (e.g., Fervo, Eavor) and advanced nuclear plays secure multiple offtake agreements with hyperscalers. Transformer lead times worsen (approaching 3–4 years in key markets) and local moratoria on new data center load spread. As a result, time-to-energize becomes the primary valuation metric for data-center real estate. Power-secured land options, PPAs, and development rights reprice sharply, and public market investors differentiate between grid-dependent and power-secured REITs. The thesis transitions from early signal to consensus, and the rent migration described in the thesis is unambiguous.",
      "probability": 0.22,
      "assumptions": [
        "Geothermal drilling capacity expands faster than currently anticipated, or hyperscalers provide development capital.",
        "At least one major new interconnection queue reform effort fails or is too slow.",
        "A high-profile delay (e.g., a flagship campus stuck in queue for 3+ years) makes BTM power a board-level priority for multiple hyperscalers."
      ],
      "timeline": "Evidence accumulates through 2027; by mid-2028 the market starts discounting grid-dependent shells.",
      "reflexivity_triggers": [
        "Breakthrough in long-duration storage that suddenly makes grid connection more reliable",
        "Political backlash against data-center load leading to moratoria in multiple markets"
      ]
    },
    {
      "scenario": "downside (thesis breaks)",
      "narrative": "By end-2028, fewer than two hyperscaler-scale campuses publicly secure behind-the-meter firm clean generation as a core siting advantage, OR transformer and interconnection delays normalize below ~24 months in main US AI data-center markets. The forecast's kill condition is met. Either grid infrastructure expands faster than expected (e.g., supply chain bottlenecks ease, regulatory reforms accelerate interconnection), or behind-the-meter firm power is too costly, too slow, or technically not viable at scale. Hyperscalers may instead lean on grid batteries, on-site gas backup, or load-shifting to cope, and the siting story reverts to land+cost+fiber. The thesis is falsified, and the clause resolves false.",
      "probability": 0.48,
      "assumptions": [
        "Transformer manufacturing capacity ramps up significantly by 2027.",
        "FERC or state-level interconnection reforms reduce queue times substantially.",
        "No breakthrough in next-generation geothermal or small modular nuclear that meets hyperscaler timelines and risk profiles."
      ],
      "timeline": "By 2028-12-31, the cumulative evidence fails the kill condition.",
      "reflexivity_triggers": [
        "A major transformer factory opening in the US",
        "Congressional action to fast-track transmission"
      ]
    }
  ],
  "proposed_nodes": [
    {
      "id": "n-scenario-branch-base-p1",
      "label": "Base scenario: minimum threshold met, thesis alive",
      "kind": "scenario_branch",
      "confidence": 0.8,
      "fields": {
        "probability": 0.30,
        "description": "Exactly two hyperscaler-scale campuses meet the kill-condition threshold, with no radical improvement in interconnection delays. The forecast is true but not dominant.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-scenario-branch-upside-p1",
      "label": "Upside scenario: strong re‑rating, firm-power siting becomes consensus",
      "kind": "scenario_branch",
      "confidence": 0.7,
      "fields": {
        "probability": 0.22,
        "description": "More than two public BTM firm-power campuses, worsening transformer delays, and a clear repricing of power-secured assets. The thesis earns its vision probability.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-scenario-branch-downside-p1",
      "label": "Downside scenario: kill condition met, thesis false",
      "kind": "scenario_branch",
      "confidence": 0.8,
      "fields": {
        "probability": 0.48,
        "description": "Fewer than two qualifying campuses OR transformer/interconnection delays normalize below 24 months. The forecast clause resolves false.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-refutation-path-grid-battery-alternative-p1",
      "label": "Refutation: grid batteries and load-shifting obviate BTM imperative",
      "kind": "refutation",
      "confidence": 0.4,
      "fields": {
        "prob_delta": -0.05,
        "description": "If utility-scale batteries or AI-driven load shifting become cheap and fast, hyperscalers may not need to own generation and can still avoid interconnection delays.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-refutation-path-transformer-boom-p1",
      "label": "Refutation: rapid expansion of transformer manufacturing",
      "kind": "refutation",
      "confidence": 0.5,
      "fields": {
        "prob_delta": -0.15,
        "description": "Major new transformer factories (e.g., from Siemens, Hitachi Energy, or US government incentives) come online by 2027, cutting lead times below 24 months.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    },
    {
      "id": "n-refutation-path-interconnection-reform-p1",
      "label": "Refutation: FERC or state interconnection queue reform",
      "kind": "refutation",
      "confidence": 0.6,
      "fields": {
        "prob_delta": -0.10,
        "description": "Regulatory changes (e.g., cluster studies, fast-track processes) reduce grid interconnection timelines significantly.",
        "thesis_id": "P1"
      },
      "verification_status": "proposed"
    }
  ],
  "proposed_edges": [
    {
      "src": "n-scenario-branch-base-p1",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "scenario_branch_of",
      "rationale": "Base scenario is a possible resolution that keeps the thesis true but at minimum threshold.",
      "confidence": 0.9
    },
    {
      "src": "n-scenario-branch-upside-p1",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "scenario_branch_of",
      "rationale": "Upside scenario is a more extreme positive resolution, consistent with the thesis vision.",
      "confidence": 0.9
    },
    {
      "src": "n-scenario-branch-downside-p1",
      "dst": "n-thesis-p1-the-ai-frontier-moves-from-model-access-to-firm-power-siting-b3db70cf",
      "rel": "scenario_branch_of",
      "rationale": "Downside scenario is the path where the thesis is falsified via kill condition.",
      "confidence": 0.9
    },
    {
      "src": "n-scenario-branch-downside-p1",
      "dst": "n-kill-condition-kill-if-by-end-2028-fewer-than-two-hyperscaler-scale-campuses-pub-495cf67f",
      "rel": "triggers",
      "rationale": "Downside scenario directly meets the kill condition logic.",
      "confidence": 0.95
    },
    {
      "src": "n-scenario-branch-upside-p1",
      "dst": "n-winner-geothermal-and-clean-firm-power-developers-d26c8b7d",
      "rel": "strengthens",
      "rationale": "Upside scenario creates outsized returns for firm-power developers.",
      "confidence": 0.8
    },
    {
      "src": "n-scenario-branch-downside-p1",
      "dst": "n-loser-grid-dependent-campus-projects-in-congested-markets-aab89810",
      "rel": "weakens",
      "rationale": "Downside scenario means grid-dependent projects face less disadvantage if delays normalize.",
      "confidence": 0.7
    },
    {
      "src": "n-refutation-path-grid

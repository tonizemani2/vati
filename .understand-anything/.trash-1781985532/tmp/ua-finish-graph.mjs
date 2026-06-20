#!/usr/bin/env node

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = "/Users/emizemani/Desktop/predictthefuture";
const UA = join(ROOT, ".understand-anything");
const INTER = join(UA, "intermediate");

const scan = JSON.parse(readFileSync(join(INTER, "scan-result.json"), "utf8"));
const merged = JSON.parse(readFileSync(join(INTER, "assembled-graph.json"), "utf8"));
const nodes = merged.nodes || [];
const edges = merged.edges || [];

const fileLevelTypes = new Set([
  "file",
  "config",
  "document",
  "service",
  "pipeline",
  "table",
  "schema",
  "resource",
  "endpoint",
]);

const fileNodes = nodes.filter((node) => fileLevelTypes.has(node.type));
const byPath = new Map(fileNodes.map((node) => [node.filePath, node.id]));

const doctrineRootDocs = new Set([
  "README.md",
  "BRIEFING.md",
  "VATI.md",
  "FUTURE_MAP.md",
  "VATI_WORLD_GRAPH.md",
  "doctrine.md",
  "proof.md",
  "plan.md",
  "CONSTITUTION.md",
  "POPE_ULTRA.md",
  "FORECAST_LLM.md",
  "FORECAST_SYSTEM_CONTROL_PLANE.md",
  "EDGE_DATASET_PLAN.md",
  "WORLD_DATA_PIPELINE.md",
  "LEADERSHIP_AND_SUPERFORECASTING.md",
  "NEGATIVE_RESULT_FINETUNE.md",
  "PATENT_NEEDLES.md",
  "RESEARCH_PAPERS_OPERATION.md",
  "DATA_LAYER_PLAN.md",
  "REVIEW.md",
  "OVERNIGHT_BRIEFING.md",
  "AGENTS.md",
  "CLAUDE.md",
  "VOICE.md",
  "redteam.md",
  "execution.md",
  "humanizer-context.md",
  "newbenchmarksplan.md",
]);

const operationsRootDocs = new Set([
  "OPS.md",
  "SECURITY_CLOUDFLARE.md",
  "CLOUD_COSTS.md",
  ".gitignore",
]);

const layerDefs = [
  {
    id: "layer:doctrine",
    name: "Doctrine",
    description: "Core method, doctrine, positioning, and repo-level guidance that explain what Vati is and how the system should think.",
    nodeIds: [],
  },
  {
    id: "layer:engine",
    name: "Engine",
    description: "The Python forecasting engine, world-model code, adapters, feeds, and local runtime artifacts that drive the core product logic.",
    nodeIds: [],
  },
  {
    id: "layer:surfaces",
    name: "Surfaces",
    description: "User-facing product surfaces and dashboards across the cockpit, chat, site, and landing applications.",
    nodeIds: [],
  },
  {
    id: "layer:research",
    name: "Research",
    description: "Research artifacts, experiment scaffolding, and thesis materials that support and challenge the forecasting system.",
    nodeIds: [],
  },
  {
    id: "layer:operations",
    name: "Operations",
    description: "Automation, workflow, deployment, and operator tooling used to run the repository and keep the system moving.",
    nodeIds: [],
  },
  {
    id: "layer:tests",
    name: "Tests",
    description: "Verification coverage for the engine and product surfaces, including direct checks on data, graph, and workflow behavior.",
    nodeIds: [],
  },
  {
    id: "layer:misc",
    name: "Misc",
    description: "Supporting files that do not fit neatly into the main engine, surface, research, or operations lanes.",
    nodeIds: [],
  },
];

const layerById = new Map(layerDefs.map((layer) => [layer.id, layer]));

function chooseLayer(node) {
  const fp = node.filePath || "";

  if (node.type === "service" || node.type === "pipeline" || node.type === "resource") {
    return "layer:operations";
  }
  if (fp.startsWith("tests/")) return "layer:tests";
  if (
    fp.startsWith("engine/") ||
    fp === "pyproject.toml" ||
    fp === "uv.lock" ||
    fp === "forecast.db"
  ) {
    return "layer:engine";
  }
  if (
    fp.startsWith("chat/") ||
    fp.startsWith("site/") ||
    fp.startsWith("landing/") ||
    fp.startsWith("cockpit/") ||
    fp.startsWith("content/")
  ) {
    return "layer:surfaces";
  }
  if (
    fp.startsWith("research/") ||
    fp.startsWith("paper_beyond_brier/") ||
    fp.startsWith("experiments/")
  ) {
    return "layer:research";
  }
  if (
    fp.startsWith(".claude/") ||
    fp.startsWith("scripts/") ||
    fp.startsWith("training/") ||
    fp.startsWith(".understand-anything/") ||
    fp.startsWith(".mac_fix_backup/")
  ) {
    return "layer:operations";
  }
  if (doctrineRootDocs.has(fp)) return "layer:doctrine";
  if (operationsRootDocs.has(fp)) return "layer:operations";
  if (node.type === "document" && !fp.includes("/")) return "layer:doctrine";
  return "layer:misc";
}

for (const node of fileNodes) {
  const layerId = chooseLayer(node);
  layerById.get(layerId).nodeIds.push(node.id);
}

for (const layer of layerDefs) {
  layer.nodeIds = Array.from(new Set(layer.nodeIds)).sort((a, b) => a.localeCompare(b));
}

function pickIds(paths) {
  return paths.map((path) => byPath.get(path)).filter(Boolean);
}

const tour = [
  {
    order: 1,
    title: "Start With The Thesis",
    description: "Read the repository from the outside in: the README and top-level Vaticinus briefs explain the product claim, why leak-free forecasting matters, and what this repo is trying to prove.",
    nodeIds: pickIds(["README.md", "BRIEFING.md", "VATI.md"]),
  },
  {
    order: 2,
    title: "Anchor The Method",
    description: "These files define the method and guardrails: doctrine, constitution, proof standards, and the future-map framing that keeps the project from drifting into hand-wavy AI prose.",
    nodeIds: pickIds(["doctrine.md", "CONSTITUTION.md", "proof.md", "FUTURE_MAP.md", "VATI_WORLD_GRAPH.md"]),
  },
  {
    order: 3,
    title: "Follow The Core Engine",
    description: "The engine layer is where forecasting, scoring, world-graph compilation, and local orchestration actually happen. This is the technical heart of the repo.",
    nodeIds: pickIds(["engine/cli.py", "engine/forecast.py", "engine/world_graph.py", "engine/world_graph_deepseek.py"]),
  },
  {
    order: 4,
    title: "Inspect Data And Feeds",
    description: "These files show how evidence enters the system through feeds, world-state ingestion, and offload paths. They are the bridge between abstract theses and observable signals.",
    nodeIds: pickIds(["engine/feeds/collect_all.py", "engine/world_state.py", "engine/data_offload.py", "engine/rawstore.py"]),
  },
  {
    order: 5,
    title: "See The Product Surfaces",
    description: "The repo has several outward-facing surfaces: a cockpit, a chat product, and public site layers. This step shows where the same underlying system gets rendered for users.",
    nodeIds: pickIds(["cockpit/app/page.tsx", "cockpit/components/supply-graph.tsx", "chat/package.json", "site/package.json", "landing/package.json"]),
  },
  {
    order: 6,
    title: "Watch The Operator Workflows",
    description: "Operational files tie the method to real execution: agent workflows, run scripts, and ops notes for longer-running or more fragile forecasting jobs.",
    nodeIds: pickIds([".claude/workflows/pope-mega.js", "scripts/run_deepseek_resume_safe.sh", "OPS.md"]),
  },
  {
    order: 7,
    title: "Close With Verification",
    description: "The tests show what the repo considers important enough to lock down, especially around world-graph behavior, data collection, and forecasting control paths.",
    nodeIds: pickIds(["tests/test_world_graph.py", "tests/test_pope_ultra.py", "tests/test_collect_all.py"]),
  },
].filter((step) => step.nodeIds.length > 0);

const graph = {
  version: "1.0.0",
  project: {
    name: scan.name,
    languages: scan.languages,
    frameworks: scan.frameworks,
    description: scan.description,
    analyzedAt: new Date().toISOString(),
    gitCommitHash: "9260651ce2a679b3905413a0518824dc5a550f52",
  },
  nodes,
  edges,
  layers: layerDefs.filter((layer) => layer.nodeIds.length > 0),
  tour,
};

mkdirSync(INTER, { recursive: true });
writeFileSync(join(INTER, "layers.json"), JSON.stringify(graph.layers, null, 2) + "\n");
writeFileSync(join(INTER, "tour.json"), JSON.stringify(graph.tour, null, 2) + "\n");
writeFileSync(join(INTER, "assembled-graph.json"), JSON.stringify(graph, null, 2) + "\n");

console.log(
  JSON.stringify(
    {
      layers: graph.layers.map((layer) => ({ id: layer.id, count: layer.nodeIds.length })),
      tourSteps: graph.tour.length,
    },
    null,
    2,
  ),
);

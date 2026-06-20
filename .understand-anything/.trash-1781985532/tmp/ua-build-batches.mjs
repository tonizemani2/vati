#!/usr/bin/env node

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, basename, extname } from "node:path";
import { spawnSync } from "node:child_process";

const PROJECT_ROOT = "/Users/emizemani/Desktop/predictthefuture";
const TMP_DIR = join(PROJECT_ROOT, ".understand-anything", "tmp");
const INTER_DIR = join(PROJECT_ROOT, ".understand-anything", "intermediate");
const SKILL_DIR =
  "/Users/emizemani/.understand-anything/repo/understand-anything-plugin/skills/understand";
const BATCHES_PATH = join(INTER_DIR, "batches.json");

const batchesDoc = JSON.parse(readFileSync(BATCHES_PATH, "utf8"));
const exportsByPath = batchesDoc.exportsByPath || {};

mkdirSync(TMP_DIR, { recursive: true });
mkdirSync(INTER_DIR, { recursive: true });

function complexityFromLines(lines = 0) {
  if (lines > 200) return "complex";
  if (lines >= 50) return "moderate";
  return "simple";
}

function isTestPath(filePath) {
  return (
    /(^|\/)tests?\//.test(filePath) ||
    /(^|\/)test_/.test(filePath) ||
    /\.test\./.test(filePath) ||
    /\.spec\./.test(filePath) ||
    /_test\./.test(filePath) ||
    /Tests?\./.test(filePath)
  );
}

function normalizeTags(tags) {
  const out = [];
  const seen = new Set();
  for (const raw of tags) {
    const cleaned = String(raw || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    if (!cleaned || seen.has(cleaned)) continue;
    seen.add(cleaned);
    out.push(cleaned);
  }
  return out.slice(0, 5);
}

function inferFileNodeType(fileMeta) {
  const filePath = fileMeta.path;
  const category = fileMeta.fileCategory;
  const lower = filePath.toLowerCase();
  const ext = extname(lower);

  if (category === "config") return "config";
  if (category === "docs") return "document";
  if (category === "infra") {
    if (
      lower.includes(".github/workflows/") ||
      lower === ".gitlab-ci.yml" ||
      lower.includes(".circleci/") ||
      basename(lower) === "jenkinsfile"
    ) {
      return "pipeline";
    }
    if (ext === ".tf" || ext === ".tfvars" || basename(lower) === "vagrantfile") {
      return "resource";
    }
    return "service";
  }
  if (category === "data") {
    if (ext === ".graphql" || ext === ".gql" || ext === ".proto" || ext === ".prisma") {
      return "schema";
    }
    if (ext === ".sql") return "table";
    if (lower.includes("openapi") || lower.includes("swagger")) return "endpoint";
    return "file";
  }
  return "file";
}

function fileNodeId(fileMeta, nodeType) {
  const filePath = fileMeta.path;
  if (nodeType === "config") return `config:${filePath}`;
  if (nodeType === "document") return `document:${filePath}`;
  if (nodeType === "service") return `service:${filePath}`;
  if (nodeType === "pipeline") return `pipeline:${filePath}`;
  if (nodeType === "resource") return `resource:${filePath}`;
  if (nodeType === "schema") return `schema:${filePath}`;
  if (nodeType === "endpoint") return `endpoint:${filePath}`;
  if (nodeType === "table") return `file:${filePath}`;
  return `file:${filePath}`;
}

function inferFileTags(fileMeta, nodeType) {
  const filePath = fileMeta.path;
  const base = basename(filePath);
  const tags = [];

  if (isTestPath(filePath)) tags.push("test", "verification");
  if (base === "README.md") tags.push("documentation", "entry-point", "overview");
  if (base === "package.json" || base === "pyproject.toml") {
    tags.push("configuration", "build-system", "project-manifest");
  }
  if (base.startsWith("next.config")) tags.push("configuration", "nextjs", "build-system");
  if (base.includes("tsconfig")) tags.push("configuration", "typescript", "build-system");
  if (filePath.includes("engine/")) tags.push("forecasting-engine");
  if (filePath.includes("world_graph")) tags.push("world-graph");
  if (filePath.includes("graph")) tags.push("graph");
  if (filePath.includes("forecast")) tags.push("forecasting");
  if (filePath.includes("chat")) tags.push("chat");
  if (filePath.includes("site") || filePath.includes("landing")) tags.push("frontend");
  if (filePath.includes("cockpit")) tags.push("dashboard");
  if (filePath.includes("adapter")) tags.push("integration");
  if (filePath.includes("db") || filePath.includes("sql")) tags.push("database");
  if (filePath.includes("cli")) tags.push("cli");

  if (nodeType === "document") tags.push("documentation");
  if (nodeType === "config") tags.push("configuration");
  if (nodeType === "service") tags.push("infrastructure", "deployment");
  if (nodeType === "pipeline") tags.push("ci-cd", "automation");
  if (nodeType === "resource") tags.push("infrastructure", "provisioning");
  if (nodeType === "schema") tags.push("schema-definition", "api-schema");
  if (nodeType === "endpoint") tags.push("api-schema", "endpoint");

  if (fileMeta.fileCategory === "script") tags.push("script", "automation");
  if (fileMeta.fileCategory === "markup") tags.push("ui");
  if (fileMeta.fileCategory === "code") tags.push("code");

  if (tags.length < 3) {
    tags.push(nodeType, fileMeta.fileCategory, base.replace(/\.[^.]+$/, ""));
  }
  return normalizeTags(tags);
}

function inferFileSummary(fileMeta, nodeType, result) {
  const filePath = fileMeta.path;
  const base = basename(filePath);
  const metrics = result.metrics || {};
  const bits = [];

  if (nodeType === "document") {
    return `Documentation file covering ${base.replace(/\.[^.]+$/, "")} for the Vati repository and its forecasting workflows.`;
  }
  if (nodeType === "config") {
    return `Configuration file for ${base} that shapes build, runtime, or tooling behavior in this repository.`;
  }
  if (nodeType === "service") {
    return `Infrastructure definition in ${base} used to package, run, or expose part of the Vati system.`;
  }
  if (nodeType === "pipeline") {
    return `Pipeline configuration in ${base} that automates checks, builds, or deployment tasks for the repository.`;
  }
  if (nodeType === "resource") {
    return `Infrastructure resource definition in ${base} for provisioning or operating external services.`;
  }
  if (nodeType === "schema") {
    return `Schema file ${base} defining structured data exchanged or validated by the application.`;
  }
  if (nodeType === "endpoint") {
    return `API description file ${base} capturing externally visible endpoints or request/response structure.`;
  }

  if (metrics.functionCount) bits.push(`${metrics.functionCount} function${metrics.functionCount === 1 ? "" : "s"}`);
  if (metrics.classCount) bits.push(`${metrics.classCount} class${metrics.classCount === 1 ? "" : "es"}`);
  if (metrics.importCount) bits.push(`${metrics.importCount} internal import${metrics.importCount === 1 ? "" : "s"}`);

  const scope =
    filePath.startsWith("engine/")
      ? "forecasting engine"
      : filePath.startsWith("chat/")
        ? "chat surface"
        : filePath.startsWith("site/")
          ? "public site"
          : filePath.startsWith("cockpit/")
            ? "cockpit dashboard"
            : filePath.startsWith("landing/")
              ? "landing surface"
              : "repository";

  const detail = bits.length ? ` It contains ${bits.join(", ")}.` : "";
  return `${base} is a ${fileMeta.fileCategory} asset in the ${scope}.${detail}`;
}

function functionSummary(name, filePath) {
  return `Defines ${name} in ${basename(filePath)}, contributing to that file's local behavior or exported API.`;
}

function classSummary(name, filePath) {
  return `Defines ${name} in ${basename(filePath)}, encapsulating reusable behavior or state for this module.`;
}

function functionTags(name, filePath) {
  const tags = ["function", "implementation"];
  if (/^test/i.test(name) || isTestPath(filePath)) tags.push("test");
  if (/^use[A-Z]/.test(name)) tags.push("hook");
  if (/cli|main|run|entry/i.test(name)) tags.push("entry-point");
  if (/format|parse|normalize|build/i.test(name)) tags.push("utility");
  if (/fetch|request|query|search/i.test(name)) tags.push("data-access");
  tags.push(basename(filePath).replace(/\.[^.]+$/, ""));
  return normalizeTags(tags);
}

function classTags(name, filePath) {
  const tags = ["class", "implementation"];
  if (/controller|handler/i.test(name)) tags.push("api-handler");
  if (/model|schema/i.test(name)) tags.push("data-model");
  if (/service/i.test(name)) tags.push("service");
  if (/client/i.test(name)) tags.push("integration");
  tags.push(basename(filePath).replace(/\.[^.]+$/, ""));
  return normalizeTags(tags);
}

function lineRange(start, end) {
  return [Number(start || 1), Number(end || start || 1)];
}

function isSignificantFunction(fn, exportedNames) {
  const lines = (Number(fn.endLine || fn.startLine || 1) - Number(fn.startLine || 1)) + 1;
  return lines >= 10 || exportedNames.has(fn.name);
}

function isSignificantClass(cls, exportedNames) {
  const lines = (Number(cls.endLine || cls.startLine || 1) - Number(cls.startLine || 1)) + 1;
  const methods = Array.isArray(cls.methods) ? cls.methods.length : 0;
  return methods >= 2 || lines >= 20 || exportedNames.has(cls.name);
}

function guessCrossBatchTarget(filePath, callee, importedPaths, neighborMap) {
  const imported = importedPaths || [];
  for (const targetPath of imported) {
    const exported = exportsByPath[targetPath] || [];
    if (!exported.includes(callee)) continue;
    const kind = /^[A-Z]/.test(callee) ? "class" : "function";
    return `${kind}:${targetPath}:${callee}`;
  }

  const neighborEntries = neighborMap?.[filePath] || [];
  for (const neighbor of neighborEntries) {
    if (!(neighbor.symbols || []).includes(callee)) continue;
    const kind = /^[A-Z]/.test(callee) ? "class" : "function";
    return `${kind}:${neighbor.path}:${callee}`;
  }

  return null;
}

function buildBatch(batch) {
  const batchIndex = batch.batchIndex;
  const inputPath = join(TMP_DIR, `ua-file-analyzer-input-${batchIndex}.json`);
  const extractPath = join(TMP_DIR, `ua-file-extract-results-${batchIndex}.json`);

  if (!existsSync(extractPath)) {
    writeFileSync(
      inputPath,
      JSON.stringify(
        {
          projectRoot: PROJECT_ROOT,
          batchFiles: batch.files,
          batchImportData: batch.batchImportData,
        },
        null,
        2,
      ) + "\n",
    );
    const proc = spawnSync(
      "node",
      [join(SKILL_DIR, "extract-structure.mjs"), inputPath, extractPath],
      { cwd: PROJECT_ROOT, encoding: "utf8" },
    );
    if (proc.status !== 0) {
      throw new Error(`extract-structure failed for batch ${batchIndex}: ${proc.stderr || proc.stdout}`);
    }
  }

  const extract = JSON.parse(readFileSync(extractPath, "utf8"));
  const nodes = [];
  const edges = [];
  const nodeOwners = new Map();
  const localNodesByName = new Map();
  const fileNodeByPath = new Map();

  const batchFileMeta = new Map(batch.files.map((file) => [file.path, file]));

  for (const result of extract.results || []) {
    const fileMeta = batchFileMeta.get(result.path) || {
      path: result.path,
      language: result.language || "unknown",
      sizeLines: result.totalLines || 0,
      fileCategory: result.fileCategory || "code",
    };

    const nodeType = inferFileNodeType(fileMeta);
    const fileId = fileNodeId(fileMeta, nodeType);
    const fileNode = {
      id: fileId,
      type: nodeType,
      name: basename(result.path),
      filePath: result.path,
      summary: inferFileSummary(fileMeta, nodeType, result),
      tags: inferFileTags(fileMeta, nodeType),
      complexity: complexityFromLines(result.nonEmptyLines || result.totalLines || fileMeta.sizeLines || 0),
    };
    nodes.push(fileNode);
    nodeOwners.set(fileId, result.path);
    fileNodeByPath.set(result.path, fileId);

    const exportedNames = new Set((result.exports || []).map((entry) => entry.name).filter(Boolean));
    const localNameMap = new Map();

    for (const fn of result.functions || []) {
      if (!isSignificantFunction(fn, exportedNames)) continue;
      const fnId = `function:${result.path}:${fn.name}`;
      const fnNode = {
        id: fnId,
        type: "function",
        name: fn.name,
        filePath: result.path,
        lineRange: lineRange(fn.startLine, fn.endLine),
        summary: functionSummary(fn.name, result.path),
        tags: functionTags(fn.name, result.path),
        complexity: complexityFromLines((Number(fn.endLine || fn.startLine || 1) - Number(fn.startLine || 1)) + 1),
      };
      nodes.push(fnNode);
      nodeOwners.set(fnId, result.path);
      localNameMap.set(fn.name, fnId);
      edges.push({
        source: fileId,
        target: fnId,
        type: "contains",
        direction: "forward",
        weight: 1.0,
      });
      if (exportedNames.has(fn.name)) {
        edges.push({
          source: fileId,
          target: fnId,
          type: "exports",
          direction: "forward",
          weight: 0.8,
        });
      }
    }

    for (const cls of result.classes || []) {
      if (!isSignificantClass(cls, exportedNames)) continue;
      const clsId = `class:${result.path}:${cls.name}`;
      const clsNode = {
        id: clsId,
        type: "class",
        name: cls.name,
        filePath: result.path,
        lineRange: lineRange(cls.startLine, cls.endLine),
        summary: classSummary(cls.name, result.path),
        tags: classTags(cls.name, result.path),
        complexity: complexityFromLines((Number(cls.endLine || cls.startLine || 1) - Number(cls.startLine || 1)) + 1),
      };
      nodes.push(clsNode);
      nodeOwners.set(clsId, result.path);
      localNameMap.set(cls.name, clsId);
      edges.push({
        source: fileId,
        target: clsId,
        type: "contains",
        direction: "forward",
        weight: 1.0,
      });
      if (exportedNames.has(cls.name)) {
        edges.push({
          source: fileId,
          target: clsId,
          type: "exports",
          direction: "forward",
          weight: 0.8,
        });
      }
    }

    localNodesByName.set(result.path, localNameMap);
  }

  for (const file of batch.files) {
    const fileId = fileNodeByPath.get(file.path) || `file:${file.path}`;
    const imports = batch.batchImportData?.[file.path] || [];
    for (const targetPath of imports) {
      edges.push({
        source: fileId,
        target: `file:${targetPath}`,
        type: "imports",
        direction: "forward",
        weight: 0.7,
      });
    }
  }

  for (const result of extract.results || []) {
    const localNameMap = localNodesByName.get(result.path) || new Map();
    const imports = batch.batchImportData?.[result.path] || [];
    for (const call of result.callGraph || []) {
      const sourceId = localNameMap.get(call.caller) || fileNodeByPath.get(result.path);
      if (!sourceId) continue;

      let targetId = localNameMap.get(call.callee) || null;
      if (!targetId) {
        targetId = guessCrossBatchTarget(result.path, call.callee, imports, batch.neighborMap);
      }
      if (!targetId || sourceId === targetId) continue;
      edges.push({
        source: sourceId,
        target: targetId,
        type: "calls",
        direction: "forward",
        weight: 0.8,
      });
    }
  }

  const dedupedNodes = [];
  const seenNodes = new Set();
  for (const node of nodes) {
    if (seenNodes.has(node.id)) continue;
    seenNodes.add(node.id);
    dedupedNodes.push(node);
  }

  const dedupedEdges = [];
  const seenEdges = new Set();
  for (const edge of edges) {
    if (!edge.source || !edge.target || edge.source === edge.target) continue;
    const key = `${edge.source}|${edge.target}|${edge.type}`;
    if (seenEdges.has(key)) continue;
    seenEdges.add(key);
    dedupedEdges.push(edge);
  }

  return { nodes: dedupedNodes, edges: dedupedEdges, nodeOwners };
}

function writeBatchParts(batchIndex, built) {
  const fileOrder = Array.from(new Set(Array.from(built.nodeOwners.values()))).sort((a, b) =>
    a.localeCompare(b),
  );
  const nodeCount = built.nodes.length;
  const edgeCount = built.edges.length;
  const parts = nodeCount <= 60 && edgeCount <= 120 ? 1 : Math.ceil(Math.max(nodeCount / 60, edgeCount / 120));
  const groupSize = Math.ceil(fileOrder.length / parts);
  const written = [];

  const ownerByNodeId = built.nodeOwners;

  for (let index = 0; index < parts; index += 1) {
    const ownedPaths = new Set(fileOrder.slice(index * groupSize, (index + 1) * groupSize));
    const nodes = built.nodes.filter((node) => ownedPaths.has(ownerByNodeId.get(node.id)));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const edges = built.edges.filter((edge) => nodeIds.has(edge.source));
    const payload = { nodes, edges };
    const outPath =
      parts === 1
        ? join(INTER_DIR, `batch-${batchIndex}.json`)
        : join(INTER_DIR, `batch-${batchIndex}-part-${index + 1}.json`);
    writeFileSync(outPath, JSON.stringify(payload, null, 2) + "\n");
    written.push(outPath);
  }

  return written;
}

const writtenFiles = [];

for (const batch of batchesDoc.batches) {
  const built = buildBatch(batch);
  writtenFiles.push(...writeBatchParts(batch.batchIndex, built));
}

process.stdout.write(`Wrote ${writtenFiles.length} batch graph file(s).\n`);

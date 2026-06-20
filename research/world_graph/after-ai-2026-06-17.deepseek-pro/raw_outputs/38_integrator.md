Below is the integration standard and the JSON Schema that governs how role-output patches must be structured before they can be merged into `world_graph.patch.json`. The schema is designed to keep facts separate from hypotheses, prevent invention of project‑specific detail, and ensure that only source‑backed evidence is promoted to decision‑grade status.

---

### Integration Standard (Principles)

1. **Strict provenance** – Every node or edge must carry a `verification_status`, the primary source URL, publication date, and a quote or field excerpt. No “fill‑in‑the‑blank” inventions (permits, people, prices, dates) are allowed.
2. **Separation of facts and forecasts** – Forecast clauses remain falsifiable; patches may add new observations or refutations but may not alter the clause’s `clause_p`, `kill`, or `metric` without a new source review.
3. **Patch‑only merge** – Role outputs are delivered as JSON patch objects. Only objects that satisfy the schema below are applied to the world graph.
4. **Task resolution** – When a patch completes an unknown task (e.g., `source_pack`), it must reference the original task `id` and close it by setting its `status` to `done`.
5. **Confidence control** – All added facts carry a `confidence` (0‑1) and a machine‑readable `trust_rationale`.

---

### JSON Schema: world_graph.patch.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vaticinus.world/schemas/world-graph-patch.json",
  "title": "World Graph Patch – Verified Role Output",
  "description": "A patch payload that adds or updates graph objects (nodes, edges, verification tasks) while enforcing provenance and avoiding unverified claims.",
  "type": "object",
  "required": ["patch_id", "applied_at", "source_role", "operations"],
  "properties": {
    "patch_id": {
      "type": "string",
      "description": "Unique identifier, e.g. 'patch-p1-source-pack-20260619'"
    },
    "applied_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO‑8601 timestamp of patch creation"
    },
    "source_role": {
      "type": "string",
      "enum": [
        "verification_source_pack",
        "verification_substitute_path",
        "verification_scenario_branch",
        "verification_entity_resolution"
      ],
      "description": "Which verification role produced this patch"
    },
    "related_thesis_id": {
      "type": "string",
      "pattern": "^P[1-6]$",
      "description": "Thesis this patch relates to (P1–P6)"
    },
    "operations": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          { "$ref": "#/$defs/nodeOperation" },
          { "$ref": "#/$defs/edgeOperation" },
          { "$ref": "#/$defs/taskResolution" }
        ]
      }
    }
  },
  "$defs": {
    "baseOperation": {
      "type": "object",
      "required": ["op", "timestamp"],
      "properties": {
        "op": {
          "type": "string",
          "enum": ["add", "update", "remove"],
          "description": "Graph operation: 'add' a new object, 'update' existing, or 'remove' (only allowed for unverified nodes)"
        },
        "timestamp": {
          "type": "string",
          "format": "date-time"
        },
        "resolves_task": {
          "type": "string",
          "description": "ID of the unknown task this operation fulfills (optional for purely additive patches)"
        }
      }
    },
    "provenance": {
      "type": "object",
      "required": ["source_url", "source_date", "quote_or_field", "trust_rationale"],
      "properties": {
        "source_url": {
          "type": "string",
          "format": "uri"
        },
        "source_date": {
          "type": "string",
          "format": "date"
        },
        "quote_or_field": {
          "type": "string",
          "description": "Exact text or data field from source that justifies this fact"
        },
        "trust_rationale": {
          "type": "string",
          "enum": [
            "official_publication",
            "company_press_release",
            "government_agency_statement",
            "peer_reviewed_journal",
            "trade_press_report",
            "analyst_report_primary",
            "expert_interview",
            "public_filing"
          ],
          "description": "Why this source is trusted and how it was obtained"
        }
      }
    },
    "confidence": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 1.0,
      "description": "Confidence that this fact is true (≥0.5 required for adding to graph, <0.9 still considered 'unverified' until further cross‑check)"
    },
    "verificationDecision": {
      "type": "string",
      "enum": [
        "verified_from_source",
        "partially_verified",
        "corroborated_by_multiple",
        "needs_expert_review",
        "disputed"
      ],
      "description": "The final verification status to be stamped on the node/edge after this patch"
    },
    "nodeFields": {
      "type": "object",
      "description": "Free‑form fields for the node, but must not contain any of the forbidden keys",
      "patternProperties": {
          "^(?!.*(permit|people|contacts|project_names_like_Stargate|pricing_exact|dates_in_future_invented)).*$": {}
      },
      "additionalProperties": false
    },
    "nodeOperation": {
      "allOf": [
        { "$ref": "#/$defs/baseOperation" },
        {
          "type": "object",
          "required": ["node_id", "payload"],
          "properties": {
            "node_id": {
              "type": "string",
              "description": "ID of the node to add or update"
            },
            "payload": {
              "type": "object",
              "required": ["verification_status", "provenance", "confidence"],
              "properties": {
                "kind": {
                  "type": "string",
                  "enum": [
                    "source",
                    "thesis",
                    "forecast_clause",
                    "constraint",
                    "metric",
                    "kill_condition",
                    "observable",
                    "price_channel",
                    "buyer_segment",
                    "action",
                    "winner",
                    "loser"
                  ]
                },
                "label": { "type": "string" },
                "fields": { "$ref": "#/$defs/nodeFields" },
                "verification_status": { "$ref": "#/$defs/verificationDecision" },
                "provenance": { "$ref": "#/$defs/provenance" },
                "confidence": { "$ref": "#/$defs/confidence" }
              }
            }
          }
        }
      ]
    },
    "edgeOperation": {
      "allOf": [
        { "$ref": "#/$defs/baseOperation" },
        {
          "type": "object",
          "required": ["edge_id", "payload"],
          "properties": {
            "edge_id": {
              "type": "string",
              "description": "ID of the edge to add or update"
            },
            "payload": {
              "type": "object",
              "required": ["verification_status", "provenance", "confidence", "src", "dst", "rel"],
              "properties": {
                "src": { "type": "string" },
                "dst": { "type": "string" },
                "rel": { "type": "string" },
                "rationale": { "type": "string" },
                "verification_status": { "$ref": "#/$defs/verificationDecision" },
                "provenance": { "$ref": "#/$defs/provenance" },
                "confidence": { "$ref": "#/$defs/confidence" }
              }
            }
          }
        }
      ]
    },
    "taskResolution": {
      "allOf": [
        { "$ref": "#/$defs/baseOperation" },
        {
          "type": "object",
          "required": ["task_id", "new_status"],
          "properties": {
            "task_id": {
              "type": "string",
              "description": "ID from the unknown_queue or watchlist to mark as resolved"
            },
            "new_status": {
              "type": "string",
              "enum": ["done", "invalid", "duplicate"]
            },
            "resolution_note": {
              "type": "string",
              "description": "Quick note on why it is considered resolved"
            }
          }
        }
      ]
    }
  },
  "additionalProperties": false
}
```

---

### Usage Guidance

- **Patch files** must be placed under `/patches/role_outputs/` and named `<role>_<thesis>_<date>.patch.json`.
- The integrator validates each patch against this schema before merging.
- An `add` or `update` that supplies `verification_status: "verified_from_source"` can promote a node to the `source-verified` set (closing the `verification_source_verified_nodes` gap).
- Forecast clauses may receive additional `observable` edges but **never** altered probabilities.
- Any patch attempting to set `confidence` < 0.5 or missing mandatory provenance is rejected with a note.
- Substitutes, scenario branches, and entity resolutions are delivered as new nodes (kind `substitute`, `scenario`, `canonical_entity`) that link to the original thesis via edges; they do not replace existing nodes until a subsequent human review.

This schema ensures that all merged information stays falsifiable, source‑disciplined, and free of fabricated details.

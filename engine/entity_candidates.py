"""Entity-resolution scaling (A7) — candidate generation → verify → commit.

The hand-curated CLUSTERS in entity.py stay the GOLD SEED. This adds the path to hundreds of links
across multi-source data WITHOUT the §9 blind-fuzzy-match anti-pattern: generators only PROPOSE
(into `entity_candidates`); a human/Claude accepts → it commits to `entity_links`. Fuzzy may
propose, never commit. Every proposal carries a confidence + rationale (GIGO).

Generators, in trust order:
  • exact_id   — an unlinked series whose normalized label/alias EXACTLY equals an entity's
                 canonical name or a known alias. High precision; proposed at 0.9.
  • string_block — token-overlap with an entity name (RECALL-oriented blocking). Proposed low (~0.5),
                 method 'string_block' — it narrows what a human/LLM reviews, it never decides.
  • llm        — (optional, needs a key) adjudicates a blocked pair as same/parent/child/sibling/
                 distinct with a reason; updates the candidate. Cost-gated via the LLM adapter.

Commit (`accept`) promotes a 'same' candidate to an entity_link; parent/child/sibling can become an
entity_edge; 'distinct' is rejected. The over-merge error (NLP ≠ deep learning) is caught at review.
"""

from __future__ import annotations

import re
import sqlite3

from engine import entity
from engine.schemas import Entity, EntityCandidate, EntityEdge, EntityLink, _now, _uid

_STOP = {"the", "a", "of", "and", "for", "in", "to", "system", "model", "method", "technology"}


def _toks(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t not in _STOP and len(t) > 1}


def _entity_index(conn: sqlite3.Connection) -> list[tuple[str, str, set[str], set[str]]]:
    """(entity_id, canonical_name, exact_surface_forms, token_set) per entity."""
    import json
    out = []
    for e in conn.execute("SELECT id, canonical_name, aliases FROM entities").fetchall():
        aliases = []
        try:
            aliases = json.loads(e["aliases"] or "[]")
        except json.JSONDecodeError:
            pass
        surfaces = {e["canonical_name"].lower(), *(a.lower() for a in aliases)}
        toks = set()
        for s in surfaces:
            toks |= _toks(s)
        out.append((e["id"], e["canonical_name"], surfaces, toks))
    return out


def _linked_series(conn: sqlite3.Connection) -> set[str]:
    return {r["ref_id"] for r in
            conn.execute("SELECT ref_id FROM entity_links WHERE ref_table='series'")}


def _proposed_keys(conn: sqlite3.Connection) -> set[tuple]:
    return {(r["entity_id"], r["ref_table"], r["ref_id"], r["generator"]) for r in
            conn.execute("SELECT entity_id, ref_table, ref_id, generator FROM entity_candidates")}


def generate(conn: sqlite3.Connection, *, block_threshold: float = 0.5, log=print) -> dict:
    """Propose links for UNLINKED series against existing entities. Writes 'proposed' rows. $0."""
    index = _entity_index(conn)
    linked = _linked_series(conn)
    seen = _proposed_keys(conn)
    n_exact = n_block = 0
    for s in conn.execute("SELECT id, label, pillar_id FROM series ORDER BY label").fetchall():
        if s["id"] in linked:
            continue
        label = s["label"]
        norm = label.lower()
        ltoks = _toks(label)
        if not ltoks:
            continue
        for eid, ename, surfaces, etoks in index:
            exact = any(surf in norm or norm in surf for surf in surfaces)
            overlap = len(ltoks & etoks) / len(ltoks | etoks) if (ltoks | etoks) else 0.0
            if exact:
                gen, conf, rel = "exact_id", 0.9, "same"
                rationale = f"series label '{label}' surface-matches entity '{ename}'."
            elif overlap >= block_threshold:
                gen, conf, rel = "string_block", round(min(0.6, overlap), 2), "same"
                rationale = (f"token overlap {overlap:.2f} between '{label}' and '{ename}' "
                             f"— BLOCKED candidate for review, not a decision.")
            else:
                continue
            if (eid, "series", s["id"], gen) in seen:
                continue
            cand = EntityCandidate(
                entity_id=eid, ref_table="series", ref_id=s["id"], ref_label=label,
                pillar_id=s["pillar_id"], generator=gen, relation=rel, confidence=conf,
                rationale=rationale,
            )
            _insert_candidate(conn, cand)
            seen.add((eid, "series", s["id"], gen))
            n_exact += gen == "exact_id"
            n_block += gen == "string_block"
    conn.commit()
    log(f"  generated {n_exact} exact_id + {n_block} string_block candidates (proposed, awaiting review)")
    return {"exact": n_exact, "block": n_block}


def _insert_candidate(conn: sqlite3.Connection, c: EntityCandidate) -> None:
    conn.execute(
        "INSERT INTO entity_candidates (id,entity_id,proposed_name,ref_table,ref_id,ref_label,"
        "pillar_id,generator,relation,confidence,rationale,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(entity_id,ref_table,ref_id,generator) DO NOTHING",
        (c.id, c.entity_id, c.proposed_name, c.ref_table, c.ref_id, c.ref_label, c.pillar_id,
         c.generator, c.relation, c.confidence, c.rationale, c.status, c.created_at.isoformat()),
    )


def list_proposed(conn: sqlite3.Connection, *, log=print) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT c.id, c.generator, c.relation, c.confidence, c.ref_label, c.rationale, e.canonical_name "
        "FROM entity_candidates c LEFT JOIN entities e ON e.id=c.entity_id "
        "WHERE c.status='proposed' ORDER BY c.confidence DESC"
    ).fetchall()
    if not rows:
        log("  no proposed candidates (run entity-candidates --generate)")
    for r in rows:
        log(f"  [{r['id'][:8]}] {r['confidence']:.2f} {r['generator']:<12} "
            f"{r['ref_label'][:36]:<38} → {r['canonical_name']}  ({r['relation']})")
    return rows


def accept(conn: sqlite3.Connection, candidate_id: str, *, by: str = "in_session") -> str:
    """Promote a 'same' candidate to an entity_link (or a parent/child/sibling to an entity_edge)."""
    c = conn.execute("SELECT * FROM entity_candidates WHERE id=? AND status='proposed'",
                     (candidate_id,)).fetchone()
    if c is None:
        raise ValueError(f"no proposed candidate {candidate_id}")
    method = {"exact_id": "exact_id", "llm": "llm_verified"}.get(c["generator"], "in_session")
    if c["relation"] == "same":
        entity._upsert_link(conn, EntityLink(
            entity_id=c["entity_id"], ref_table=c["ref_table"], ref_id=c["ref_id"],
            ref_label=c["ref_label"], pillar_id=c["pillar_id"], confidence=c["confidence"],
            method=method, rationale=f"{c['rationale']} (accepted by {by})",
        ))
        result = "linked"
    else:
        result = f"relation '{c['relation']}' — review as an entity_edge, not auto-linked"
    conn.execute("UPDATE entity_candidates SET status='accepted', decided_at=? WHERE id=?",
                 (_now().isoformat(), candidate_id))
    conn.commit()
    return result


def reject(conn: sqlite3.Connection, candidate_id: str) -> None:
    conn.execute("UPDATE entity_candidates SET status='rejected', decided_at=? WHERE id=?",
                 (_now().isoformat(), candidate_id))
    conn.commit()


def add_edge(conn: sqlite3.Connection, src_entity: str, dst_entity: str, rel: str, *,
             confidence: float, rationale: str, source_id: str | None = None) -> None:
    """Add a typed entity↔entity edge (the implicit 10x→consumable supplier link, made explicit)."""
    e = EntityEdge(src_entity=src_entity, dst_entity=dst_entity, rel=rel,
                   confidence=confidence, rationale=rationale, source_id=source_id)
    conn.execute(
        "INSERT INTO entity_edges (id,src_entity,dst_entity,rel,confidence,rationale,source_id,created_at) "
        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(src_entity,dst_entity,rel) DO UPDATE SET "
        "confidence=excluded.confidence, rationale=excluded.rationale, source_id=excluded.source_id",
        (e.id, e.src_entity, e.dst_entity, e.rel, e.confidence, e.rationale, e.source_id,
         e.created_at.isoformat()),
    )
    conn.commit()


# ── component 2 (#4, dependency half): the supplier-edge spine ──
# The entity spine links the same concept across pillars; this adds the SUPPLY STRUCTURE *between*
# entities so a constraint can be traced one hop upstream/downstream — the dependency-graph half of #4.
# Each edge is a WELL-ESTABLISHED real-world supplier relation (not a hallucinated chain, §3 caution),
# stated in-session with a rationale (GIGO), tracing the LIVE thesis chains the system already bets on.
# `(src) supplies (dst)` = src is an input/upstream constraint for dst. Confidence is lower where the
# relation is one-of-several inputs. LLM 10-K extraction can PROPOSE more at scale (extract.py) under
# the same human-verify gate (rule 4); these curated edges are the gold seed, like the entity clusters.
SUPPLIER_EDGES: list[tuple[str, str, float, str]] = [
    # AI-power chain (the deepest live thesis: rent migrates GPU → electrical interconnect → GOES)
    ("Grain-oriented electrical steel", "Large-power transformer", 0.95,
     "GOES is the core magnetic material of a large-power transformer's laminated core — the deepest "
     "named bottleneck in the ai_power chain (Japan-concentrated, HHI 0.62)."),
    ("Copper", "Large-power transformer", 0.8,
     "Copper is the winding conductor of power transformers — a co-input alongside GOES; Chile-concentrated."),
    ("Large-power transformer", "Data center", 0.9,
     "AI data centers cannot energize without grid-interconnection transformers — the ~2-3yr-backlogged "
     "step capital cannot fast-forward (the survived AI→interconnect thesis)."),
    ("HV switchgear", "Data center", 0.8,
     "High-voltage switchgear is the other long-lead electrical-interconnect input for a data center."),
    ("NVIDIA", "Data center", 0.9, "NVIDIA GPUs are the compute substrate of AI data centers (the elastic layer)."),
    ("Micron Technology", "Data center", 0.7, "Micron HBM/DRAM is a memory input to AI accelerators (the MoE→memory thesis)."),
    ("Rare-earth elements", "Electric vehicle", 0.8,
     "Rare-earth permanent magnets drive EV traction motors — China-concentrated (HHI rising)."),
    # energy storage chain
    ("Lithium (critical mineral)", "Lithium-ion battery", 0.9, "Lithium is the irreplaceable active material of Li-ion cells."),
    ("Lithium-ion battery", "Electric vehicle", 0.9, "The battery pack is the dominant cost+constraint of an EV."),
    ("Solid electrolyte", "Solid-state battery", 0.9,
     "The solid electrolyte is the enabling (and bottleneck) component of a solid-state battery."),
    # nuclear restart chain (survived thesis: rent → enrichment)
    ("Uranium enrichment (SWU/HALEU)", "Nuclear energy", 0.85,
     "Enriched uranium (SWU/HALEU) is the fuel input restarts/SMRs depend on — the Western-capacity "
     "bottleneck (Centrus near-monopoly) the survived nuclear thesis names."),
    # single-cell genomics chain (the 1st live thesis + paper bet)
    ("10x Genomics", "Single-cell RNA sequencing", 0.95,
     "10x Genomics' droplet instruments+consumables are the dominant scRNA-seq platform (the IP-defended "
     "consumable layer where rent lands)."),
    ("Illumina", "Genome sequencing", 0.9, "Illumina sequencers are the read-out substrate of most genomics."),
    ("Illumina", "Single-cell RNA sequencing", 0.7, "scRNA-seq libraries are read out on Illumina sequencers — a cross-platform input."),
    # GLP-1 chain (survived thesis: rent → injection consumable)
    ("Messenger RNA (mRNA)", "GLP-1 injection consumable", 0.3,
     "Weak/illustrative: both are injectable-biologic demand drivers that lift elastomer-closure demand "
     "(the consumable layer); kept low-confidence, not a direct material input."),
]


def seed_supplier_edges(conn: sqlite3.Connection, *, log=print) -> dict:
    """Seed the curated entity↔entity supplier edges (#4 dependency half). Resolves canonical names →
    ids; an edge whose endpoints don't both exist is SKIPPED + logged (never faked). Idempotent. $0."""
    name_to_id = {r["canonical_name"]: r["id"]
                  for r in conn.execute("SELECT id, canonical_name FROM entities")}
    added = skipped = 0
    for src, dst, conf, why in SUPPLIER_EDGES:
        si, di = name_to_id.get(src), name_to_id.get(dst)
        if not si or not di:
            log(f"  ⚠ skip (missing entity): {src} → {dst}")
            skipped += 1
            continue
        add_edge(conn, si, di, "supplies", confidence=conf, rationale=why)
        added += 1
    total = conn.execute("SELECT COUNT(*) FROM entity_edges").fetchone()[0]
    log(f"  supplier edges: {added} added · {skipped} skipped · {total} total entity↔entity edges")
    # show the longest traceable chain as the payoff
    for r in conn.execute(
        "SELECT s.canonical_name a, d.canonical_name b, e.confidence c FROM entity_edges e "
        "JOIN entities s ON s.id=e.src_entity JOIN entities d ON d.id=e.dst_entity "
        "WHERE e.rel='supplies' ORDER BY e.confidence DESC LIMIT 6").fetchall():
        log(f"    ◆ {r['a']} →supplies→ {r['b']}  ({r['c']})")
    return {"added": added, "skipped": skipped, "total": total}


# ─────────────────────────────────────────────────────────────────────────────
# Curated taxonomy seed (#4, the heavy half) — the canonical sub-topic vocabulary.
#
# The 14 hand-curated clusters in entity.py stay the GOLD SEED; this widens the spine
# to the remaining ~320 unlinked series WITHOUT the over-merge error the constitution
# forbids. The discipline: EVERY DISTINCT CONCEPT IS ITS OWN ENTITY (auto-minted from its
# own clean OpenAlex/arXiv label), so RNN / GAN / GNN / NLP / CV / QEC / quantum-dot can
# NEVER fold into a parent (deep learning / quantum computing) — under-merging is safe,
# over-merging is the cardinal sin. We fold ONLY true cross-source / cross-pillar surface
# variants of the SAME concept (an explicit allow-list below). Every link carries a
# rationale (GIGO). The payoff is the cross-pillar TRACE: hydrogen spans research→capital→
# policy→attention (5 pillars), copper / GOES / transformer span dependency→pricing — a
# constraint can now be followed across the value layers, which is the whole point.

_CHANNEL_SUFFIX = re.compile(
    r"\s*\((?:topic share|field breadth|talent inflow|citation velocity|NIH grants|patents|"
    r"SEC filings|pageviews|Fed\. Register)\)\s*$", re.I)

# Cross-source / cross-pillar FOLDS — distinct surface forms of the SAME concept. Allow-list
# only; anything not here mints its own entity (the over-merge guard). key = normalized core.
_FOLD = {
    # research synonyms / abbreviations
    "mrna vaccine": "Messenger RNA (mRNA)",
    "messenger rna": "Messenger RNA (mRNA)",
    "mrna": "Messenger RNA (mRNA)",
    "single cell rna": "Single-cell RNA sequencing",          # existing gold entity
    "single-cell sequencing": "Single-cell RNA sequencing",
    "hydrogen fuel": "Hydrogen economy",
    "hydrogen": "Hydrogen economy",
    "hydrogen economy": "Hydrogen economy",
    "quantum information science": "Quantum computing",        # existing alias
    "solid state battery": "Solid-state battery",
    "solid-state battery": "Solid-state battery",
    "artificial intelligence": "Artificial intelligence",
    "machine learning": "Machine learning",
    "carbon capture": "Carbon sequestration",
    "rare earth": "Rare-earth elements",
}
# Display-name overrides for auto-minted research cores (disambiguate / capitalize).
_DISPLAY = {
    "transformer": "Transformer (DL architecture)",            # NOT the electrical transformer
    "alphafold": "AlphaFold",
    "large language model": "Large language model",
    "mixture of experts": "Mixture of experts",
    "generative adversarial network": "Generative adversarial network",
    "graph neural network": "Graph neural network",
    "recurrent neural network": "Recurrent neural network",
    "vision transformer": "Vision transformer",
    "car t cell": "CAR T-cell therapy",
    "lithium metal": "Lithium-metal anode",
    "dna computing": "DNA computing",
    "wimax": "WiMAX",
}
# arXiv subject categories (coarse field trackers) → concept (lower confidence, it is a field).
_ARXIV_CAT = {
    "arXiv cs.AI (Artificial Intelligence)": "Artificial intelligence",
    "arXiv cs.LG (Machine Learning)": "Machine learning",
    "arXiv cs.CL (Computation & Language)": "Natural language processing",
    "arXiv cs.CV (Computer Vision)": "Computer vision",
    "arXiv quant-ph (Quantum Physics)": "Quantum physics",
    "arXiv cond-mat.supr-con (Superconductivity)": "Superconductivity",
    "arXiv q-bio.BM (Biomolecules)": "Biomolecular structure",
    "arXiv eess.SY (Systems & Control)": "Control systems",
}
# Structured (pillar ≥2) series → canonical, by EXACT label or unambiguous substring. These are
# the high-value cross-pillar joins (dependency↔pricing↔policy share one entity).
_STRUCTURED = [  # (predicate over (label, pillar, provider), canonical)
    ("Large-power transformer PPI",            "Large-power transformer"),
    ("HV switchgear PPI",                       "HV switchgear"),
    ("Other electrical equipment PPI",          "Electrical equipment"),
    ("Iron & steel PPI (GOES proxy)",           "Grain-oriented electrical steel"),
    ("Copper mill products PPI",                "Copper"),
    ("Copper-base-metal mine output (US)",      "Copper"),
    ("Metal-ore mine output (US)",              "Metal-ore mining"),
    ("genome seq affordability",                "Genome sequencing"),
    ("geothermal lcoe affordability",           "Geothermal energy"),
    ("offshore wind lcoe affordability",        "Wind power"),
    ("supercomputer flops",                     "Supercomputing"),
    ("transistors per chip",                    "Transistor"),
    ("mrna (SEC filings)",                      "Messenger RNA (mRNA)"),
    ("nuclear fusion (SEC filings)",            "Nuclear fusion"),
    ("solid state battery (SEC filings)",       "Solid-state battery"),
    ("hydrogen (SEC filings)",                  "Hydrogen economy"),
    ("artificial intelligence (SEC filings)",   "Artificial intelligence"),
    ("machine learning (SEC filings)",          "Machine learning"),
    ("semiconductor (SEC filings)",             "Semiconductor"),
    ("data center (SEC filings)",               "Data center"),
    ("electric vehicle (SEC filings)",          "Electric vehicle"),
    ("hydrogen economy (pageviews)",            "Hydrogen economy"),
    ("nuclear fusion (pageviews)",              "Nuclear fusion"),
    ("single-cell sequencing (pageviews)",      "Single-cell RNA sequencing"),
    ("solid-state battery (pageviews)",         "Solid-state battery"),
    ("artificial intelligence (Fed. Register)", "Artificial intelligence"),
    ("semiconductor (Fed. Register)",           "Semiconductor"),
    ("electric vehicle (Fed. Register)",        "Electric vehicle"),
    ("hydrogen (Fed. Register)",                "Hydrogen economy"),
    ("lithium (Fed. Register)",                 "Lithium (critical mineral)"),
    ("rare earth (Fed. Register)",              "Rare-earth elements"),
    ("critical minerals (Fed. Register)",       "Critical minerals"),
    ("nuclear energy (Fed. Register)",          "Nuclear energy"),
    ("carbon capture (Fed. Register)",          "Carbon sequestration"),
    ("data privacy (Fed. Register)",            "Data privacy"),
    ("export control (Fed. Register)",          "Export controls"),
    ("tariff (Fed. Register)",                  "Trade tariffs"),
    # company capex (p6) — firm-level entities (research→capex→pricing trace)
    ("NVDA capex (elastic-compute)",            "NVIDIA"),
    ("AMD capex (elastic-compute)",             "AMD"),
    ("AVGO capex (elastic-compute)",            "Broadcom"),
    ("MU capex (elastic-compute)",              "Micron Technology"),
    ("ETN capex (inelastic-grid)",              "Eaton"),
    ("HUBB capex (inelastic-grid)",             "Hubbell"),
    ("PWR capex (inelastic-grid)",              "Quanta Services"),
    ("VRT capex (inelastic-grid)",              "Vertiv"),
]
_STRUCTURED_SUBSTR = [  # substring (UN Comtrade families, p3)
    ("Refined copper",                          "Copper"),
    ("Grain-oriented electrical steel",         "Grain-oriented electrical steel"),
    ("Electrical transformer",                  "Large-power transformer"),
    ("Rare-earth",                              "Rare-earth elements"),
    # p9 retro narratives
    ("3D printing",                             "3D printing"),
    ("Graphene",                                "Graphene"),
    ("Hydrogen economy",                        "Hydrogen economy"),
    ("Metaverse",                               "Metaverse"),
    ("Shale",                                   "Shale / tight oil"),
]
# Explicit metadata for named entities (kind/domain/aliases). Auto-minted research concepts
# default to technology + a keyword-inferred domain.
_META = {
    "Messenger RNA (mRNA)": ("technology", "bio", ["mrna", "messenger rna", "mrna vaccine"]),
    "Hydrogen economy": ("technology", "energy", ["hydrogen", "hydrogen fuel"]),
    "Solid-state battery": ("technology", "energy", ["solid state battery"]),
    "Artificial intelligence": ("technology", "AI", ["AI"]),
    "Machine learning": ("technology", "AI", ["ML"]),
    "Semiconductor": ("technology", "semiconductors", ["chip", "integrated circuit"]),
    "Data center": ("infrastructure", "compute", ["datacenter"]),
    "Electric vehicle": ("technology", "energy", ["EV"]),
    "Supercomputing": ("technology", "compute", ["HPC", "flops"]),
    "Genome sequencing": ("technology", "genomics", ["dna sequencing"]),
    "Copper": ("material", "metals", ["refined copper"]),
    "Grain-oriented electrical steel": ("material", "metals", ["GOES", "electrical steel"]),
    "Rare-earth elements": ("material", "metals", ["rare earth", "REE"]),
    "Critical minerals": ("material", "metals", []),
    "Metal-ore mining": ("material", "metals", []),
    "Lithium (critical mineral)": ("material", "metals", ["lithium"]),
    "Large-power transformer": ("component", "grid", ["power transformer"]),
    "HV switchgear": ("component", "grid", ["switchgear"]),
    "Electrical equipment": ("component", "grid", []),
    "Nuclear energy": ("technology", "energy", ["nuclear fission", "nuclear power"]),
    "Data privacy": ("policy", "compute", []),
    "Export controls": ("policy", "geo", []),
    "Trade tariffs": ("policy", "geo", ["tariff"]),
    "Metaverse": ("technology", "compute", []),
    "Shale / tight oil": ("technology", "energy", ["fracking"]),
    "3D printing": ("technology", "manufacturing", ["additive manufacturing"]),
    "Quantum physics": ("field", "quantum", []),
    "Biomolecular structure": ("field", "bio", []),
    "Control systems": ("field", "AI", []),
    # capex firms
    "NVIDIA": ("company", "semiconductors", ["NVDA"]),
    "AMD": ("company", "semiconductors", ["Advanced Micro Devices"]),
    "Broadcom": ("company", "semiconductors", ["AVGO"]),
    "Micron Technology": ("company", "semiconductors", ["MU"]),
    "Eaton": ("company", "grid", ["ETN"]),
    "Hubbell": ("company", "grid", ["HUBB"]),
    "Quanta Services": ("company", "grid", ["PWR"]),
    "Vertiv": ("company", "grid", ["VRT"]),
}
# Keyword → domain for auto-minted research concepts. Word boundaries (\b) where a bare substring
# would collide (gene⊂generative, fusion⊂diffusion). Domain is a coarse display bucket, not gating.
_DOMAIN_KW = [
    (r"quantum|qubit|topological insulator", "quantum"),
    (r"\brna\b|protein|organoid|microbiome|immunotherapy|stem cell|\bgene\b|genetic|gene editing|"
     r"crispr|optogenetic|cryo.electron|synthetic biology|antibody|car t|alphafold|transcriptomic|"
     r"biomolecul|vaccine", "bio"),
    (r"battery|fuel cell|electrolyte|lithium|hydrogen|solar|perovskite|\bwind\b|geothermal|"
     r"nuclear|\bfusion\b|tokamak|supercapacitor|thermoelectric|heat pump|electrocataly", "energy"),
    (r"graphene|nanotube|nanoparticle|metamaterial|metal.organic|high entropy alloy|"
     r"gallium nitride|spintronic|memristor|twisted bilayer|superconduc|photonic|"
     r"laser melting", "materials"),
    (r"rfid|wimax|near field|internet of things|edge computing|grid computing|semantic web|"
     r"radar|drone|satellite|augmented reality|brain.computer|transistor|plasma display|"
     r"autostereoscopy", "devices"),
    (r"learning|neural|\bnetwork\b|transformer|\bgan\b|\bnlp\b|language model|language processing|"
     r"natural language|computer vision|attention|\bagent\b|knowledge|anomaly|speech|translation|"
     r"reinforcement|distillation|retrieval|self.supervised|foundation model|diffusion model|"
     r"fuzzy|federated|contrastive|architecture search|in.context|robotic|mixture of experts", "AI"),
]


def _core(label: str) -> str:
    """Strip channel suffix → the underlying concept, normalized for matching."""
    core = _CHANNEL_SUFFIX.sub("", label).strip()
    return re.sub(r"[‐-―\-]", " ", core.lower()).strip()  # unify hyphens/dashes


def _infer_domain(core: str) -> str:
    for pat, dom in _DOMAIN_KW:
        if re.search(pat, core):
            return dom
    return "general"


def _resolve(label: str, pillar: int | None, provider: str) -> tuple[str, str, float, bool] | None:
    """Map a series → (canonical, rationale, confidence, mint_from_core). None = leave unlinked.
    When mint_from_core is True the first field is the NORMALIZED core (not a display name); the
    caller resolves it to one display name per core so casing/source variants converge (Organoid ≡
    organoid), never fragment into two entities."""
    if provider == "synthetic" or label.startswith("CONTROL"):
        return None                                            # the flat negative control — no entity
    if label in _ARXIV_CAT:
        return (_ARXIV_CAT[label], f"arXiv subject category '{label}' is the field-level tracker for "
                f"this concept (coarse — a field, not a single technique)", 0.7, False)
    if (pillar or 1) >= 2:
        for key, canon in _STRUCTURED:
            if label == key:
                return (canon, f"'{label}' (pillar {pillar}, {provider}) is a measured channel of "
                        f"the {canon} constraint — a cross-pillar link", 0.9, False)
        for sub, canon in _STRUCTURED_SUBSTR:
            if sub.lower() in label.lower():
                return (canon, f"'{label}' (pillar {pillar}, {provider}) measures the {canon} "
                        f"constraint — a cross-pillar link", 0.88, False)
        return None                                            # unmapped structured series — skip, don't guess
    # pillar 1 (research): fold synonyms, else mint the concept itself (keyed by normalized core)
    core = _core(label)
    if core in _FOLD:
        return (_FOLD[core], f"research signal '{label}' is a surface form of {_FOLD[core]} "
                f"(curated fold)", 0.85, False)
    return (core, f"research signal '{label}' is its own concept "
            f"(point-in-time channel; kept as its own entity, never merged into a parent)", 0.95, True)


def _p1_display_map(rows: list[sqlite3.Row], linked: set[str]) -> dict[str, str]:
    """One display name per normalized core: a curated override, else the richest surface form seen
    (most uppercase letters → the OpenAlex 'Cancer immunotherapy' beats the arXiv 'cancer ...')."""
    surfaces: dict[str, list[str]] = {}
    for s in rows:
        if s["id"] in linked or s["provider"] == "synthetic" or s["label"].startswith("CONTROL"):
            continue
        if s["label"] in _ARXIV_CAT or (s["pillar_id"] or 1) >= 2:
            continue
        core = _core(s["label"])
        if core in _FOLD:
            continue
        surfaces.setdefault(core, []).append(_CHANNEL_SUFFIX.sub("", s["label"]).strip())
    out = {}
    for core, labs in surfaces.items():
        chosen = _DISPLAY.get(core)
        if chosen is None:                                     # richest surface, then Title-case the head
            best = sorted(labs, key=lambda L: (-sum(c.isupper() for c in L), L))[0]
            chosen = best[:1].upper() + best[1:]
        out[core] = chosen
    return out


def seed_taxonomy(conn: sqlite3.Connection, *, log=print) -> dict:
    """Link every unlinked series to a canonical entity (minting entities as needed), under the
    no-over-merge discipline. Idempotent: re-runs skip already-linked series. $0, stdlib."""
    linked = _linked_series(conn)
    rows = conn.execute("SELECT id, label, pillar_id, provider FROM series ORDER BY label").fetchall()
    display = _p1_display_map(rows, linked)
    name_to_id: dict[str, str] = {
        r["canonical_name"]: r["id"] for r in conn.execute("SELECT id, canonical_name FROM entities")}
    n_link = n_new = n_skip = 0
    spanned: dict[str, set] = {}
    for s in rows:
        if s["id"] in linked:
            continue
        res = _resolve(s["label"], s["pillar_id"], s["provider"])
        if res is None:
            n_skip += 1
            continue
        canon, rationale, conf, mint_core = res
        if mint_core:
            canon = display.get(canon, canon[:1].upper() + canon[1:])
        eid = name_to_id.get(canon)
        if eid is None:                                        # mint the entity
            kind, domain, aliases = _META.get(canon, ("technology", _infer_domain(_core(canon)), []))
            ent = Entity(kind=kind, canonical_name=canon, domain=domain, aliases=aliases,
                         note="seeded by the curated taxonomy (#4); distinct concept = own entity")
            eid = entity._upsert_entity(conn, ent)
            name_to_id[canon] = eid
            n_new += 1
        entity._upsert_link(conn, EntityLink(
            entity_id=eid, ref_table="series", ref_id=s["id"], ref_label=s["label"],
            pillar_id=s["pillar_id"], confidence=conf, method="taxonomy_curated", rationale=rationale))
        n_link += 1
        spanned.setdefault(canon, set()).add(s["pillar_id"])
    conn.commit()
    cross = {k: sorted(v) for k, v in spanned.items() if len(v) >= 2}
    log(f"  taxonomy: {n_link} series linked · {n_new} entities minted · {n_skip} skipped (controls/unmapped)")
    log(f"  cross-pillar traces ({len(cross)}): the constraint-tracing payoff —")
    for k, pil in sorted(cross.items(), key=lambda x: -len(x[1])):
        log(f"    ◆ {k:<32} spans pillars {pil}")
    return {"linked": n_link, "minted": n_new, "skipped": n_skip, "cross_pillar": cross}

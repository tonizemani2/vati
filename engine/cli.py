"""The CLI — the single seam the cockpit shells out to.

init-db / seed / status (foundation) + collect-frontier / detect (Phase 1). Keep this small:
each command is a thin wrapper; the work lives in engine.pillars.* and engine.detector.
"""

from __future__ import annotations

import typer

from datetime import date
from pathlib import Path

from engine import backtest, bet, companies_house_enrich, consensus, cost, coverage_grade, data_offload, db, decisions, detector, discover, disk_guard, entity, experiment, forecast, gleif_enrich, graph, holdout, hypothesis, indicators, ladder, locator, market, quality, raw_provenance, rawstore, research_papers, retro, saturation, sec_company_enrich, seed, signals, significance, universe, wikidata_enrich, world_catalog, world_graph, world_graph_deepseek, world_seed, world_state
from engine.schemas import ForecastOutcome
from engine.pillars import dependency, frontier, metals, power, research

app = typer.Typer(add_completion=False, help="Foresight engine CLI.")


@app.command("init-db")
def init_db() -> None:
    """Create the SQLite tables (idempotent)."""
    conn = db.connect()
    db.init_db(conn)
    tables = db.table_names(conn)
    conn.close()
    typer.echo(f"DB ready at {db.DB_PATH}")
    typer.echo(f"tables: {', '.join(tables)}")


@app.command("seed")
def seed_cmd() -> None:
    """Seed the 9 pillars (idempotent — never overwrites status)."""
    conn = db.connect()
    db.init_db(conn)  # safe if init-db wasn't run yet
    added = seed.seed_pillars(conn)
    total = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
    conn.close()
    typer.echo(f"seeded {added} new pillar(s); {total} total.")


@app.command("signals")
def signals_cmd(
    topic: str = typer.Argument(..., help="free-text topic or question to ground"),
    as_json: bool = typer.Option(False, "--json", help="emit the raw pack as JSON"),
) -> None:
    """Topic → structural evidence pack from the data layer (grounds a forecast). $0."""
    import json as _json

    from engine.signals import evidence_pack, format_pack
    pack = evidence_pack(topic)
    typer.echo(_json.dumps(pack, ensure_ascii=False) if as_json else format_pack(pack))


@app.command("world-state")
def world_state_cmd(
    topic: str = typer.Argument(..., help="free-text topic or question to freeze"),
    as_of: str = typer.Option(..., "--as-of", help="point-in-time cutoff, YYYY-MM-DD"),
    record: bool = typer.Option(True, "--record/--no-record", help="record a snapshot row; --no-record is read-only"),
    as_json: bool = typer.Option(False, "--json", help="emit the raw pack as JSON"),
) -> None:
    """Topic -> timestamped world-state pack with a deterministic snapshot hash. $0."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    pack = world_state.state_pack(topic, date.fromisoformat(as_of[:10]), conn=conn, record=record)
    conn.close()
    typer.echo(_json.dumps(pack, ensure_ascii=False, sort_keys=True) if as_json else world_state.format_pack(pack))


@app.command("world-graph-compile")
def world_graph_compile_cmd(
    board_path: str = typer.Argument(..., help="Pope board JSON to compile into the Vati World Graph"),
    out_dir: str | None = typer.Option(None, "--out-dir", help="directory for graph pack outputs"),
    as_json: bool = typer.Option(False, "--json", help="emit the raw atlas JSON"),
) -> None:
    """Compile a Pope board into a deterministic World Graph atlas pack. $0/local-only."""
    import json as _json

    path = Path(board_path)
    try:
        board = world_graph.load_board(path)
    except (OSError, _json.JSONDecodeError) as exc:
        typer.echo(f"ERROR: could not read board JSON: {exc}", err=True)
        raise typer.Exit(2) from None
    atlas = world_graph.build_atlas(board, path)
    if out_dir:
        files = world_graph.write_outputs(atlas, Path(out_dir))
        if as_json:
            typer.echo(_json.dumps({"atlas": atlas, "files": files}, ensure_ascii=False, sort_keys=True))
            return
        typer.echo(
            "world graph compiled: "
            f"nodes={atlas['summary']['node_count']} edges={atlas['summary']['edge_count']} "
            f"forecasts={atlas['summary']['forecast_count']} unknowns={atlas['summary']['unknown_count']} "
            f"coverage={atlas['coverage']['score']}/100"
        )
        typer.echo(f"out_dir: {out_dir}")
        typer.echo(f"markdown: {files['markdown']}")
        typer.echo(f"json: {files['json']}")
        return
    typer.echo(_json.dumps(atlas, ensure_ascii=False, sort_keys=True) if as_json else world_graph.render_markdown(atlas))


@app.command("world-graph-deepseek")
def world_graph_deepseek_cmd(
    board_path: str = typer.Argument(..., help="Pope board JSON to run through the DeepSeek V4 World Graph plan"),
    out_dir: str = typer.Option(..., "--out-dir", help="directory for DeepSeek run pack outputs"),
    plan: str = typer.Option("standard", "--plan", help="lite, standard, or full"),
    execute: bool = typer.Option(False, "--execute/--dry-run", help="actually call DeepSeek API; dry-run only writes prompts and estimates"),
    model_flash: str = typer.Option(world_graph_deepseek.MODEL_FLASH, "--model-flash", help="fast/cheap DeepSeek model id"),
    model_pro: str = typer.Option(world_graph_deepseek.MODEL_PRO, "--model-pro", help="reasoning DeepSeek model id"),
    allow_unstable_mac: bool = typer.Option(False, "--allow-unstable-mac", help="bypass recent Codex/Dock crash-loop guard"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable run pack/result"),
) -> None:
    """Create or execute a DeepSeek V4 E2E World Graph improvement run."""
    import json as _json

    try:
        if execute:
            result = world_graph_deepseek.execute_run(
                board_path,
                out_dir=out_dir,
                plan=plan,
                model_flash=model_flash,
                model_pro=model_pro,
                allow_unstable_mac=allow_unstable_mac,
            )
        else:
            result = world_graph_deepseek.build_run_pack(
                board_path,
                out_dir=out_dir,
                plan=plan,
                model_flash=model_flash,
                model_pro=model_pro,
            )
    except (OSError, ValueError, _json.JSONDecodeError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    except (cost.CostGateError, world_graph_deepseek.llm.LLMConfigError, RuntimeError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    if as_json:
        typer.echo(_json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    est = result["estimate"]
    typer.echo(
        "deepseek world graph "
        f"{result['run_mode']}: plan={result['plan']} calls={result['call_count']} "
        f"est=${est['total_cost_usd_cache_miss']:.4f} cache-miss"
    )
    typer.echo(f"out_dir: {out_dir}")
    typer.echo(f"manifest: {Path(out_dir) / 'RUN_MANIFEST.md'}")
    if not execute:
        typer.echo("dry-run only; add --execute after setting DEEPSEEK_API_KEY and cost approval.")


@app.command("world-state-audit")
def world_state_audit_cmd(
    as_json: bool = typer.Option(False, "--json", help="emit the raw audit as JSON"),
) -> None:
    """Non-mutating audit of DB counts, raw coverage, health gaps, snapshots, and cost burn."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    out = world_state.audit(conn)
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else world_state.format_audit(out))


@app.command("world-state-proof")
def world_state_proof_cmd(
    topic: str = typer.Argument(..., help="free-text topic or question to prove"),
    as_of: str = typer.Option(..., "--as-of", help="point-in-time cutoff, YYYY-MM-DD"),
    limit: int = typer.Option(12, "--limit", help="maximum facts to include in the proof"),
    as_json: bool = typer.Option(False, "--json", help="emit the raw proof as JSON"),
) -> None:
    """Read-only proof that returned facts existed before the forecast timestamp. $0."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    out = world_state.state_proof(topic, date.fromisoformat(as_of[:10]), conn=conn, limit=limit)
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else world_state.format_proof(out))


@app.command("world-research-pack")
def world_research_pack_cmd(
    topic: str = typer.Argument(..., help="free-text research topic or question"),
    as_of: str = typer.Option(..., "--as-of", help="point-in-time cutoff, YYYY-MM-DD"),
    paper_limit: int = typer.Option(world_state.DEFAULT_RESEARCH_PAPER_LIMIT, "--paper-limit", help="maximum papers to return"),
    fact_limit: int = typer.Option(world_state.DEFAULT_RESEARCH_FACT_LIMIT, "--fact-limit", help="maximum research facts to return"),
    count_fact_exclusions: bool = typer.Option(False, "--count-fact-exclusions", help="count matching future facts; slower on large local DBs"),
    count_paper_exclusions: bool = typer.Option(False, "--count-paper-exclusions", help="count matching future papers; slower on large local corpora"),
    search_abstracts: bool = typer.Option(False, "--search-abstracts", help="search paper abstracts too; slower on large local corpora"),
    fill_token_fallback: bool = typer.Option(False, "--fill-token-fallback", help="fill paper slots with broader token matches after exact phrase matches"),
    full_paper_scan: bool = typer.Option(False, "--full-paper-scan", help="scan full paper corpus for text matches; slow but higher recall"),
    paper_scan_rows: int = typer.Option(world_state.DEFAULT_RESEARCH_PAPER_SCAN_ROWS, "--paper-scan-rows", help="bounded newest-paper rows to score before cutoff"),
    as_json: bool = typer.Option(False, "--json", help="emit the raw research pack as JSON"),
) -> None:
    """Topic -> point-in-time research context from local papers and research facts. $0/read-only."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    out = world_state.research_pack(
        topic,
        date.fromisoformat(as_of[:10]),
        conn=conn,
        paper_limit=paper_limit,
        fact_limit=fact_limit,
        count_fact_exclusions=count_fact_exclusions,
        count_paper_exclusions=count_paper_exclusions,
        search_abstracts=search_abstracts,
        fill_token_fallback=fill_token_fallback,
        full_paper_scan=full_paper_scan,
        paper_scan_rows=paper_scan_rows,
    )
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else world_state.format_research_pack(out))


@app.command("world-state-backfill-observations")
def world_state_backfill_observations_cmd(
    replace: bool = typer.Option(False, "--replace", help="rebuild derived observation facts"),
    limit: int | None = typer.Option(None, "--limit", help="optional row cap for test runs"),
    provider: str | None = typer.Option(None, "--provider", help="optional series provider filter, e.g. nsf_awards"),
    min_free_gb: float = typer.Option(disk_guard.DEFAULT_MIN_FREE_GB, "--min-free-gb", help="refuse below this free local disk threshold"),
    max_used_pct: float = typer.Option(disk_guard.DEFAULT_MAX_USED_PCT, "--max-used-pct", help="refuse above this local disk usage percentage"),
    allow_low_disk: bool = typer.Option(False, "--allow-low-disk", help="explicitly override disk guardrails"),
) -> None:
    """Backfill timestamped world-state facts from existing measured series observations. $0."""
    try:
        stats = disk_guard.assert_safe(
            db.REPO_ROOT,
            min_free_gb=min_free_gb,
            max_used_pct=max_used_pct,
            label="world-state observation fact backfill",
            allow_low_disk=allow_low_disk,
        )
    except disk_guard.DiskSpaceError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    typer.echo(
        f"disk ok for world-state backfill: free {stats['free_gb']:.1f}GiB, "
        f"used {stats['used_pct']:.1f}% (floor {min_free_gb:.1f}GiB, cap {max_used_pct:.1f}%)"
    )
    conn = db.connect()
    db.init_db(conn)
    out = world_state.backfill_observation_facts(conn, replace=replace, limit=limit, provider=provider)
    conn.close()
    typer.echo(
        "world-state observation facts: "
        f"seen {out['seen']}, written {out['written']}, "
        f"before {out['before']}, after {out['after']}. cost: $0.00"
    )


@app.command("world-state-backfill-metric-entities")
def world_state_backfill_metric_entities_cmd(
    replace: bool = typer.Option(False, "--replace", help="rebuild derived metric-to-entity bridge facts"),
    metric: str | None = typer.Option(None, "--metric", help="optional metric filter, e.g. interconnection_queue_capacity"),
    min_free_gb: float = typer.Option(disk_guard.DEFAULT_MIN_FREE_GB, "--min-free-gb", help="refuse below this free local disk threshold"),
    max_used_pct: float = typer.Option(disk_guard.DEFAULT_MAX_USED_PCT, "--max-used-pct", help="refuse above this local disk usage percentage"),
    allow_low_disk: bool = typer.Option(False, "--allow-low-disk", help="explicitly override disk guardrails"),
) -> None:
    """Backfill timestamped world-state facts from known metric→top-entity bridges. $0."""
    try:
        stats = disk_guard.assert_safe(
            db.REPO_ROOT,
            min_free_gb=min_free_gb,
            max_used_pct=max_used_pct,
            label="world-state metric entity bridge backfill",
            allow_low_disk=allow_low_disk,
        )
    except disk_guard.DiskSpaceError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    typer.echo(
        f"disk ok for world-state metric entity bridge backfill: free {stats['free_gb']:.1f}GiB, "
        f"used {stats['used_pct']:.1f}% (floor {min_free_gb:.1f}GiB, cap {max_used_pct:.1f}%)"
    )
    conn = db.connect()
    db.init_db(conn)
    out = world_state.backfill_metric_entity_facts(conn, replace=replace, metric=metric)
    conn.close()
    typer.echo(
        "world-state metric entity bridge facts: "
        f"seen {out['seen']}, written {out['written']}, "
        f"before {out['before']}, after {out['after']}. cost: $0.00"
    )


@app.command("world-state-backfill-identifiers")
def world_state_backfill_identifiers_cmd(
    replace: bool = typer.Option(False, "--replace", help="rebuild derived official identifier facts"),
    limit: int | None = typer.Option(None, "--limit", help="optional row cap for test runs"),
    min_free_gb: float = typer.Option(disk_guard.DEFAULT_MIN_FREE_GB, "--min-free-gb", help="refuse below this free local disk threshold"),
    max_used_pct: float = typer.Option(disk_guard.DEFAULT_MAX_USED_PCT, "--max-used-pct", help="refuse above this local disk usage percentage"),
    allow_low_disk: bool = typer.Option(False, "--allow-low-disk", help="explicitly override disk guardrails"),
) -> None:
    """Backfill timestamped world-state facts from official entity identifiers. $0."""
    try:
        stats = disk_guard.assert_safe(
            db.REPO_ROOT,
            min_free_gb=min_free_gb,
            max_used_pct=max_used_pct,
            label="world-state identifier fact backfill",
            allow_low_disk=allow_low_disk,
        )
    except disk_guard.DiskSpaceError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    typer.echo(
        f"disk ok for world-state identifier backfill: free {stats['free_gb']:.1f}GiB, "
        f"used {stats['used_pct']:.1f}% (floor {min_free_gb:.1f}GiB, cap {max_used_pct:.1f}%)"
    )
    conn = db.connect()
    db.init_db(conn)
    out = world_state.backfill_entity_identifier_facts(conn, replace=replace, limit=limit)
    conn.close()
    typer.echo(
        "world-state identifier facts: "
        f"seen {out['seen']}, written {out['written']}, identifiers {out['identifier_entities']}, "
        f"before {out['before']}, after {out['after']}. cost: $0.00"
    )


@app.command("world-entity-autolink")
def world_entity_autolink_cmd(
    all_series: bool = typer.Option(False, "--all-series", help="also scan series that already have links"),
    limit: int | None = typer.Option(None, "--limit", help="optional row cap for test runs"),
) -> None:
    """Auto-link obvious series/entity matches using exact aliases, ISO codes, and tickers. $0."""
    conn = db.connect()
    db.init_db(conn)
    out = world_state.autolink_series_entities(conn, only_unlinked=not all_series, limit=limit)
    conn.close()
    typer.echo(
        "world entity autolink: "
        f"seen {out['series_seen']}, matched {out['matched']}, links_written {out['links_written']}, "
        f"geo_entities_created {out['geo_entities_created']}, "
        f"remaining_unlinked_series {out['remaining_unlinked_series']}. cost: $0.00"
    )


@app.command("world-raw-recover")
def world_raw_recover_cmd(
    limit: int = typer.Option(50, "--limit", help="maximum missing hashed sources to inspect"),
    max_bytes_mb: float = typer.Option(5.0, "--max-bytes-mb", help="maximum response size per URL"),
    timeout: float = typer.Option(raw_provenance.DEFAULT_TIMEOUT, "--timeout", help="fetch timeout in seconds"),
    execute: bool = typer.Option(False, "--execute", help="store exact hash matches; default only reports"),
    allow_prefix: list[str] | None = typer.Option(
        None,
        "--allow-prefix",
        help="allowed URL prefix; repeat to override the built-in conservative allowlist",
    ),
    url_prefix: list[str] | None = typer.Option(
        None,
        "--url-prefix",
        help="candidate source URL prefix; repeat to target small/recoverable subsets",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable recovery stats"),
    min_free_gb: float = typer.Option(disk_guard.DEFAULT_MIN_FREE_GB, "--min-free-gb", help="execute-mode local free disk floor"),
    max_used_pct: float = typer.Option(disk_guard.DEFAULT_MAX_USED_PCT, "--max-used-pct", help="execute-mode local disk usage cap"),
    allow_low_disk: bool = typer.Option(False, "--allow-low-disk", help="explicitly override execute-mode disk guardrails"),
) -> None:
    """Recover missing raw_docs rows only when refetched bytes match an existing source hash."""
    import json as _json

    if execute:
        try:
            stats = disk_guard.assert_safe(
                db.REPO_ROOT,
                min_free_gb=min_free_gb,
                max_used_pct=max_used_pct,
                label="raw provenance recovery",
                allow_low_disk=allow_low_disk,
            )
        except disk_guard.DiskSpaceError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(2) from None
        if not as_json:
            typer.echo(
                f"disk ok for raw recovery: free {stats['free_gb']:.1f}GiB, "
                f"used {stats['used_pct']:.1f}%"
            )

    conn = db.connect()
    db.init_db(conn)
    out = raw_provenance.recover_missing_raw_docs(
        conn,
        limit=limit,
        max_bytes=max(1, int(max_bytes_mb * 1024 * 1024)),
        timeout=timeout,
        execute=execute,
        allow_prefixes=tuple(allow_prefix) if allow_prefix else raw_provenance.DEFAULT_ALLOW_PREFIXES,
        url_prefixes=tuple(url_prefix) if url_prefix else None,
    )
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else raw_provenance.format_recovery(out))


@app.command("world-raw-mark-legacy")
def world_raw_mark_legacy_cmd(
    overwrite: bool = typer.Option(False, "--overwrite", help="recompute existing provenance status fields"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable marking stats"),
) -> None:
    """Mark source rows as exact raw-doc provenance or explicit legacy/no-raw provenance."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    out = raw_provenance.mark_legacy_provenance(conn, overwrite=overwrite)
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else raw_provenance.format_legacy_mark(out))


@app.command("world-raw-locate")
def world_raw_locate_cmd(
    content_hash: str = typer.Argument(..., help="sha256 content hash from sources/raw_docs/world_state_facts"),
    manifest_path: str | None = typer.Option(None, "--manifest", help="offload manifest path; defaults to data/_offload_manifest.jsonl"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable location info"),
) -> None:
    """Locate exact raw bytes locally or in the S3 offload manifest. $0 unless S3 is inspected externally."""
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    out = rawstore.locate(conn, content_hash, manifest_path=Path(manifest_path) if manifest_path else None)
    conn.close()
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
        return
    typer.echo(
        "raw doc location: "
        f"hash={out['content_hash']} status={out['status']} "
        f"indexed={out['indexed']} local={out['exists_local']}"
    )
    if out.get("local_path"):
        typer.echo(f"local_path: {out['local_path']}")
    if out.get("remote_uri"):
        typer.echo(f"remote_uri: {out['remote_uri']}")
    if out.get("byte_len"):
        typer.echo(f"bytes: {out['byte_len']}")


@app.command("world-raw-restore")
def world_raw_restore_cmd(
    content_hash: str = typer.Argument(..., help="sha256 content hash to restore from offloaded raw byte storage"),
    max_bytes_mb: float = typer.Option(100.0, "--max-bytes-mb", help="refuse to restore a document larger than this"),
    manifest_path: str | None = typer.Option(None, "--manifest", help="offload manifest path; defaults to data/_offload_manifest.jsonl"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable restore info"),
    min_free_gb: float = typer.Option(disk_guard.DEFAULT_MIN_FREE_GB, "--min-free-gb", help="local free disk floor"),
    max_used_pct: float = typer.Option(disk_guard.DEFAULT_MAX_USED_PCT, "--max-used-pct", help="local disk usage cap"),
    allow_low_disk: bool = typer.Option(False, "--allow-low-disk", help="explicitly override disk guardrails"),
) -> None:
    """Restore one exact raw document from S3 by hash, with hash verification and a byte cap."""
    import json as _json

    try:
        stats = disk_guard.assert_safe(
            db.REPO_ROOT,
            min_free_gb=min_free_gb,
            max_used_pct=max_used_pct,
            label="single raw-doc restore",
            allow_low_disk=allow_low_disk,
        )
    except disk_guard.DiskSpaceError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None

    conn = db.connect()
    db.init_db(conn)
    try:
        out = rawstore.restore(
            conn,
            content_hash,
            max_bytes=max(1, int(max_bytes_mb * 1024 * 1024)),
            manifest_path=Path(manifest_path) if manifest_path else None,
        )
    except (FileNotFoundError, RuntimeError, ValueError, data_offload.DataOffloadError) as exc:
        conn.close()
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    conn.close()
    if as_json:
        typer.echo(_json.dumps({"disk": stats, **out}, ensure_ascii=False, sort_keys=True))
        return
    typer.echo(
        f"raw doc restore: hash={out['content_hash']} restored={out.get('restored')} "
        f"status={out['status']} bytes={out.get('byte_len', 0)}"
    )
    typer.echo(f"local_path: {out.get('local_path')}")
    if out.get("restored_from"):
        typer.echo(f"restored_from: {out['restored_from']}")


@app.command("world-data-plan")
def world_data_plan_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show sources with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by status"),
    entities: bool = typer.Option(False, "--entities", help="include top global entity seed list"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable registry"),
) -> None:
    """Show the global source coverage plan: sources, processing, outputs, cost posture."""
    import json as _json

    rows = world_catalog.registry(priority=priority, status=status)
    if as_json:
        payload = {"summary": world_catalog.global_view(), "sources": rows}
        if entities:
            payload["top_entities"] = world_catalog.top_entities()
        typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(world_catalog.format_plan(rows, include_entities=entities))


@app.command("world-land-permits-plan")
def world_land_permits_plan_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show jurisdictions with priority <= N"),
    region: str | None = typer.Option(None, "--region", help="filter by region/name substring"),
    limit: int | None = typer.Option(20, "--limit", help="limit human-readable jurisdiction rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV source inventory"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable source inventory"),
) -> None:
    """Read-only worldwide land-permit/concession source inventory; no collection or spend."""
    import json as _json

    out = world_catalog.land_permit_inventory(priority=priority, region=region)
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.land_permit_inventory_csv(out), nl=False)
    else:
        typer.echo(world_catalog.format_land_permit_inventory(out, limit=limit))


@app.command("world-land-source-seed")
def world_land_source_seed_cmd(
    register: bool = typer.Option(False, "--register", help="also register source targets in SQLite"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable seed result"),
) -> None:
    """Seed a tiny official/open land-permit source-target manifest; no bulk scrape or spend."""
    import json as _json

    from engine.feeds import land_permit_sources

    manifest = land_permit_sources.write_manifest()
    payload = {"manifest": manifest, "registered": None}
    if register:
        conn = db.connect()
        db.init_db(conn)
        payload["registered"] = land_permit_sources.seed_sources(conn)
        conn.close()
    if as_json:
        typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    typer.echo(
        f"land permit source seed: rows={manifest['rows']} path={manifest['path']} "
        "cost=$0.00 bulk_fetch=no paid_processing=no"
    )
    if payload["registered"]:
        reg = payload["registered"]
        typer.echo(
            f"registered source targets: rows={reg['rows']} inserted={reg['inserted']} "
            f"updated={reg['updated']} manifest_hash={reg['manifest_hash']}"
        )


@app.command("world-constraint-plan")
def world_constraint_plan_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show constraint targets with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by target status"),
    limit: int | None = typer.Option(20, "--limit", help="limit human-readable target rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV constraint inventory"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable constraint inventory"),
) -> None:
    """Read-only physical-constraint data plan: permits, papers, patents, grid, water, materials, logistics."""
    import json as _json

    out = world_catalog.physical_constraint_inventory(priority=priority, status=status)
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.physical_constraint_inventory_csv(out), nl=False)
    else:
        typer.echo(world_catalog.format_physical_constraint_inventory(out, limit=limit))


@app.command("world-research-plan")
def world_research_plan_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show targets with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by target status"),
    limit: int | None = typer.Option(20, "--limit", help="limit human-readable target rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV research expansion inventory"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable research expansion inventory"),
) -> None:
    """Read-only research expansion plan; no corpus collection or spend."""
    import json as _json

    out = world_catalog.research_expansion_inventory(priority=priority, status=status)
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.research_expansion_inventory_csv(out), nl=False)
    else:
        typer.echo(world_catalog.format_research_expansion_inventory(out, limit=limit))


@app.command("world-data-status")
def world_data_status_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show sources with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by registry status"),
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable operational status"),
) -> None:
    """Read-only status: collected files, DB rows, world-state facts, blockers, disk safety."""
    import json as _json

    conn = db.connect()
    out = world_catalog.data_status(
        conn,
        priority=priority,
        status=status,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else world_catalog.format_status(out))


@app.command("world-data-actions")
def world_data_actions_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show sources with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by registry status"),
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable next actions"),
) -> None:
    """Read-only next-action view: safe local refreshes, paid approvals, blockers."""
    import json as _json

    conn = db.connect()
    out = world_catalog.data_status(
        conn,
        priority=priority,
        status=status,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    payload = {
        "summary": out["summary"],
        "db": out["db"],
        "disk": out["disk"],
        "cost_ledger": out["cost_ledger"],
        "scan_logs": out.get("scan_logs", {}),
        "entity_identifiers": out.get("entity_identifiers", {}),
        "series_health": out.get("series_health", {}),
        "action_plan": out["action_plan"],
        "blockers": out["blockers"],
    }
    typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True) if as_json else world_catalog.format_actions(out))


@app.command("world-roi-sprint")
def world_roi_sprint_cmd(
    priority: int | None = typer.Option(None, "--priority", help="build status from sources with priority <= N"),
    top: int | None = typer.Option(12, "--top", help="limit ROI queue rows"),
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable ROI sprint queue"),
) -> None:
    """Read-only ROI-ranked sprint queue for constraint data acquisition; no collection or spend."""
    import json as _json

    conn = db.connect()
    out = world_catalog.data_status(
        conn,
        priority=priority,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    payload = world_catalog.constraint_roi_queue(out, limit=top)
    typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True) if as_json else world_catalog.format_constraint_roi_queue(payload, limit=top))


@app.command("world-data-matrix")
def world_data_matrix_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show sources with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by registry status"),
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    limit: int | None = typer.Option(None, "--limit", help="limit human-readable rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV source matrix"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable source matrix"),
) -> None:
    """Read-only source matrix: coverage, processing, outputs, cost posture, state, and next action."""
    import json as _json

    conn = db.connect()
    out = world_catalog.data_status(
        conn,
        priority=priority,
        status=status,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    matrix = world_catalog.source_matrix(out)
    if as_json:
        typer.echo(_json.dumps(matrix, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.source_matrix_csv(matrix), nl=False)
    else:
        typer.echo(world_catalog.format_source_matrix(matrix, limit=limit))


@app.command("world-research-status")
def world_research_status_cmd(
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    limit: int | None = typer.Option(20, "--limit", help="limit human-readable source rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV research layer matrix"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable research layer status"),
) -> None:
    """Read-only research-layer status: diversity, time coverage, queryability, blockers, cost policy."""
    import json as _json

    conn = db.connect()
    out = world_catalog.research_layer_status(
        conn,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.research_layer_status_csv(out), nl=False)
    else:
        typer.echo(world_catalog.format_research_layer_status(out, limit=limit))


@app.command("world-research-profile")
def world_research_profile_cmd(
    limit: int = typer.Option(25, "--limit", help="limit top provider/category/predicate rows"),
    full_paper_groups: bool = typer.Option(
        False,
        "--full-paper-groups",
        help="include exact paper year/category histograms; heavier local SQLite scan",
    ),
    full_source_status: bool = typer.Option(
        False,
        "--full-source-status",
        help="include full research source matrix status; heavier local SQLite scan",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable research coverage profile"),
) -> None:
    """Read-only research coverage profile: providers, categories, years, predicates, provenance."""
    import json as _json

    conn = db.connect()
    out = world_catalog.research_coverage_profile(
        conn,
        limit=limit,
        include_paper_groups=full_paper_groups,
        include_source_status=full_source_status,
    )
    conn.close()
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(world_catalog.format_research_coverage_profile(out, limit=limit))


@app.command("world-research-provenance")
def world_research_provenance_cmd(
    limit: int = typer.Option(25, "--limit", help="limit source and predicate gap rows"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable research provenance gaps"),
) -> None:
    """Read-only research raw-doc provenance gaps; no refetch or mutation."""
    import json as _json

    conn = db.connect()
    out = world_catalog.research_provenance_gaps(conn, limit=limit)
    conn.close()
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(world_catalog.format_research_provenance_gaps(out, limit=limit))


@app.command("world-data-approvals")
def world_data_approvals_cmd(
    priority: int | None = typer.Option(None, "--priority", help="show sources with priority <= N"),
    status: str | None = typer.Option(None, "--status", help="filter by registry status"),
    stale_hours: float = typer.Option(world_catalog.DEFAULT_STALE_HOURS, "--stale-hours", help="feed age that should be considered stale"),
    max_local_refresh_mb: float = typer.Option(
        world_catalog.DEFAULT_MAX_LOCAL_REFRESH_MB,
        "--max-local-refresh-mb",
        help="mark larger local feed refreshes as cloud-first/manual",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable approval packet"),
) -> None:
    """Read-only approval packet: paid, keyed, visibility-limited, and cloud-first data blockers."""
    import json as _json

    conn = db.connect()
    out = world_catalog.data_status(
        conn,
        priority=priority,
        status=status,
        stale_hours=stale_hours,
        max_local_refresh_mb=max_local_refresh_mb,
    )
    conn.close()
    payload = world_catalog.approval_plan(out)
    typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True) if as_json else world_catalog.format_approval_plan(out))


@app.command("world-entity-status")
def world_entity_status_cmd(
    kind: str | None = typer.Option(None, "--kind", help="filter top entities by kind"),
    missing_only: bool = typer.Option(False, "--missing-only", help="only show entities without hard identifiers"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable identifier coverage"),
) -> None:
    """Read-only top-entity identifier coverage for the global entity backbone."""
    import json as _json

    conn = db.connect()
    out = world_catalog.entity_identifier_status(conn, kind=kind, missing_only=missing_only)
    conn.close()
    typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True) if as_json else world_catalog.format_entity_identifier_status(out))


@app.command("world-entity-coverage")
def world_entity_coverage_cmd(
    kind: str | None = typer.Option(None, "--kind", help="filter top entities by kind"),
    missing_only: bool = typer.Option(False, "--missing-only", help="only show entities without timestamped facts"),
    limit: int | None = typer.Option(80, "--limit", help="limit human-readable entity rows"),
    as_csv: bool = typer.Option(False, "--csv", help="emit CSV entity coverage"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable entity coverage"),
) -> None:
    """Read-only top-entity world-state coverage: facts, sources, predicates, series, identifiers."""
    import json as _json

    conn = db.connect()
    out = world_catalog.top_entity_coverage(conn, kind=kind, missing_only=missing_only)
    conn.close()
    if as_json:
        typer.echo(_json.dumps(out, ensure_ascii=False, sort_keys=True))
    elif as_csv:
        typer.echo(world_catalog.top_entity_coverage_csv(out), nl=False)
    else:
        typer.echo(world_catalog.format_top_entity_coverage(out, limit=limit))


@app.command("world-entity-seed")
def world_entity_seed_cmd() -> None:
    """Seed the top global countries, companies, technologies, and materials into entities."""
    conn = db.connect()
    db.init_db(conn)
    out = world_catalog.seed_top_entities(conn, log=typer.echo)
    conn.close()
    typer.echo(
        f"\ndone — created {out['created']} top entities, "
        f"merged {out['existing']} existing, registry total {out['total']}."
    )


@app.command("world-entity-enrich-gleif")
def world_entity_enrich_gleif_cmd(
    limit: int = typer.Option(gleif_enrich.DEFAULT_LIMIT, "--limit", help="max company entities to query"),
    only: list[str] | None = typer.Option(None, "--only", help="specific canonical company name(s)"),
) -> None:
    """Enrich top company entities with official GLEIF LEI identifiers. $0/keyless."""
    conn = db.connect()
    db.init_db(conn)
    out = gleif_enrich.enrich_top_entities(conn, limit=limit, only=only, log=typer.echo)
    conn.close()
    typer.echo(
        "GLEIF enrichment: "
        f"seen {out['seen']}, matched {out['matched']}, missed {out['missed']}, "
        f"cleaned {out.get('cleaned', 0)}, raw_responses {out['raw_responses']}, "
        f"source_id {out['source_id']}. cost: $0.00"
    )
    if out["misses"]:
        typer.echo("misses: " + ", ".join(out["misses"][:20]))


@app.command("world-entity-enrich-sec")
def world_entity_enrich_sec_cmd(
    limit: int = typer.Option(sec_company_enrich.DEFAULT_LIMIT, "--limit", help="max company entities to query"),
    only: list[str] | None = typer.Option(None, "--only", help="specific canonical company name(s)"),
) -> None:
    """Enrich top company entities with official SEC ticker and CIK identifiers. $0/keyless."""
    conn = db.connect()
    db.init_db(conn)
    out = sec_company_enrich.enrich_top_entities(conn, limit=limit, only=only, log=typer.echo)
    conn.close()
    typer.echo(
        "SEC company enrichment: "
        f"seen {out['seen']}, matched {out['matched']}, missed {out['missed']}, "
        f"links_written {out['links_written']}, source_id {out['source_id']}. cost: $0.00"
    )
    if out["misses"]:
        typer.echo("misses: " + ", ".join(out["misses"][:20]))


@app.command("world-entity-enrich-companies-house")
def world_entity_enrich_companies_house_cmd(
    limit: int = typer.Option(companies_house_enrich.DEFAULT_LIMIT, "--limit", help="max company entities to query"),
    only: list[str] | None = typer.Option(None, "--only", help="specific canonical company name(s)"),
) -> None:
    """Enrich UK-linked top company entities with official Companies House numbers. $0/keyless."""
    conn = db.connect()
    db.init_db(conn)
    out = companies_house_enrich.enrich_top_entities(conn, limit=limit, only=only, log=typer.echo)
    conn.close()
    typer.echo(
        "Companies House enrichment: "
        f"seen {out['seen']}, matched {out['matched']}, missed {out['missed']}, "
        f"links_written {out['links_written']}, source_id {out['source_id']}. cost: $0.00"
    )
    if out["misses"]:
        typer.echo("misses: " + ", ".join(out["misses"][:20]))


@app.command("world-entity-enrich-wikidata")
def world_entity_enrich_wikidata_cmd(
    kind: str = typer.Option("company", "--kind", help="top-entity kind to query"),
    limit: int = typer.Option(wikidata_enrich.DEFAULT_LIMIT, "--limit", help="max entities to query"),
    only: list[str] | None = typer.Option(None, "--only", help="specific canonical entity name(s)"),
    missing_only: bool = typer.Option(
        True,
        "--missing-only/--all-top-entities",
        help="default to top entities still lacking hard identifiers",
    ),
) -> None:
    """Enrich top entities with exact-match Wikidata QID identifiers. $0/keyless."""
    conn = db.connect()
    db.init_db(conn)
    out = wikidata_enrich.enrich_top_entities(
        conn,
        kind=kind,
        limit=limit,
        only=only,
        missing_only=missing_only,
        log=typer.echo,
    )
    conn.close()
    typer.echo(
        "Wikidata enrichment: "
        f"seen {out['seen']}, matched {out['matched']}, missed {out['missed']}, "
        f"links_written {out['links_written']}, raw_responses {out['raw_responses']}, "
        f"sources {len(out['source_ids'])}. cost: $0.00"
    )
    if out["misses"]:
        typer.echo("misses: " + ", ".join(out["misses"][:20]))


@app.command("data-offload")
def data_offload_cmd(
    root: str = typer.Option(str(db.REPO_ROOT / "data"), "--root", help="file or directory to inventory/offload"),
    min_size_mb: float = typer.Option(100.0, "--min-size-mb", help="only consider files at least this large"),
    dest: str | None = typer.Option(None, "--dest", help="S3 prefix, e.g. s3://bucket/prefix"),
    execute: bool = typer.Option(False, "--execute", help="actually upload; default is inventory/dry-run only"),
    delete_local: bool = typer.Option(False, "--delete-local", help="delete local files after upload and remote size verification"),
    allow_critical_delete: bool = typer.Option(
        False,
        "--allow-critical-delete",
        help="allow deletion of critical .db/.sqlite/.parquet files after verified upload",
    ),
    manifest: str = typer.Option(
        str(db.REPO_ROOT / "data" / "_offload_manifest.jsonl"),
        "--manifest",
        help="JSONL manifest written after real uploads",
    ),
    manifest_status: bool = typer.Option(False, "--manifest-status", help="show recorded offloads and exit"),
    restore_plan: bool = typer.Option(False, "--restore-plan", help="show aws s3 cp commands from uploaded manifest entries"),
    as_json: bool = typer.Option(False, "--json", help="emit machine-readable inventory/offload/manifest details"),
) -> None:
    """Inventory large local data files and optionally offload them to S3. Dry-run by default."""
    import json as _json

    base = db.REPO_ROOT
    manifest_path = Path(manifest).expanduser()
    root_path = Path(root).expanduser()
    if not root_path.is_absolute():
        root_path = base / root_path
    try:
        if manifest_status or restore_plan:
            manifest_entries = data_offload.read_manifest(manifest_path)
            if as_json:
                payload = {
                    "manifest": str(manifest_path),
                    "summary": data_offload.manifest_summary(manifest_entries),
                    "restore_commands": data_offload.restore_commands(manifest_entries) if restore_plan else [],
                }
                typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return
            typer.echo(data_offload.format_manifest(manifest_entries))
            if restore_plan:
                typer.echo(data_offload.format_restore_plan(manifest_entries))
            return
        entries = data_offload.iter_large_files(root_path, min_size_mb=min_size_mb)
        if as_json and not dest:
            payload = {
                "root": str(root_path),
                "base": str(base),
                "mode": "inventory",
                "summary": data_offload.inventory_summary(entries, base=base),
                "uploaded": False,
                "deleted_local": False,
            }
            typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return
        if not as_json:
            typer.echo(data_offload.format_inventory(entries, base=base))
        if not dest:
            typer.echo("No --dest supplied; inventory only. No files uploaded or deleted.")
            return
        results = data_offload.offload(
            entries,
            base=base,
            dest_prefix=dest,
            execute=execute,
            delete_local=delete_local,
            allow_critical_delete=allow_critical_delete,
            manifest_path=manifest_path,
        )
    except data_offload.DataOffloadError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from None
    if as_json:
        payload = {
            "root": str(root_path),
            "base": str(base),
            "mode": "execute" if execute else "dry_run",
            "dest": dest,
            "inventory": data_offload.inventory_summary(entries, base=base),
            "delete_local_requested": delete_local,
            "results": [result.as_dict() for result in results],
            "uploaded": bool(execute),
            "deleted_local": any(result.deleted_local for result in results),
            "dry_run_delete_local_ignored": bool(delete_local and not execute),
        }
        typer.echo(_json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    typer.echo(data_offload.format_offload_plan(results, execute=execute, delete_local=delete_local))
    if not execute:
        typer.echo("Dry run only. Add --execute to upload; add --delete-local only after you want local bytes removed.")


@app.command("research-papers-operation")
def research_papers_operation_cmd(
    remote_prefix: str | None = typer.Option(
        None,
        "--remote-prefix",
        help="Object-store prefix for the lake, e.g. s3://bucket/research-papers",
    ),
    budget_usd: float = typer.Option(
        0.0,
        "--budget-usd",
        help="Named budget for metered/requester-pays stages. Required with --execute.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Mark bulk execution ready after validation. This command still downloads no bulk bytes.",
    ),
    allow_metered: bool = typer.Option(
        False,
        "--allow-metered",
        help="Allow metered/requester-pays sources to pass validation with --execute.",
    ),
    allow_low_disk: bool = typer.Option(
        False,
        "--allow-low-disk",
        help="Bypass local disk guard for manifest bootstrap only.",
    ),
    as_json: bool = typer.Option(False, "--json", help="emit the operation manifest as JSON"),
) -> None:
    """Research papers lake control plane: manifest, sources, budgets, disk gate.

    Safe by default: writes data/research_papers/operation_manifest.json and downloads no
    bulk bytes. Full-text arXiv/PMC/etc. stages must run remotely from the manifest.
    """
    import json as _json

    conn = db.connect()
    db.init_db(conn)
    payload = research_papers.bootstrap(
        remote_prefix=remote_prefix,
        budget_usd=budget_usd,
        execute=execute,
        allow_metered=allow_metered,
        allow_low_disk=allow_low_disk,
        conn=conn,
    )
    conn.close()
    typer.echo(
        _json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if as_json else research_papers.format_summary(payload)
    )


@app.command("collect-frontier")
def collect_frontier() -> None:
    """Pillar 1: collect OpenAlex concept velocity + arXiv presence (free/keyless, $0)."""
    conn = db.connect()
    db.init_db(conn)
    # exhausting Pillar 1 → mark it in progress (strict-layering visibility, rule 2)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    result = frontier.collect(conn, log=typer.echo)
    conn.close()
    typer.echo(
        f"done — openalex: {result['openalex_series']} series / {result['openalex_obs']} obs; "
        f"patents: {result['patent_series']}; grants: {result['grant_series']}; "
        f"benchmarks: {result['benchmark_series']}; arxiv: {result['arxiv_series']} series. "
        f"cost: $0.00"
    )


@app.command("collect-pillars")
def collect_pillars() -> None:
    """Pillars 2/5/6/8: capability curves (OWID) · demand (Wikipedia) · capital (SEC EDGAR) ·
    policy (Federal Register). All keyless. Runs collect → data-audit → detect so the QC gate
    vets every row. Local imports keep this independent of the contended top-level import block.
    """
    from engine.pillars import capability, demand, capital, policy
    conn = db.connect()
    db.init_db(conn)
    for pid, name, mod in [(2, "capability", capability), (5, "demand", demand),
                           (6, "capital", capital), (8, "policy", policy)]:
        conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'", (pid,))
        conn.commit()
        typer.echo(f"\n— Pillar {pid}: {name} —")
        out = mod.collect(conn, log=typer.echo)
        typer.echo(f"  {name}: {out}")
    quality.run_audit(conn, log=typer.echo)
    detector.run_detector(conn, log=typer.echo)
    conn.close()


@app.command("collect-forces")
def collect_forces() -> None:
    """FORCES axis ($0, keyless): two channels of the politics/geo force.
    • geopolitics/news — GDELT event-velocity (ATTENTION/LAG; graceful when GDELT throttles).
    • decreed-scarcity — OFAC/BIS Federal-Register rule deltas, typed per cornered input, polarity-
      netted (the LEADING channel: a decree is the scarcity-creating act, ahead of the price).
    Runs collect → data-audit → detect so the QC gate vets every row."""
    from engine.pillars import forces
    conn = db.connect()
    db.init_db(conn)
    typer.echo("— Forces: geopolitics/news (GDELT, LAG) —")
    out = forces.collect(conn, log=typer.echo)
    typer.echo(f"  geo: {out}")
    typer.echo("— Forces: US decreed-scarcity (OFAC/BIS, LEADING) —")
    dec = forces.collect_decreed(conn, log=typer.echo)
    typer.echo(f"  decreed: {dec}")
    typer.echo("— Forces: China decrees (MOFCOM export-control network, LEADING) —")
    cd = forces.collect_china_decrees(conn, log=typer.echo)
    typer.echo(f"  china_decrees: {cd}")
    typer.echo("— Forces: China decree-footprint (Comtrade, CONFIRMATION/LAG) —")
    cn = forces.collect_china_footprint(conn, log=typer.echo)
    typer.echo(f"  china_footprint: {cn}")
    if out.get("series") or dec.get("series") or cd.get("series") or cn.get("series"):
        quality.run_audit(conn, log=typer.echo)
        detector.run_detector(conn, log=typer.echo)
    conn.close()


@app.command("collect-diffusion")
def collect_diffusion() -> None:
    """Pillar 1: the ORTHOGONAL early channel — cross-field diffusion per OpenAlex concept ($0, keyless).

    For every existing works series, build a point-in-time inverse-Simpson effective-field-count
    series (breadth of adoption, not volume) — a technique crossing field A→B fires here before its
    aggregate count saturates. Consumed by universe-run as a second detector channel (OR-recall).
    """
    conn = db.connect()
    db.init_db(conn)
    n = frontier.collect_diffusion(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} diffusion series. cost: $0.00")


@app.command("collect-research")
def collect_research(
    sets: list[str] = typer.Option(
        None, "--set", help="OAI set(s) to harvest (default: the seed fields cs/stat/q-bio/cond-mat/eess)."),
    max_pages: int = typer.Option(
        None, help="Cap pages PER SET for a quick slice (each page ~1000 papers). Omit = full gapless harvest."),
    signals_only: bool = typer.Option(
        False, help="Skip the harvest; just (re)compute signals from the existing `papers` table."),
) -> None:
    """Pillar 1 (fine grain): harvest arXiv over time (gapless) -> topic-share/diffusion/talent signals.

    The earliest, finest research grain the coarse-counts blind spot was missing (goal.md #2). Streams
    the official keyless OAI-PMH bulk protocol into the `papers` substrate (resumable; re-run continues),
    then derives three LEADING series per technique the existing detector/FDR/discover funnel consumes
    unchanged. A full seed-field harvest takes a while — safe to interrupt and resume. $0.
    """
    conn = db.connect()
    conn.execute("PRAGMA busy_timeout=300000")   # wait out concurrent writers (other collectors)
    try:
        db.init_db(conn)
    except Exception as e:  # noqa: BLE001 — a concurrent schema migration can race init_db's
        # check-then-ALTER (duplicate-column) or hold a lock; the tables already exist, so proceed.
        typer.echo(f"  · init_db skipped (concurrent migration: {type(e).__name__}: {e}); continuing")
    out = research.collect(conn, sets=list(sets) if sets else None, max_pages=max_pages,
                           signals_only=signals_only, log=typer.echo)
    conn.close()
    typer.echo(
        f"done — harvested {out['harvested']} this run; {out['papers_total']} papers total; "
        f"{out['series']} signal series ({out.get('share', 0)} share / {out.get('breadth', 0)} breadth"
        f" / {out.get('talent', 0)} talent). cost: $0.00"
    )


@app.command("collect-capex")
def collect_capex() -> None:
    """Pillar 6: per-company capex acceleration from SEC XBRL — the capital-flow elasticity tell.

    Actual $ incumbents pour into capacity, per fiscal year, across constraint layers (elastic
    compute vs inelastic grid/power vs bio). Capital flooding a layer = it turns elastic = where the
    bottleneck WON'T be. Keyless primary XBRL (SEC fair-access UA), $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=6 AND status='untapped'")
    conn.commit()
    out = capital.collect_capex(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['series']} capex series / {out['obs']} obs. cost: $0.00")


@app.command("collect-thesis-revenue")
def collect_thesis_revenue() -> None:
    """Pillar 6: annual revenue (SEC XBRL) for the inelastic-layer players that RESOLVE survived theses.

    The rent-capturing public company each constraint-migration hypothesis names (Centrus enrichment,
    West Pharma injection consumables) — revenue = rent landing at that layer, the point-in-time series
    a forward card resolves on. Keyless primary XBRL, $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    out = capital.collect_thesis_revenue(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} revenue series / {out['obs']} obs. cost: $0.00")


@app.command("collect-slow")
def collect_slow() -> None:
    """The SLOW-constraint aperture (execution §7/§10): demographics · aging · water · land.

    The acceleration detector is blind to constraints that bind by slowly crossing a mechanism
    threshold (a workforce peaking, water/arable per capita falling). This collects keyless World Bank
    WDI series and runs the THRESHOLD detector (years-to-bind, not σ). Runs collect → audit. $0.
    """
    from engine.pillars import slow
    conn = db.connect()
    db.init_db(conn)
    out = slow.collect(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} slow-constraint series, {out['binding']} binding now. cost: $0.00")


@app.command("forecast-slow")
def forecast_slow() -> None:
    """Turn the approaching slow constraints into immutable forward ForecastCards (scheduled bindings).

    'Does [metric] cross [threshold] by [year]?' — point-in-time falsifiable, P from the drift-MC over
    the WDI trend (not a story). Run after collect-slow. Immutable (rule 7); idempotent on the question. $0.
    """
    from engine.pillars import slow
    conn = db.connect()
    db.init_db(conn)
    out = slow.forecast_crossings(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['cards']} slow-constraint forecast cards. cost: $0.00")


@app.command("collect-procurement")
def collect_procurement() -> None:
    """Pillar 6: federal procurement obligations per product class (USAspending, keyless).

    The measurable DEMAND that resolves a thesis whose inelastic layer has no public pure-play —
    ammunition + explosives/propellant federal contract $/fiscal-year pulls on the energetics supply
    the re-armament thesis names. Keyless USAspending v2 API, $0. Runs collect → audit → detect.
    """
    from engine.pillars import capital
    conn = db.connect()
    db.init_db(conn)
    out = capital.collect_procurement(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=lambda *_a, **_k: None)
    conn.close()
    typer.echo(f"done — {out['series']} procurement series / {out['obs']} obs. cost: $0.00")


@app.command("collect-patents")
def collect_patents() -> None:
    """Pillar 1: refresh patent filing-velocity series (Google Patents, via resi proxy).

    Standalone entry point (was only reachable via collect-frontier). Google blocks DC+repeat IPs,
    so this prefers the residential proxy (Evomi) with a rotating IP per call. Runs collect →
    data-audit → detect. $0/keyless; resi bandwidth is metered → cost-gated before each batch.
    """
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    n = frontier.collect_patents(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} patent series. cost: $0.00")


@app.command("collect-citations")
def collect_citations() -> None:
    """Pillar 1: citation-velocity channel (Semantic Scholar open graph, via DC proxy).

    Citations RECEIVED per year by each term's seminal corpus. Built as a candidate recall-fix
    (hypothesis: it leads the publication-count curve) but the data DISCONFIRMED that — it LAGS
    (papers must exist before being cited) and plateaus to silent at maturity; its one virtue is
    staying silent on fizzles the count channel false-positives on (a confirmer, not a lead signal).
    See the `citation-velocity-lags` memory / execution.md §3. Self-collected through the proxy
    (rotating IP). Runs collect → data-audit → detect. $0/keyless (DC bandwidth sub-cent).
    """
    conn = db.connect()
    db.init_db(conn)
    conn.execute("UPDATE pillars SET status='in_progress' WHERE id=? AND status='untapped'",
                 (frontier.FRONTIER_PILLAR_ID,))
    conn.commit()
    n = frontier.collect_citation_velocity(conn, log=typer.echo)
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {n} citation-velocity series. cost: $0.00")


@app.command("collect-power")
def collect_power() -> None:
    """Pillar 4: collect the AI-power inelastic-layer price series (FRED transformer/switchgear PPI, $0).

    The 2nd domain's testable, point-in-time supply-elasticity signal — the falsifiable series the
    hypothesis gate demanded for the survived AI-buildout→electrical-interconnect thesis. Keyless.
    """
    conn = db.connect()
    db.init_db(conn)
    out = power.collect(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("collect-metals")
def collect_metals() -> None:
    """Pillar 4 (metals/mining): collect the copper-mine supply-QUANTITY series and close the drill loop.

    The graph's drill-score named copper-mine supply the #1 deep-data target (high pressure × thin
    coverage). This collects the measured mine-output series (keyless FRED G.17), QC-audits it,
    attaches it to the copper-mine node, then re-flows the connected world — so you watch the
    drill-score collapse as the data the graph asked for arrives. $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = metals.collect(conn, log=typer.echo)
    # QC the new series so coverage reflects a MEASURED build series (health), not a parameter.
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    # Attach the measured copper-mine output to the node the drill-score named (closes the loop).
    graph.set_build_series(conn, chain=metals.METALS_CHAIN, node_name=metals.COPPER_MINE_NODE,
                           series_id=out["build_series_id"], log=typer.echo)
    # Re-flow the connected world; show the drill-score now that copper-mine is measured.
    chains = ("ai_power", "metals")
    prop = graph.propagate(conn, chain="ai_power", chains=chains, shock=graph.AI_POWER_SHOCK)
    drills = graph.drill_targets(conn, prop, chain="ai_power", chains=chains)
    typer.echo("\nDrill targets after attaching the measured copper-mine series:")
    for d in drills[:5]:
        typer.echo(f"  {d.drill_score:>5.2f}  {d.name[:44]:<44} [{d.chain}]  cov {d.coverage:>3.0%}  · {d.why}")
    conn.close()
    typer.echo(f"\ndone — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("collect-dependency")
def collect_dependency() -> None:
    """Pillar 3 (dependency graph): collect UN Comtrade import-dependency series — value + supplier HHI.

    Opens the most-starved value layer (dependency graph was at 0 series). For each critical input the
    world graph names (refined copper, GOES steel, transformers, rare earths) it measures US import
    VALUE (magnitude) and partner CONCENTRATION (fragility) from keyless Comtrade, QC-audits them, then
    runs the frozen detector so you see which dependencies are ACCELERATING (rising concentration =
    deepening chokepoint) vs the deliberate elastic contrast (transformers, low HHI, should stay
    silent). $0 keyless.
    """
    conn = db.connect()
    conn.execute("PRAGMA busy_timeout=300000")   # wait out concurrent writers (background harvest)
    db.init_db(conn)
    out = dependency.collect(conn, log=typer.echo)
    # QC the new series so they pass the data-health gate before the detector reads them.
    quality.run_audit(conn, log=lambda *_a, **_k: None)
    # Run the frozen detector — the payoff: rising-concentration chokepoints fire, elastic stays silent.
    typer.echo("\nDetector over the dependency layer (frozen k — rising import-concentration = fires):")
    detector.run_detector(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['series']} series / {out['obs']} obs. cost: $0.00")


@app.command("detect")
def detect_cmd(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold to fire"),
    require_qc: bool = typer.Option(True, help="Skip series flagged 'fail' by data-audit (the QC gate)."),
) -> None:
    """Run the domain-agnostic acceleration detector over all series; write verdicts back."""
    conn = db.connect()
    db.init_db(conn)
    detector.run_detector(conn, k=k, require_qc=require_qc, log=typer.echo)
    conn.close()


@app.command("significance")
def significance_cmd(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (match the detect run)."),
    q: float = typer.Option(significance.DEFAULT_Q, help="Benjamini-Hochberg false-discovery level."),
    m: int = typer.Option(significance.DEFAULT_M, help="Surrogate count (the p floor is 1/(M+1)). Higher = finer, slower."),
) -> None:
    """Component 4b: the look-elsewhere correction over the detector (run AFTER `detect`).

    For every scanned series, build an empirical null (early trend continues + bootstrapped early
    noise), run the FROZEN detector on M surrogates → an honest p-value, then Benjamini-Hochberg
    across the whole scan → which fires survive multiple testing + the expected false-discovery count.
    Replaces the Gaussian-σ fantasy (the "43345σ" tell) with p + a denominator. $0, stdlib only.
    """
    conn = db.connect()
    db.init_db(conn)
    significance.run_significance(conn, k=k, q=q, m=m, log=typer.echo)
    conn.close()
    typer.echo("cost: $0.00")


@app.command("discover")
def discover_cmd(
    rescan: bool = typer.Option(False, help="Re-run the full funnel (audit→detect→significance) first. Slow."),
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (only used with --rescan)."),
    q: float = typer.Option(significance.DEFAULT_Q, help="BH-FDR level (only used with --rescan)."),
    m: int = typer.Option(significance.DEFAULT_M, help="Surrogate count (only used with --rescan)."),
) -> None:
    """Component 17: the OPEN, industry-agnostic discovery scan — find where the future is, gated.

    Surfaces the FDR-surviving signals across ALL feeds, then the PRE-CONSENSUS cross-reference:
    which technologies fire on a LEADING channel (capability/science/supply) while LAGGING channels
    (attention/capital/policy) are still flat = EARLY (real + not yet priced) vs PRICED vs the
    attention-only decoys. Most days EARLY is short or empty — that honest default is the point.
    Read-only by default ($0); --rescan re-runs the gates first. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    discover.run_scan(conn, k=k, q=q, m=m, rescan=rescan, log=typer.echo)
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("discover-instruments")
def discover_instruments(
    entity: str = typer.Argument(..., help="Entity id (8-char ok) or canonical name of a discovered signal."),
    provider: str = typer.Option("deepinfra_keyless", help="LLM provider (free keyless first; 'minimax' if it exhausts)."),
    est_cost_cents: int = typer.Option(0, help="Estimated cost for a keyed provider (cost-gated; 0 for keyless)."),
) -> None:
    """Stage 3 (propose): LLM proposes a tradeable ticker PAIR for a discovered constraint.

    The pair is CIK-verified against the SEC filer list (hallucinations dropped automatically) and
    written propose-only to entity_candidates. Confirm with `entity-accept <id>`, then `discover-price`.
    Free keyless by default; a keyed provider is cost-gated. Never auto-commits a bet.
    """
    conn = db.connect()
    db.init_db(conn)
    discover.propose_instruments(conn, entity, provider=provider, est_cost_cents=est_cost_cents,
                                 log=typer.echo)
    conn.close()


@app.command("discover-price")
def discover_price(
    entity: str = typer.Argument(..., help="Entity id (8-char ok) or canonical name with an accepted ticker pair."),
) -> None:
    """Stage 3 (gate): run the priced-in consensus gate on a discovered entity's accepted ticker pair.

    Reads the human-accepted inelastic/elastic ticker links, builds a ConsensusConfig, and runs the
    deterministic consensus gate on REAL Stooq + SEC data → edge | priced_in | inconclusive. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    score = discover.price_entity(conn, entity, log=typer.echo)
    conn.close()
    if score is None:
        raise typer.Exit(code=1)
    typer.echo("\ncost: $0.00")


@app.command("saturation-scan")
def saturation_scan(
    limit: int = typer.Option(12, help="How many of the top EARLY candidates to measure."),
) -> None:
    """Component 17b: MEASURE how known each EARLY discovery candidate already is (keyless, $0).

    For every EARLY entity it runs a keyless web search over public coverage (trade press / regulatory
    / finance — the channels the indexed lag-set misses) and scores narrative saturation. A 'priced/
    known' verdict HARD-DEMOTES the candidate EARLY→PRICED on the next scan: if it's already in the
    trade press, it is not pre-consensus. The honest fix for 'least-seen' being asserted, not measured.
    """
    conn = db.connect()
    db.init_db(conn)
    out = saturation.score_early_board(conn, limit=limit, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['scored']} scored, {out['demoted']} demoted. cost: $0.00")


@app.command("saturation-topic")
def saturation_topic(
    topic: str = typer.Argument(..., help="A topic/thesis phrase to measure public-coverage saturation for."),
) -> None:
    """Measure narrative saturation for one ad-hoc topic — is this thesis already widely covered?

    Keyless web search ($0) → transparent volume×authority×recency score with the hit URLs cited. Use
    before pitching any thesis as 'pre-consensus': it returns 'priced/known' if the crowd is already here.
    """
    conn = db.connect()
    db.init_db(conn)
    s = saturation.score_topic(conn, topic, log=typer.echo)
    typer.echo(f"\n  → saturation {s.saturation:.2f} ({s.tier}) · {s.verdict}")
    typer.echo(f"  {s.rationale}")
    for u in s.evidence_urls[:6]:
        typer.echo(f"    · {u}")
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("consensus-eye")
def consensus_eye(
    claim: str = typer.Argument(..., help="The structural claim, in plain words (the sector/macro reorganization)."),
    ticker: str = typer.Option(None, help="OPTIONAL US ticker, only to add the price channel (financial-optional)."),
) -> None:
    """Is this structural forecast already priced — at the RIGHT altitude (not just a stock multiple)?

    Multi-channel, physical-primary: (1) NARRATIVE saturation, (2) the CONSENSUS-FORECAST channel — have
    the official forecasters (IEA/IMF/banks) already projected it? — and (3) an OPTIONAL price run-up if a
    ticker is given. A structural call with no instrument is still valid; price is never required. Keyless, $0.
    """
    conn = db.connect()
    db.init_db(conn)
    sat = saturation.score_topic(conn, claim, log=typer.echo)
    fc = saturation.consensus_forecast(conn, claim, log=typer.echo)
    price = consensus.price_runup(conn, ticker) if ticker else None
    if price:
        typer.echo(f"  price: {price['rationale']}")
    # HONEST ASYMMETRY (the calibration fix): the eye RELIABLY detects PRICED, it can NEVER certify
    # pre-consensus (keyless search is blind to sell-side / specialist press). So 'all quiet' is
    # UNCONFIRMED — your call, not a green light. PRICED if narrative known OR forecasters hold the base
    # case OR specialist/trade press covers it ('covered'); PARTLY on a lone forecaster / a hot price.
    priced = sat.verdict == "priced/known" or fc["verdict"] in ("priced", "covered")
    partly = fc["verdict"] == "partly" or bool(price and price.get("hot"))
    overall = "PRICED" if priced else ("PARTLY-PRICED" if partly else "UNCONFIRMED — judge in-session")
    typer.echo(f"\n  ═══ {overall} ═══")
    typer.echo(f"  narrative: {sat.tier} ({sat.saturation:.2f}) · forecasters/coverage: {fc['verdict']} "
               f"({fc['n_forecasters']}f/{fc.get('n_covered', 0)} broad) · "
               f"price: {(('hot' if price['hot'] else 'quiet') if price and price.get('measured') else 'n/a')}")
    if not priced and not partly:
        typer.echo("  ⚠ UNCONFIRMED ≠ pre-consensus: keyless search can't see paywalled sell-side / specialist "
                   "notes. If the obvious layer is covered, test the layer BENEATH it; then JUDGE in-session.")
    typer.echo("  → the eye certifies PRICED, never pre-consensus; physical metric is what scores, price is optional.")
    conn.close()
    typer.echo("\ncost: $0.00")


@app.command("market-anchor")
def market_anchor_cmd(
    claim: str = typer.Argument(..., help="The claim/topic to check against live prediction markets."),
    as_json: bool = typer.Option(False, "--json", help="emit the raw anchor as JSON"),
) -> None:
    """Is a LIVE prediction market already trading this? The sharpest priced-in read for a structural
    claim with no clean equity pair (Manifold + Metaculus, keyless, $0). A liquid match = PRICED at its
    probability; the edge is only the GAP to your P. No match = UNPRICED-UNSEEN (not a green light).
    """
    import json as _json

    from engine.market import format_anchor, market_anchor
    a = market_anchor(claim)
    typer.echo(_json.dumps(a, ensure_ascii=False) if as_json else format_anchor(a))


@app.command("ground")
def ground_cmd(
    topic: str = typer.Argument(..., help="The area/thesis/claim to ground in the measured data layer."),
    as_json: bool = typer.Option(False, "--json", help="emit the raw grounding pack as JSON"),
) -> None:
    """Retrieval bridge: put the measured data layer in front of the forecaster. Composes the spine
    coverage walk + the measured signal pack (series trends, patent HHI, dependency edges) + the
    priced-in market gate into ONE grounding block. The Pope channel/gate agents run this FIRST and
    reason from it instead of from vibes. Keyless, $0.
    """
    import json as _json

    from engine.ground import format_ground, ground_pack
    g = ground_pack(topic)
    typer.echo(_json.dumps(g, ensure_ascii=False, default=str) if as_json else format_ground(g))


@app.command("data-audit")
def data_audit(
    strict: bool = typer.Option(False, help="Exit non-zero if any series fails QC (gate a collect→audit→detect chain)."),
) -> None:
    """Component 16: audit every series for freshness/completeness/validity/reconciliation/provenance.

    Writes a per-series health verdict; the detector then skips 'fail' series and forecasts refuse a
    'fail' seed — stale/incomplete data cannot silently feed a bet. Run order: collect → data-audit → detect.
    """
    conn = db.connect()
    db.init_db(conn)
    out = quality.run_audit(conn, log=typer.echo)
    conn.close()
    if strict and out["fail"] > 0:
        raise typer.Exit(code=1)


@app.command("backtest")
def backtest_cmd(
    cutoff: int = typer.Option(backtest.DEFAULT_CUTOFF, help="Cap data at this year; grade on what came after."),
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold for both firing and breakout."),
    target: str = typer.Option("gain_share", help="What to grade against: 'gain_share' (thesis) or 'acceleration'."),
    sweep: bool = typer.Option(False, help="Rolling-origin sweep (2008–2016): pooled lift, Fisher-exact p, honest LOCO Brier."),
) -> None:
    """Time-machine: blind detector calls at `cutoff`, graded against the known future (proof)."""
    conn = db.connect()
    db.init_db(conn)
    if sweep:
        backtest.run_sweep(conn, k=k, target=target, log=typer.echo)
    else:
        backtest.run_backtest(conn, cutoff=cutoff, k=k, target=target, log=typer.echo)
    conn.close()


@app.command("adapter-smoke")
def adapter_smoke() -> None:
    """Phase 2: smoke-test every adapter (cost gate, Exa, pdftotext, LLM). No spend."""
    from engine.adapters import smoke

    results = smoke.run_smoke()
    for name, ok, detail in results:
        typer.echo(f"  [{'PASS' if ok else 'FAIL'}] {name:<26} {detail}")
    passed = sum(1 for _, ok, _ in results if ok)
    typer.echo(f"{passed}/{len(results)} adapters passed.")
    if passed != len(results):
        raise typer.Exit(code=1)


@app.command("search")
def search_cmd(
    query: list[str] = typer.Argument(..., help="One or more search queries."),
    num: int = typer.Option(5, help="Results per query."),
) -> None:
    """Real keyless web search (Exa → DDG). Logs a $0 'auto' cost-ledger row before running."""
    from engine.adapters import search as search_adapter

    conn = db.connect()
    db.init_db(conn)
    out = search_adapter.search_multi(conn, query, num_results=num)
    conn.close()
    for q, results in out.items():
        typer.echo(f"\n# {q}  ({len(results)} hits)")
        for r in results:
            typer.echo(f"  - {r.title[:80]}  [{r.source}]")
            typer.echo(f"    {r.url}")


@app.command("answer")
def answer_cmd(
    question: list[str] = typer.Argument(..., help="A specific, non-interpretive factual question (a number/spec)."),
    steps: int = typer.Option(3, help="Max search/fetch rounds (1 = single-pass; >1 = multi-step agentic)."),
    proxy: str = typer.Option(None, help="Optional proxy URL to scale keyless LLM calls past per-IP limits."),
) -> None:
    """Keyless agentic hard-NUMBER lookup: search → (refine / drill into a source incl. PDFs) → ONE cited figure.

    Multi-step when needed, single-step when not — stops the instant it can answer. For settled,
    non-interpretive numbers only (specs, capacities, published counts) — never forecasts or opinion
    (that reasoning stays in-session). Always prints the source URL to verify against; degrades to the
    raw top hits rather than fabricate if the keyless LLM is down. $0 keyless.
    """
    from engine.adapters import answer as answer_adapter

    q = " ".join(question)
    conn = db.connect()
    db.init_db(conn)
    a = answer_adapter.find_number(conn, q, max_steps=steps, proxy=proxy, log=typer.echo)
    conn.close()
    typer.echo(f"\nQ: {a.question}")
    typer.echo(f"A: {a.value or '— not found —'}   ({a.steps} step{'s' if a.steps != 1 else ''})")
    typer.echo(f"   source: {a.source_url or 'n/a'}   confidence: {a.confidence}")
    if a.note:
        typer.echo(f"   note: {a.note}")
    if a.value is None and a.hits:
        typer.echo("   top hits (manual read):")
        for r in a.hits[:5]:
            typer.echo(f"     - {r.title[:70]}  {r.url}")
    typer.echo("cost: $0.00")


@app.command("approve-cost")
def approve_cost(
    ledger_id: str = typer.Argument(..., help="cost_ledger id to approve."),
    by: str = typer.Option(..., "--by", help="Who is approving (the human)."),
) -> None:
    """Approve a pending spend the cost gate blocked (rule 3)."""
    conn = db.connect()
    db.init_db(conn)
    ok = cost.approve(conn, ledger_id, by)
    conn.close()
    typer.echo(f"approved {ledger_id}" if ok else f"no pending row with id {ledger_id}")


@app.command("forecast-seed")
def forecast_seed() -> None:
    """Write the first ForecastCards from the scRNA-seq detector hit (reasoned in-session, $0)."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_forecasts(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} card(s) created, {out['resolved']} resolved. cost: $0.00")


@app.command("forecast-batch")
def forecast_batch() -> None:
    """Author the dozen FORWARD structural calls (the starved-instrument deliverable).

    Each is a one-layer-deeper, physical-primary structural forecast: P + 80% interval + a dated
    resolution metric + kill-criteria, adversarially challenged in-session. Idempotent on the
    question; several seed off real in-DB series so driver-status can track them now. $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_forward_batch(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} created, {out.get('superseded', 0)} superseded "
               f"(stock-pick → physical-primary), {out['skipped']} already present. cost: $0.00")


@app.command("scenario-seed")
def scenario_seed() -> None:
    """Author the forecast WEBS — linked, confidence-weighted scenario trees instead of one
    extrapolated statement. Currently: HVDC deployment · injectable delivery (GLP-1/biologics) ·
    ex-China rare-earth/critical-input refining · US electrification labour. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_all_webs(conn, log=typer.echo)
    total = out["created"]
    conn.close()
    typer.echo(f"done — {total} web node(s) written. cost: $0.00")


@app.command("scenario")
def scenario_show(scenario_id: str) -> None:
    """Print a forecast WEB as a tree: each node with its CONDITIONAL P and its MARGINAL P
    (= product of conditionals down its path)."""
    conn = db.connect()
    db.init_db(conn)
    tree = forecast.scenario_tree(conn, scenario_id)
    conn.close()

    def render(node: dict, depth: int) -> None:
        pad = "  " * depth
        tag = "" if depth == 0 else f"cond {node['conditional_p']:.0%} · "
        typer.echo(f"{pad}[{node['marginal_p']:.0%}] {tag}{node['question'][:96]}")
        for k in node["children"]:
            render(k, depth + 1)

    render(tree, 0)


@app.command("webs-v2")
def webs_v2() -> None:
    """Act on the 44/100 external review: author the 4 corrected webs (re-priced / MECE-fixed) + the
    new SiC / power-semiconductor web, supersede the v1 webs (rule 7), re-point the belief-net by
    question. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.rebuild_v2(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['webs_created']} v2 node(s) + {out['edges']} belief edge(s). cost: $0.00")


@app.command("belief-seed")
def belief_seed() -> None:
    """Author the cross-thesis BELIEF-NET edges — one web's resolution shifting another web's P, where
    two webs share an inelastic input. Idempotent, $0."""
    conn = db.connect()
    db.init_db(conn)
    out = forecast.seed_belief_edges(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} belief edge(s) written. cost: $0.00")


@app.command("belief-net")
def belief_net_show(resolve: list[str] = typer.Option(None, "--resolve", help="card-id-or-prefix=true/false")) -> None:
    """Show the belief-net: each cross-web edge with the target's baseline P and — if you pass
    --resolve <from>=true/false — the target's CONDITIONAL view. Pure read; never mutates a card.
    e.g. `belief-net --resolve db8b6288=true` (ex-China magnets bind) shifts the linked roots."""
    resolved = {}
    for r in (resolve or []):
        if "=" not in r:
            raise typer.BadParameter("use card=true / card=false")
        k, v = r.rsplit("=", 1)
        resolved[k.strip()] = v.strip().lower() in ("true", "t", "1", "yes")
    conn = db.connect()
    db.init_db(conn)
    net = forecast.belief_net(conn, resolved=resolved)
    conn.close()

    for e in net["edges"]:
        arrow = "↑" if e["sign"] == 1 else "↓"
        shift = "" if e["state"] == "prior" else f"  ⇒ {e['state']}: {e['p_to_baseline']:.0%} → {e['view']:.0%}"
        typer.echo(f"[{e['from_id'][:8]}] {e['from_q']}…  (P {e['p_from']:.0%})")
        typer.echo(f"   {arrow}{'+' if e['sign']==1 else '−'} → [{e['to_id'][:8]}] {e['to_q']}…  base {e['p_to_baseline']:.0%}{shift}")
        typer.echo(f"      ↳ {e['mechanism'][:110]}…")
    if net["islands"]:
        typer.echo("\nislands (no cross-web edge — honestly decoupled):")
        for i in net["islands"]:
            typer.echo(f"   ◦ [{i['root_id'][:8]}] {i['q']}…")


@app.command("constraint-cards")
def constraint_cards() -> None:
    """Write the GRAPH-DERIVED constraint cards (redteam #2): probability = P(bottleneck) from the
    supply-graph propagation, magnitude = the supply-gap CI — NOT a trend extrapolation. Pairs with
    the demand-count cards (whose probability is the series-growth MC). $0, idempotent."""
    conn = db.connect()
    db.init_db(conn)
    out = graph.seed_constraint_cards(conn, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['created']} constraint card(s) written. cost: $0.00")


@app.command("ladder-run")
def ladder_run(
    horizon: int = typer.Option(ladder.H_YEARS, help="Rung horizon in years (intermediate metrics are annual)."),
    rebuild: bool = typer.Option(False, "--rebuild", help="Wipe existing rungs and rebuild — re-measure calibration cleanly after a method change."),
    point_estimate: bool = typer.Option(False, "--point-estimate", help="Use the old plug-in MC (no parameter-uncertainty tails) — for A/B against honest tails."),
    no_sharpen: bool = typer.Option(False, "--no-sharpen", help="Issue the univariate MC persistence P (calibrated, AUC ~0.5) instead of the sharpened model — for A/B against discrimination."),
) -> None:
    """The fast-resolution ladder (redteam #3): rolling-origin short-horizon micro-forecasts on EVERY
    QC-passing series, Brier-scored on resolution NOW. Calibrated (full-history drift + honest tails)
    AND discriminating (sharpen.py logistic, leak-free expanding window, AUC ~0.68). $0."""
    conn = db.connect()
    db.init_db(conn)
    out = ladder.run_ladder(conn, h=horizon, honest_tails=not point_estimate,
                            sharpen_p=not no_sharpen, clear=rebuild, log=typer.echo)
    conn.close()
    typer.echo(f"done — {out['new']} rungs ({out['resolved_now']} resolved this run); "
               f"{out['n_resolved']} total resolved. cost: $0.00")


def _echo_driver_health(h: dict) -> None:
    """Print one card/hypothesis's live driver verdict (the cockpit is the real view)."""
    sig = "—" if h["signal"] is None else f"{h['signal']:.0%}"
    head = h.get("title", h.get("card_id") or h.get("hypothesis_id"))
    typer.echo(f"\n{head}")
    typer.echo(f"  driver signal {sig}  ·  {h['n']} driver(s): {h['n_on_track']} on-track, "
               f"{h['n_approaching']} approaching, {h['n_falsified']} falsified, {h['n_no_data']} no-data "
               f"→ worst: {h['worst_status'].upper()}")
    for d in h["drivers"]:
        ms = "—" if d["margin_sigma"] is None else f"{d['margin_sigma']:+.2f}σ"
        val = "—" if d["value"] is None else f"{d['value']:g}"
        arrow = {"fails_below": ">=", "fails_above": "<="}[d["direction"]]
        typer.echo(f"    [{d['status']:<11}] {d['label'][:44]:<44} {val} {arrow} {d['threshold']:g} "
                   f"(margin {ms}, trend {d['trend']})")


@app.command("driver-link")
def driver_link(
    series: str = typer.Option(..., help="The leading-indicator series id this driver watches."),
    threshold: float = typer.Option(..., help="The falsification level (a kill-criterion's numeric bound)."),
    direction: str = typer.Option(..., help="'fails_below' | 'fails_above' — which way the metric trips the kill-criterion."),
    confirm: str = typer.Option(..., help="'up' | 'down' — which trend direction moves TOWARD confirmation."),
    card: str = typer.Option(None, help="Forecast card id this driver hangs off (xor --hypothesis)."),
    hypothesis_id: str = typer.Option(None, "--hypothesis", help="Hypothesis id this driver hangs off (xor --card)."),
    kill_index: int = typer.Option(None, "--kill-index", help="Which kill_criteria[i] this proxies (provenance only)."),
    note: str = typer.Option("", help="Why this series proxies this kill-criterion (GIGO)."),
) -> None:
    """Link one kill-criterion / driver to a series — forecast the DRIVERS, not the endpoint.

    The judgment (which series proxies which kill-criterion) is Claude's, in-session; this only records
    the link + threshold. Observe-only — it never edits the immutable card (rule 7). $0."""
    conn = db.connect()
    db.init_db(conn)
    out = indicators.link_driver(
        conn, series_id=series, threshold=threshold, direction=direction, confirm_dir=confirm,
        card_id=card, hypothesis_id=hypothesis_id, kill_index=kill_index, note=note)
    frontier._log_cost(conn, "driver_link", "in_session", 1.0)
    conn.commit()
    conn.close()
    typer.echo(f"{'updated' if out['updated'] else 'linked'} driver {out['id'][:8]}. cost: $0.00")


@app.command("driver-status")
def driver_status(
    card: str = typer.Option(None, help="Show one card's driver health (8-char id ok)."),
    hypothesis_id: str = typer.Option(None, "--hypothesis", help="Show one hypothesis's driver health."),
) -> None:
    """The leading-indicator scoreboard: are the drivers of our live calls trending toward confirmation
    or falsification NOW — years before the slow resolution date? Observe-only. $0."""
    conn = db.connect()
    db.init_db(conn)
    if card or hypothesis_id:
        _echo_driver_health(indicators.card_driver_health(conn, card_id=card, hypothesis_id=hypothesis_id))
    else:
        rows = indicators.all_driver_health(conn)
        if not rows:
            typer.echo("No drivers linked yet. Link one: "
                       "`driver-link --card <id> --series <id> --threshold <x> --direction fails_below --confirm up`.")
        for h in rows:
            _echo_driver_health(h)
    conn.close()


@app.command("driver-seed")
def driver_seed() -> None:
    """Link the obvious driver for the live scRNA-seq FORWARD card: its kill-criterion 'FY2026 awards
    < 6,500' → the seed series itself (awards/year, confirming = up). Idempotent; demonstrates the
    tracker end-to-end like `hypothesis-seed`. $0."""
    conn = db.connect()
    db.init_db(conn)
    row = conn.execute(
        "SELECT id, seed_series_id FROM forecast_cards WHERE question LIKE 'By FY2026,%single-cell RNA-seq%' "
        "AND superseded_by IS NULL ORDER BY created_at DESC LIMIT 1").fetchone()
    if row is None or not row["seed_series_id"]:
        typer.echo("scRNA-seq FORWARD card not found (run `seed-forecasts` first). nothing linked.")
        conn.close()
        return
    out = indicators.link_driver(
        conn, series_id=row["seed_series_id"], threshold=6500, direction="fails_below", confirm_dir="up",
        card_id=row["id"], kill_index=0,
        note="Kill-criterion 0 ('FY2026 awards < 6,500 — demand acceleration stalled') made machine-"
             "readable: the seed NIH-grant series IS the demand-leg leading indicator; rising = confirming.")
    frontier._log_cost(conn, "driver_link", "in_session", 1.0)
    conn.commit()
    h = indicators.card_driver_health(conn, card_id=row["id"])
    conn.close()
    typer.echo(f"{'updated' if out['updated'] else 'linked'} driver on card {row['id'][:8]}.")
    _echo_driver_health(h)
    typer.echo("\ncost: $0.00")


@app.command("emergent-scan")
def emergent_scan_cmd(
    limit: int = typer.Option(12, help="target number of PURSUE calls"),
    no_capture: bool = typer.Option(False, "--no-capture", help="judge only, skip the capture step"),
    all_concepts: bool = typer.Option(False, "--all", help="include abstract research-data concepts (default: physical needles only)"),
    json_out: bool = typer.Option(False, "--json", help="machine-readable output"),
) -> None:
    """The detect→gate→CAPTURE loop: accelerating+commercializing concepts → DeepSeek judges pre-consensus
    → web-grounds a named factory/person/ask for survivors. PAID (DeepSeek, ~sub-cent/call; logged). Parks
    PURSUE calls for `emergent-card`. NO Opus."""
    import json as _json
    from engine import emergent_scan
    conn = db.connect()
    db.init_db(conn)
    results = emergent_scan.scan(conn, limit=limit, do_capture=not no_capture,
                                 physical=not all_concepts, log=typer.echo)
    conn.close()
    if json_out:
        typer.echo(_json.dumps(results, ensure_ascii=False, default=str))
    else:
        typer.echo("\n" + emergent_scan.format_report(results))


@app.command("emergent-card")
def emergent_card(
    concept: str = typer.Option(..., help="concept name of a parked PURSUE call (from the last emergent-scan)."),
    question: str = typer.Option(None, help="override the auto-framed binary question (recommended — make it cleanly falsifiable)."),
    resolution_date: str = typer.Option(None, help="ISO resolution date (default: today + horizon_years)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the card fields without writing."),
) -> None:
    """Graduate ONE reviewed PURSUE call from the last emergent-scan into an immutable forecast card
    (fork C — "make it land"). Deliberate, human-picked (rule 7: never auto-promoted); the altitude +
    seed-QC gates in create_card are the safety net. $0."""
    import json as _json
    from engine import emergent_scan
    calls = emergent_scan.load_latest()
    match = next((c for c in calls if c.get("concept", "").lower() == concept.lower()), None)
    if match is None:
        avail = ", ".join(c.get("concept", "?") for c in calls) or "(none — run `emergent-scan` first)"
        typer.echo(f"no parked PURSUE call for '{concept}'. available: {avail}")
        raise typer.Exit(1)
    res = date.fromisoformat(resolution_date) if resolution_date else None
    fields = emergent_scan.build_card_fields(match, resolution_date=res, question=question)
    if dry_run:
        typer.echo(_json.dumps({**fields, "resolution_date": fields["resolution_date"].isoformat()},
                               ensure_ascii=False, indent=2))
        return
    conn = db.connect()
    db.init_db(conn)
    card = forecast.create_card(conn, **fields)
    conn.close()
    typer.echo(f"created {card.id} — '{fields['question']}' P={fields['probability']}")


@app.command("forecast-add")
def forecast_add(
    question: str = typer.Option(..., help="The binary, point-in-time question with a clear resolution."),
    prob: float = typer.Option(..., help="P of the binary resolving true (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date when we'll know (YYYY-MM-DD)."),
    kill: list[str] = typer.Option(..., "--kill", help="A kill-criterion (repeat for several). Required."),
    rationale: str = typer.Option(..., help="The reasoning — base rate + decomposition."),
    ci_low: float = typer.Option(None, help="80% credible-interval low on the central quantity."),
    ci_high: float = typer.Option(None, help="80% credible-interval high."),
    ci_unit: str = typer.Option(None, help="Unit of the credible interval."),
    seed_series: str = typer.Option(None, help="series id this forecast grew from."),
    pillar: list[int] = typer.Option([], "--pillar", help="Pillar id(s) used."),
    source: list[str] = typer.Option([], "--source", help="Source id(s) cited."),
    saturation: float = typer.Option(None, help="Measured narrative-saturation at issue (0..1) — sets the consensus-echo tag (plan.md #6)."),
) -> None:
    """Write a new immutable ForecastCard via the CLI seam (rule 7 — never edited, only superseded)."""
    conn = db.connect()
    db.init_db(conn)
    card = forecast.create_card(
        conn, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date),
        ci_low=ci_low, ci_high=ci_high, ci_unit=ci_unit, seed_series_id=seed_series,
        rationale=rationale, kill_criteria=list(kill), saturation=saturation,
        pillars_used=list(pillar), source_ids=list(source),
    )
    conn.close()
    typer.echo(f"created {card.id}")


@app.command("forecast-supersede")
def forecast_supersede(
    old_id: str = typer.Argument(..., help="The card to supersede (retained, never edited)."),
    question: str = typer.Option(..., help="The revised question."),
    prob: float = typer.Option(..., help="Revised probability (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date (YYYY-MM-DD)."),
    kill: list[str] = typer.Option(..., "--kill", help="Kill-criterion (repeat). Required."),
    rationale: str = typer.Option(..., help="Why the revision."),
    ci_low: float = typer.Option(None), ci_high: float = typer.Option(None),
    ci_unit: str = typer.Option(None), seed_series: str = typer.Option(None),
    pillar: list[int] = typer.Option([], "--pillar"),
    source: list[str] = typer.Option([], "--source"),
) -> None:
    """Replace a card with a revised one; the old stays for the track record (rule 7)."""
    conn = db.connect()
    db.init_db(conn)
    new = forecast.supersede(
        conn, old_id, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date),
        ci_low=ci_low, ci_high=ci_high, ci_unit=ci_unit, seed_series_id=seed_series,
        rationale=rationale, kill_criteria=list(kill),
        pillars_used=list(pillar), source_ids=list(source),
    )
    conn.close()
    typer.echo(f"superseded {old_id} → {new.id}")


@app.command("forecast-resolve")
def forecast_resolve(
    card_id: str = typer.Argument(..., help="The card to resolve."),
    outcome: str = typer.Option(..., help="'true' or 'false'."),
) -> None:
    """Resolve a card and compute its Brier score = (p − outcome)²."""
    conn = db.connect()
    db.init_db(conn)
    brier = forecast.resolve(conn, card_id, ForecastOutcome(outcome))
    conn.close()
    typer.echo(f"resolved {card_id} as {outcome} → Brier {brier:.3f}")


@app.command("forecast-seal")
def forecast_seal() -> None:
    """Seal the live forward record: export every unresolved STRUCTURAL call to a deterministic,
    committable manifest + sha256. The git commit of those files is the un-backdateable timestamp
    (the moat — VATI §6). Re-running on an unchanged record is byte-identical. $0."""
    conn = db.connect()
    db.init_db(conn)
    r = forecast.export_seal(conn)
    conn.close()
    typer.echo(f"sealed {r['n_calls']} live forward structural calls → {r['path']}")
    typer.echo(f"sha256 {r['sha256']}")
    typer.echo("  next: git add experiments/forward_calls_seal.* && git commit  (commit = the timestamp seal;")
    typer.echo("        later `ots stamp experiments/forward_calls_seal.sha256` adds a blockchain proof)")


@app.command("forecast-list")
def forecast_list() -> None:
    """List live (non-superseded) cards + the calibration scoreboard vs the naive baseline."""
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT id, question, probability, resolution_date, outcome, brier_score "
        "FROM forecast_cards WHERE superseded_by IS NULL ORDER BY created_at"
    ).fetchall()
    cal = forecast.calibration(conn)
    conn.close()
    for r in rows:
        state = f"resolved {r['outcome']} (Brier {r['brier_score']:.3f})" if r["outcome"] else "open"
        typer.echo(f"  [{state}] p={r['probability']:.2f} by {r['resolution_date']}  {r['question'][:70]}")
    if cal["n_resolved"]:
        typer.echo(f"calibration: {cal['n_resolved']} resolved · mean Brier "
                   f"{cal['brier_model']:.3f} vs naive baseline {cal['brier_baseline']:.3f}")
    else:
        typer.echo("calibration: no resolved cards yet.")


@app.command("graph-seed")
def graph_seed(
    chain: str = typer.Option("scrna_seq", help="Chain to build: 'scrna_seq', 'ai_power', or 'metals'."),
) -> None:
    """Phase 4: build a supply graph (sourced nodes + typed edges) + the verify Decision. Chain-agnostic."""
    conn = db.connect()
    db.init_db(conn)
    if chain == "metals":
        # The cross-DOMAIN extension: metals chain + the ai_power→metals edges. Needs ai_power first.
        if not conn.execute("SELECT 1 FROM graph_nodes WHERE chain='ai_power' LIMIT 1").fetchone():
            graph.seed_ai_power(conn, log=typer.echo)
        out = graph.seed_metals(conn, log=typer.echo)
        conn.close()
        typer.echo(f"done — {out['nodes']} metals nodes / {out['edges']} edges + {out['cross_edges']} "
                   f"cross-domain edges into ai_power. Flow the connected world: "
                   f"graph-propagate --chain ai_power --world. cost: $0.00")
        return
    if chain == "ai_power":
        out = graph.seed_ai_power(conn, log=typer.echo)
        d = graph.propose_ai_power_verification(conn)
    else:
        out = graph.seed_graph(conn, log=typer.echo)
        d = graph.propose_verification(conn)
    conn.close()
    typer.echo(f"verify-decision open: {d.id}")
    typer.echo("  → " + d.prompt[:90] + "…")
    typer.echo(f"  HUMAN-VERIFY before propagating. Then: graph-propagate --chain {chain} --verify <decision_id>")
    typer.echo(f"done — {out['nodes']} nodes / {out['edges']} edges / {out['sources']} sources. cost: $0.00")


@app.command("graph-propagate")
def graph_propagate(
    chain: str = typer.Option("scrna_seq", help="Which chain to flow: 'scrna_seq' or 'ai_power'."),
    world: bool = typer.Option(
        False, "--world",
        help="Flow across the CONNECTED world (ai_power + metals), not one chain — cross-domain."),
    verify: str = typer.Option(
        None, "--verify",
        help="The decision id the human confirmed. Required to tie back to the forecast (the gate).",
    ),
    tie_back: bool = typer.Option(
        False, "--tie-back", help="Supersede the forward card with the graph-derived version (rule 7)."),
) -> None:
    """Flow the 10x shock → first-saturating, least-substitutable node + supply-gap interval."""
    conn = db.connect()
    db.init_db(conn)
    shock = graph.AI_POWER_SHOCK if chain == "ai_power" else graph.SHOCK
    chains = ("ai_power", "metals") if world else None
    scope_label = " + ".join(chains) if chains else chain
    prop = graph.propagate(conn, chain=chain, chains=chains, shock=shock)
    typer.echo(f"\n{shock:.0f}x demand shock → constraint propagation over '{scope_label}':")
    for p in prop.pressures:
        mark = "  ← BOTTLENECK" if p is prop.bottleneck else ""
        typer.echo(
            f"  {p.name[:48]:<48} req {p.required_multiple:>4.0f}x  supply {p.supply_multiple:>4.1f}x  "
            f"subst {p.substitutability:>3.0%}  pressure {p.pressure:>5.2f}  P(bn)={p.p_bottleneck:>4.0%}{mark}"
        )
    b = prop.bottleneck
    typer.echo(f"\nBOTTLENECK: {b.name}")
    typer.echo(f"  supply gap {prop.gap_median:.1f}x (80% CI [{prop.gap_ci_low:.1f},{prop.gap_ci_high:.1f}]) "
               f"· P(this is THE bottleneck) {b.p_bottleneck:.0%}")
    if prop.obvious_endpoint:
        o = prop.obvious_endpoint
        typer.echo(f"  (the obvious endpoint '{o.name[:40]}' is ELASTIC: pressure {o.pressure:.2f}, "
                   f"substitutability {o.substitutability:.0%} — rent does NOT land there)")

    # where to point the deep-data drill: high pressure × thin data coverage (data follows the graph)
    drills = graph.drill_targets(conn, prop, chain=chain, chains=chains)
    typer.echo("\nDRILL ORDER (where data, not reasoning, is binding — P(bn) × (1−coverage)):")
    for d in drills[:5]:
        typer.echo(f"  {d.drill_score:>5.2f}  {d.name[:44]:<44} [{d.chain}]  cov {d.coverage:>3.0%}  · {d.why}")

    # VALUE OF INFORMATION (execution §3 "spend the variance budget"): which single measurement most
    # sharpens WHERE the bottleneck is? The top term is the cheapest next measurement — the operator payoff.
    modal_name, base_p, voi = graph.variance_budget(conn, chain=chain, chains=chains, shock=shock)
    typer.echo(f"\nVALUE OF INFORMATION (measure-this-next — P(bottleneck '{modal_name[:30]}') = {base_p:.0%}):")
    for t in voi[:4]:
        typer.echo(f"  +{t.voi:>5.1%}  {t.input_name[:46]:<46} · {t.why}")
    if voi:
        typer.echo(f"  → measure FIRST: {voi[0].input_name} (collapses the most uncertainty about the bottleneck).")

    if tie_back:
        if chain == "ai_power":
            conn.close()
            typer.echo("\nNOTE: ai_power ties back via `hypothesis-promote` (the forward card is a fresh "
                       "promotion of the survived thesis, not a supersede). Confirm the verify-Decision "
                       "with `graph-verify`, then run hypothesis-promote.")
            raise typer.Exit(code=0)
        if not verify:
            conn.close()
            typer.echo("\nREFUSED: --tie-back needs --verify <decision_id> (rule 4 — never flow an "
                       "unverified chain into a forecast).")
            raise typer.Exit(code=1)
        row = conn.execute("SELECT status, chosen_option FROM decisions WHERE id=?", (verify,)).fetchone()
        if row is None or row["status"] != "decided":
            conn.close()
            typer.echo(f"\nREFUSED: decision {verify} is not confirmed yet (human-verify gate, §9).")
            raise typer.Exit(code=1)
        res = graph.graph_backed_forward_card(conn, prop)
        if res["superseded"]:
            typer.echo(f"\ntied back → superseded {res['old_id']} → {res['new_id']} "
                       f"(graph-derived; bottleneck '{res['bottleneck']}').")
        else:
            typer.echo(f"\ntie-back skipped: {res['reason']}")
    conn.close()
    typer.echo("cost: $0.00")


@app.command("graph-verify")
def graph_verify(
    decision_id: str = typer.Argument(..., help="The open verify-Decision id."),
    choose: str = typer.Option(..., "--choose", help="The option the human picked."),
) -> None:
    """Stamp the human's verification onto the supply-graph Decision (closes the gate, rule 4)."""
    conn = db.connect()
    db.init_db(conn)
    graph.record_decision(conn, decision_id, choose)
    conn.close()
    typer.echo(f"decision {decision_id} → decided: {choose!r}")


@app.command("consensus-score")
def consensus_score(
    chain: str = typer.Option("scrna_seq", help="Which thesis to gate: 'scrna_seq' or 'ai_power'."),
) -> None:
    """Phase 5 gate (pillar 7): is the constraint bottleneck already priced in?

    Pulls keyless market signals (Stooq close + SEC XBRL fundamentals), computes the numeric
    consensus delta = modeled fair premium − market-implied premium, and flags an edge only if it
    clears the threshold. Every fetch is logged to the cost ledger first ($0 auto). cost: $0.00.
    """
    cfg = consensus.AI_POWER_CFG if chain == "ai_power" else consensus.SCRNA_CFG
    conn = db.connect()
    db.init_db(conn)
    typer.echo(f"consensus gate — {cfg.chain}: inelastic ({cfg.consumable['sym']}) "
               f"vs obvious ({cfg.sequencer['sym']})")
    consensus.score_consensus(conn, cfg=cfg, log=typer.echo)
    conn.close()
    typer.echo("cost: $0.00")


@app.command("bet-translate")
def bet_translate(
    supersede: bool = typer.Option(
        False, "--supersede", help="Revise the live bet (old retained, rule 7) instead of skipping."),
) -> None:
    """Phase 5 half 2 (pillar 12): turn the scRNA-seq consensus EDGE into a sized PAPER bet.

    Maps the constraint → instrument(s) (long the inelastic consumable hedged short the elastic
    sequencer), sizes it (capped fractional Kelly from the edge magnitude + uncertainty), ties the
    horizon to the forecast card, and operationalizes the kill-criteria into monitorable triggers.
    Paper only — translation, NOT execution. No data fetch ⇒ no spend. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    typer.echo("bet translation — scRNA-seq: long consumable (TXG) / short sequencer (ILMN)")
    card = bet.translate(conn, supersede_live=supersede, log=typer.echo)
    conn.close()
    if card is None:
        raise typer.Exit(code=1)
    typer.echo("cost: $0.00")


@app.command("retro-run")
def retro_run(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (frozen at 3 — do NOT tune to the corpus)."),
) -> None:
    """Phase 6: run the §8 winners+fizzles corpus point-in-time with the method FROZEN.

    Seeds the corpus as point-in-time series, lets the EXISTING detector decide blindly on data
    ≤ each case's signal_date (no new forecasting logic), then scores precision + recall + lead-
    time + Brier vs the base-rate baseline. Look-ahead is verified absent. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    out = retro.run(conn, k=k, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['cases']} cases, look-ahead violations: {out['look_ahead_violations']}. cost: $0.00")


@app.command("recall-probe")
def recall_probe(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (frozen at 3 — same as §8)."),
) -> None:
    """The §3 recall fix, VALIDATED: does a finer leading channel catch the AI-compute-class miss early?

    Rolls the cutoff back over the live monthly arXiv talent-inflow / topic-share channels
    (research.py) for the §8 ai_compute case and asks, point-in-time, at which cutoff each first fires.
    Uses the SAME frozen detector; NEVER edits the §8 scoreboard (that would be tuning, §9). Persists to
    recall_probe so the cockpit surfaces it. cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    out = retro.recall_probe(conn, k=k, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['recall_gains']}/{out['probes']} channels close the miss early. cost: $0.00")


@app.command("universe-run")
def universe_run(
    k: float = typer.Option(detector.DEFAULT_K, help="σ threshold (FROZEN at 3 — never tune to the universe)."),
    origins: str = typer.Option("", help="comma-separated origin years (default = the frozen 5). Ad-hoc only."),
    gain_margin: float = typer.Option(backtest.GAIN_MARGIN, help="share-gain label threshold (FROZEN at 1.5)."),
    channels: str = typer.Option("count", help="count | count+diffusion | count+diffusion+talent."),
    block_null: bool = typer.Option(False, help="also compute the block-permutation p + lift CI (slower)."),
) -> None:
    """Phase 6+: the survivorship-killer. Run the FROZEN method across a MECHANICALLY-DRAWN universe.

    Instead of 10 famous cases, the candidate set is drawn by a frozen rule from the OpenAlex concept
    pool (data ≤ each origin), the win/lose label is assigned by a frozen gain-of-share rule (data >
    origin), and the existing detector calls each blind. Reports the pooled + de-clustered confusion
    matrix, lift, lead-time, Fisher-p and honest LOCO Brier — nobody picked the cases or the outcomes.
    The knobs are ad-hoc exploration only; the PRE-REGISTERED experiment is `experiment-select`/
    `experiment-reveal` (experiments/protocol_v1.yaml). cost: $0.00.
    """
    conn = db.connect()
    db.init_db(conn)
    org = tuple(int(x) for x in origins.split(",") if x.strip()) or universe.ORIGINS
    out = universe.run(conn, k=k, origins=org, gain_margin=gain_margin, channels=channels,
                       block_null=block_null, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['drawn']} drawn / {out['scored']} scored across {out['n_origins']} origins, "
               f"look-ahead violations: {out['look_ahead_violations']}. cost: $0.00")


@app.command("experiment-select")
def experiment_select(
    m: int = typer.Option(2000, help="block-permutation / bootstrap draws (deterministic seed)."),
) -> None:
    """Stage 1 (pre-registered): run the full search space on the SELECTION origins, ledger every
    config, promote argmax de-clustered lift. Never touches the sealed TEST origins. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.select_and_seal(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-reveal")
def experiment_reveal(
    m: int = typer.Option(2000, help="block-permutation / bootstrap draws (deterministic seed)."),
) -> None:
    """Stage 1: the ONE-TIME sealed-TEST reveal. Scores the promoted config on the held-out TEST
    origins, deflates the p by the configs tried, records it immutably. Refuses if already revealed.
    Ensure experiments/protocol_v1.yaml is committed FIRST (the seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.reveal_test(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-status")
def experiment_status() -> None:
    """Stage 1: print the experiment ledger — configs tried, the deflation denominator, the best
    selection lift, and whether TEST is still sealed. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.status(conn, log=typer.echo)
    conn.close()


@app.command("experiment-v2-select")
def experiment_v2_select(m: int = typer.Option(2000, help="block-perm / bootstrap draws.")) -> None:
    """protocol_v2 (concept-disjoint, powered): run the search space on the SELECT concepts, ledger,
    promote. Never scores the held-out TEST concepts. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.select_and_seal_v2(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-v2-reveal")
def experiment_v2_reveal(m: int = typer.Option(2000, help="block-perm / bootstrap draws.")) -> None:
    """protocol_v2: the ONE-TIME concept-disjoint TEST reveal + per-provider grain breakdown. Refuses
    if already revealed. Commit experiments/protocol_v2.yaml FIRST (the seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.reveal_test_v2(conn, m=m, log=typer.echo)
    conn.close()


@app.command("experiment-power")
def experiment_power(
    m_inner: int = typer.Option(2000, help="block-permutation draws per synthetic set (resolution)."),
    m_outer: int = typer.Option(400, help="synthetic datasets per assumed true lift (power estimate)."),
) -> None:
    """Power analysis of the v2 sealed-TEST: was the null well-powered (signal dead) or under-powered
    (couldn't see a weak edge)? Prints the power curve + MDE_80, raw and deflated by the CUMULATIVE
    config count. Read-only — writes nothing (audits a closed seal). cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    experiment.power_report(conn, m_inner=m_inner, m_outer=m_outer, log=typer.echo)
    conn.close()


@app.command("locator-run")
def locator_run(
    k: float = typer.Option(detector.DEFAULT_K, help="detector σ threshold (frozen at 3)."),
) -> None:
    """Stage 2: the mechanical constraint-LOCATOR — the one retro-test of the THESIS with an
    INDEPENDENT (price) label. Wires layer-price feeds, runs the rolling-origin locator over the
    connected ai_power→metals world, grades located/obvious/graph picks vs the realized price winner.
    Honest small N — suggestive, not proof. Commit experiments/protocol_locator.yaml first. cost: $0.00."""
    conn = db.connect()
    db.init_db(conn)
    locator.run(conn, k=k, log=typer.echo)
    conn.close()


@app.command("holdout-run")
def holdout_run(
    provider: str = typer.Option("deepinfra_keyless", help="LLM provider: deepinfra_keyless ($0) | "
                                 "openrouter | minimax. An OLD-cutoff model (openrouter "
                                 "openai/gpt-3.5-turbo-0613) is required for a VALID run."),
    model: str = typer.Option("", help="explicit model id (e.g. openai/gpt-3.5-turbo-0613). Empty = roster."),
    est_cost_cents: int = typer.Option(0, help="estimated spend for the cost gate (keyed routes)."),
    proxy: bool = typer.Option(False, help="route keyless calls through the residential proxy."),
) -> None:
    """Stage 3: the older-model temporal holdout — the only leakage-bounded test of LLM JUDGMENT. Probes
    the model's effective cutoff FIRST and refuses to score unless it is provably blind to the outcomes
    (the leakage gate). Keyless/MiniMax are ~2025-cutoff → they fail the gate (the honest blocker until
    an old-cutoff model is wired). cost-gated (rule 3)."""
    from engine.adapters import proxy as proxymod
    conn = db.connect()
    db.init_db(conn)
    px = proxymod.proxy_url() if proxy and proxymod.available() else None
    holdout.run(conn, provider=provider, model=(model or None), est_cost_cents=est_cost_cents,
                proxy=px, log=typer.echo)
    conn.close()


@app.command("structbench-run")
def structbench_run(
    provider: str = typer.Option("openrouter", help="LLM provider. An OLD-cutoff model (e.g. openrouter "
                                 "meta-llama/llama-3-70b-instruct) is required for a leak-free run."),
    model: str = typer.Option("", help="explicit model id. Empty = roster."),
    est_cost_cents: int = typer.Option(0, help="estimated spend for the cost gate (keyed routes)."),
    threshold: float = typer.Option(0.05, help="the fixed ≥X% rise rule (pre-registered)."),
    proxy: bool = typer.Option(False, help="route keyless calls through the residential proxy."),
) -> None:
    """The DEFENSIBLE retro bench: run THE FRAMEWORK on Class-1 structural questions mechanically built
    from the engine's public dated series (FRED/Comtrade/World Bank/OWID/Epoch), leak-gated. Immune to
    the 'self-authored / N=7' critiques. Pre-registered in experiments/protocol_structbench.yaml.
    cost-gated (rule 3)."""
    from engine.adapters import proxy as proxymod
    conn = db.connect()
    db.init_db(conn)
    px = proxymod.proxy_url() if proxy and proxymod.available() else None
    holdout.run_structural(conn, provider=provider, model=(model or None),
                           est_cost_cents=est_cost_cents, threshold=threshold, proxy=px, log=typer.echo)
    conn.close()


@app.command("entity-seed")
def entity_seed() -> None:
    """Component 2: resolve the curated entity clusters (in-session judgment, GIGO-rationaled).

    Links existing rows — frontier series, supply-graph nodes, market tickers — onto canonical
    entities, so one technology/firm can be traced across pillars. Additive, idempotent, $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = entity.seed(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['entities']} entities, {out['links']} links, "
               f"{out['missing']} missing. cost: $0.00")


@app.command("entity-list")
def entity_list() -> None:
    """Show resolved entities + the pillars each spans (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    entity.list_entities(conn, log=typer.echo)
    conn.close()


@app.command("entity-candidates")
def entity_candidates_cmd(
    generate: bool = typer.Option(False, help="Generate new candidate links for unlinked series."),
) -> None:
    """A7: propose entity links for unlinked rows (exact-id + string-blocking), then list them.

    Generators only PROPOSE; nothing commits without `entity-accept`. Fuzzy may propose, never commit.
    """
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    if generate:
        ec.generate(conn, log=typer.echo)
    ec.list_proposed(conn, log=typer.echo)
    conn.close()


@app.command("entity-accept")
def entity_accept(candidate_id: str = typer.Argument(..., help="entity_candidates id (8-char ok).")) -> None:
    """Promote a proposed candidate to a committed entity_link (human/Claude verify gate)."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    # accept by full or short id
    row = conn.execute("SELECT id FROM entity_candidates WHERE id=? OR id LIKE ?",
                       (candidate_id, candidate_id + "%")).fetchone()
    if not row:
        typer.echo(f"no candidate matching {candidate_id}")
        raise typer.Exit(code=1)
    typer.echo(ec.accept(conn, row["id"]))
    conn.close()


@app.command("entity-reject")
def entity_reject(candidate_id: str = typer.Argument(..., help="entity_candidates id (8-char ok).")) -> None:
    """Reject a proposed candidate (e.g. an over-merge like NLP→deep learning)."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    row = conn.execute("SELECT id FROM entity_candidates WHERE id=? OR id LIKE ?",
                       (candidate_id, candidate_id + "%")).fetchone()
    if not row:
        typer.echo(f"no candidate matching {candidate_id}")
        raise typer.Exit(code=1)
    ec.reject(conn, row["id"])
    typer.echo(f"rejected {row['id'][:8]}")
    conn.close()


@app.command("entity-taxonomy")
def entity_taxonomy() -> None:
    """Component 2 (#4, heavy half): seed the canonical sub-topic vocabulary over every unlinked
    series. Each DISTINCT concept becomes its own entity (over-merge structurally impossible);
    only true cross-source/cross-pillar variants of the same concept fold. The payoff printed is
    the cross-pillar TRACE — a constraint followed across the value layers. $0, stdlib."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    ec.seed_taxonomy(conn, log=typer.echo)
    conn.close()


@app.command("entity-supplier-edges")
def entity_supplier_edges() -> None:
    """Component 2 (#4, dependency half): seed the curated entity↔entity SUPPLIER edges — the supply
    structure between entities so a constraint can be traced one hop up/downstream. Each is a known
    real-world supplier relation, GIGO-rationaled (not a hallucinated chain); LLM 10-K extraction can
    propose more at scale under the same human-verify gate. $0."""
    from engine import entity_candidates as ec
    conn = db.connect()
    db.init_db(conn)
    ec.seed_supplier_edges(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-seed")
def hypothesis_seed() -> None:
    """Component 8: run the oracle pass — divergent, cross-domain constraint-migration hypotheses.

    Each is generated in-session through a Bucket-2 lens, then FORCED through the same gate a forecast
    obeys (outside-view base rate, disconfirmer-first, kill-criteria, projectibility). The gate verdict
    — survived / parked / killed — falls out. The seer proposes; the cold machine disposes. $0.
    """
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.seed(conn, log=typer.echo)
    conn.close()
    typer.echo(f"\ndone — {out['generated']} generated: {out['survived']} survived, "
               f"{out['parked']} parked, {out['killed']} killed. cost: $0.00")


@app.command("hypothesis-list")
def hypothesis_list() -> None:
    """Show generated hypotheses by verdict (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    hypothesis.list_hypotheses(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-skeptic")
def hypothesis_skeptic(
    hypothesis_id: str = typer.Argument(..., help="The hypothesis to test (8-char id ok)."),
    votes: str = typer.Option(..., help="JSON list of INDEPENDENT skeptic votes: "
                              '[{"skeptic","refuted","reason","confidence"}]. A strict majority to '
                              "refute kills the thesis (§2.6). May be a @path to a JSON file."),
) -> None:
    """Component 9: fold an independent multi-skeptic panel onto a hypothesis (majority-refute → re-gate).

    The skeptics are run by Claude in-session (real, independent adversarial passes — each asked only
    to REFUTE, blind to the others); this records their votes and recomputes the gate verdict. A single
    in-session refutation can fool itself; a blind majority cannot as easily.
    """
    import json as _json
    raw = open(votes[1:], encoding="utf-8").read() if votes.startswith("@") else votes
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.record_skeptic_panel(conn, hypothesis_id, _json.loads(raw), log=typer.echo)
    conn.close()
    typer.echo(f"\npanel recorded: {out['n_refute']}/{out['n_skeptics']} refute → {out['status']}. $0.00")


@app.command("hypothesis-add")
def hypothesis_add(
    title: str = typer.Option(..., help="One-line thesis name."),
    lens: str = typer.Option(..., help=f"Bucket-2 lens: {', '.join(hypothesis.LENSES)}."),
    seed: str = typer.Option(..., help="The divergent spark (analogy / inversion / 'what must be true')."),
    claim: str = typer.Option(..., help="The constraint-migration thesis — where rent moves."),
    inelastic: str = typer.Option(..., "--inelastic", help="The non-obvious binding constraint (where rent lands)."),
    obvious: str = typer.Option(..., "--obvious", help="The obvious-but-wrong endpoint everyone prices."),
    ref_class: str = typer.Option(..., "--ref-class", help="The outside-view reference class (doctrine §2.1)."),
    disconfirmer: str = typer.Option(..., help="The strongest case AGAINST, sought FIRST (required, §2.6)."),
    refutation: str = typer.Option(..., help="The in-session adversarial verdict — why it survives/dies."),
    refuted: bool = typer.Option(False, help="Did the disconfirmer win? (→ killed)"),
    measurable: bool = typer.Option(False, help="Is there a point-in-time series that could test it? (§0.5)"),
    base_rate: float = typer.Option(None, help="The reference class's hit rate (the outside-view anchor)."),
    horizon: str = typer.Option(None, help="Rough resolution horizon (YYYY-MM-DD)."),
    kill: list[str] = typer.Option([], "--kill", help="A kill-criterion with a date (repeat)."),
    thesis_kind: str = typer.Option(None, "--thesis-kind",
        help=f"The SHAPE of the structural call: {', '.join(hypothesis.THESIS_KINDS)}."),
    mispricing_kind: str = typer.Option(None, "--mispricing-kind",
        help=f"WHY consensus is wrong: {', '.join(hypothesis.MISPRICING_KINDS)}."),
    horizon_years: int = typer.Option(None, "--horizon-years",
        help="Years until the structural claim binds (≤4 = harvestable; long+hot-narrative = hype-over-priced)."),
    note: str = typer.Option("", help="Optional note."),
) -> None:
    """Author one structural-foresight hypothesis in-session and run it through the gate.

    The output is a BIG falsifiable structural call (a sector/sub-sector/macro reorganization), not a
    stock pick: 'consensus believes X; I predict Y; resolved by [dated structural metric]'. The
    inelastic-layer decomposition is the MECHANISM, not the deliverable. Tag --thesis-kind /
    --mispricing-kind so the call feeds the measured base-rate-by-kind (`base-rates`)."""
    conn = db.connect()
    db.init_db(conn)
    h = hypothesis.add(
        conn, title=title, lens=lens, seed=seed, claim=claim, inelastic_layer=inelastic,
        obvious_layer=obvious, reference_class=ref_class, base_rate=base_rate,
        disconfirmer=disconfirmer, kill_criteria=list(kill),
        horizon=date.fromisoformat(horizon) if horizon else None,
        measurable=measurable, refuted=refuted, refutation=refutation,
        thesis_kind=thesis_kind, mispricing_kind=mispricing_kind, horizon_years=horizon_years,
        note=note,
    )
    conn.close()
    typer.echo(f"{h.title}\n→ gate verdict: {h.status.upper()}")


@app.command("base-rates")
def base_rates() -> None:
    """The closed loop: measured hit rate + Brier of each KIND of structural call.

    Combines the §8 retrodiction corpus (known outcomes, tagged by kind → non-empty now) with any
    resolved live cards. This is the outside view EARNED from our own record, not a typed-in prior —
    the thing no analyst has: not a pick, but a base rate of which kinds of where-rent-migrates calls pay."""
    conn = db.connect()
    db.init_db(conn)
    hypothesis.base_rates(conn, log=typer.echo)
    conn.close()


@app.command("hypothesis-promote")
def hypothesis_promote(
    hypothesis_id: str = typer.Argument(..., help="The SURVIVED hypothesis to promote (8-char ok)."),
    question: str = typer.Option(..., help="The binary, point-in-time forecast question."),
    prob: float = typer.Option(..., help="P of the binary resolving true (0..1)."),
    resolution_date: str = typer.Option(..., help="ISO date when we'll know (YYYY-MM-DD)."),
    ci_low: float = typer.Option(None), ci_high: float = typer.Option(None),
    ci_unit: str = typer.Option(None), seed_series: str = typer.Option(None),
    pillar: list[int] = typer.Option([], "--pillar"),
    source: list[str] = typer.Option([], "--source"),
) -> None:
    """Graduate a SURVIVED hypothesis into an immutable ForecastCard (rule 7). Refuses parked/killed."""
    conn = db.connect()
    db.init_db(conn)
    out = hypothesis.promote(
        conn, hypothesis_id, question=question, probability=prob,
        resolution_date=date.fromisoformat(resolution_date), ci_low=ci_low, ci_high=ci_high,
        ci_unit=ci_unit, seed_series_id=seed_series, pillars_used=list(pillar),
        source_ids=list(source), log=typer.echo,
    )
    conn.close()
    typer.echo(f"forecast {out['forecast_id']}")


@app.command("decision-open")
def decision_open(
    prompt: str = typer.Option(..., help="The pivotal fork, stated concisely (rule 4)."),
    option: list[str] = typer.Option(..., "--option", help="An option (repeat for each)."),
    rec: str = typer.Option(None, help="The recommended option + why (≤1 line)."),
    blocks: str = typer.Option(None, help="What is paused until this resolves."),
) -> None:
    """Component 14: log a pivotal steering fork → it surfaces in the cockpit's Decisions panel."""
    conn = db.connect()
    db.init_db(conn)
    d = decisions.open_decision(conn, prompt=prompt, options=list(option), recommendation=rec,
                                blocks=blocks, log=typer.echo)
    conn.close()
    typer.echo(f"decision {d.id}")


@app.command("decision-resolve")
def decision_resolve(
    decision_id: str = typer.Argument(..., help="Decision id (8-char ok)."),
    choice: str = typer.Argument(..., help="The chosen option (verbatim, 1-based index, or free text)."),
) -> None:
    """Component 14: stamp the human's choice onto an open decision (closes the fork)."""
    conn = db.connect()
    db.init_db(conn)
    out = decisions.resolve_decision(conn, decision_id, choice, log=typer.echo)
    conn.close()
    typer.echo(f"resolved {out['id'][:8]} → {out['chosen']}")


@app.command("decision-list")
def decision_list(open_only: bool = typer.Option(False, "--open", help="Only show open decisions.")) -> None:
    """Component 14: the steering log (the cockpit #decisions panel is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    decisions.list_decisions(conn, only_open=open_only, log=typer.echo)
    conn.close()


@app.command("world-seed")
def world_seed_cmd() -> None:
    """Mint/refresh the unifying chain='world' spine graph from existing data ($0, idempotent)."""
    conn = db.connect()
    db.init_db(conn)
    world_seed.seed_world(conn, log=typer.echo)
    conn.close()


@app.command("world-coverage")
def world_coverage_cmd(
    topic: str = typer.Argument(..., help="A topic or distilled question to score coverage for."),
) -> None:
    """Coverage critic: which spine layers the world graph covers for a topic, and which are blank."""
    conn = db.connect()
    db.init_db(conn)
    cov = world_seed.coverage(conn, topic)
    conn.close()
    typer.echo(world_seed.format_coverage(cov))


@app.command("world-grade")
def world_grade_cmd(
    topic: str = typer.Argument(None, help="Optional topic — also prints its spine-coverage walk."),
    as_json: bool = typer.Option(False, "--json", help="Emit the grade scorecard as JSON."),
) -> None:
    """The substrate-wide grade of completion per spine layer (where we are rich vs blind)."""
    conn = db.connect()
    db.init_db(conn)
    g = coverage_grade.layer_grades(conn)
    cov = world_seed.coverage(conn, topic) if topic else None
    conn.close()
    if as_json:
        import json as _json
        typer.echo(_json.dumps({"grade": g, "coverage": cov}, indent=2))
        return
    typer.echo(coverage_grade.format_grades(g))
    if cov:
        typer.echo("")
        typer.echo(world_seed.format_coverage(cov))


_DATA_QUERY_VERBS = ("grade", "coverage", "signals", "depend", "entities", "market")


@app.command("data-query")
def data_query_cmd(
    verb: str = typer.Argument(..., help="One of: grade | coverage | signals | depend | entities | market"),
    topic: str = typer.Argument(None, help="The topic / distilled question (omit only for bare `grade`)."),
) -> None:
    """Agentic data seam: call ONE read primitive over the substrate, loop as your reasoning needs it.

    Walk it like a tool, not a dump: start at `grade` (where is the substrate rich vs blind), `coverage`
    (which spine layers light up for the topic), `depend` (walk citations to the inelastic input — the
    needle), `signals` (the dated base rate), `entities` (who actually holds/operates it), `market`
    (is it already priced?). Each verb is cheap and keyless; chain them instead of reading one static pack.
    """
    verb = verb.lower().strip()
    if verb not in _DATA_QUERY_VERBS:
        typer.echo(f"unknown verb '{verb}'. choose: {', '.join(_DATA_QUERY_VERBS)}")
        raise typer.Exit(1)
    if verb != "grade" and not topic:
        typer.echo(f"verb '{verb}' needs a topic, e.g. data-query {verb} \"rare earth magnets\"")
        raise typer.Exit(1)

    conn = db.connect()
    db.init_db(conn)
    try:
        if verb == "grade":
            typer.echo(coverage_grade.format_grades(coverage_grade.layer_grades(conn)))
            if topic:
                typer.echo("")
                typer.echo(world_seed.format_coverage(world_seed.coverage(conn, topic)))
        elif verb == "coverage":
            typer.echo(world_seed.format_coverage(world_seed.coverage(conn, topic)))
        elif verb == "signals":
            typer.echo(signals.format_pack(signals.evidence_pack(topic)))
        elif verb == "depend":
            dep = signals.dependency_neighbors(conn, topic)
            if not dep:
                typer.echo(f"DEPENDENCY WALK '{topic}' — no concept_flow match (data layer blind here).")
            else:
                typer.echo(f"DEPENDENCY WALK '{topic}' — walk a mid-weight draws_on with heavy inbound "
                           f"load to the inelastic input (the needle, not the curve):")
                for d in dep:
                    draws = ", ".join(x["name"] for x in d["draws_on"][:4]) or "—"
                    used_by = ", ".join(x["name"] for x in d["drawn_on_by"][:4]) or "—"
                    pr = (d.get("patent_reliance") or {}).get("n_patents")
                    prs = f"  [{pr:,} patents cite it]" if pr else ""
                    typer.echo(f"  • {d['concept']}{prs}\n      draws_on: {draws}\n      used_by:  {used_by}")
        elif verb == "entities":
            typer.echo(signals.format_entities(signals.match_entities(conn, topic)))
        elif verb == "market":
            try:
                anchor = market.market_anchor(topic)
            except Exception as exc:
                anchor = {"query": topic, "markets": [], "verdict": "UNPRICED-UNSEEN",
                          "error": f"{type(exc).__name__}: {exc}"}
            typer.echo(market.format_anchor(anchor))
    finally:
        conn.close()


@app.command("data-showcase")
def data_showcase_cmd(
    out: str = typer.Option("site/public/data/coverage.json", "--out", help="Where to write the JSON."),
    full: bool = typer.Option(False, "--full", help="Write the full per-layer depth payload (gated/internal) instead of the public teaser."),
) -> None:
    """Export the data-coverage showcase JSON: public teaser (scale + breadth + reach over time, no
    grade) for the open site, or --full per-layer depth for the gated research tier."""
    import json as _json
    from pathlib import Path
    conn = db.connect()
    db.init_db(conn)
    payload = coverage_grade.showcase_payload(conn)
    conn.close()
    payload = payload if full else coverage_grade.public_teaser(payload)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(payload, indent=2, default=str))
    t = payload["totals"]
    typer.echo(f"wrote {'FULL' if full else 'public teaser'} → {p}")
    typer.echo(f"  {t['papers']:,} papers · {t['observations']:,} observations · {t['series']:,} series "
               f"· {t['entities']:,} entities · {t['sources']} sources / {t['providers']} providers")


@app.command("status")
def status() -> None:
    """Quick text view of the foundation state (the cockpit is the real view)."""
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute("SELECT ord, name, status FROM pillars ORDER BY ord").fetchall()
    spend = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(actual_cost_cents, est_cost_cents)), 0) FROM cost_ledger"
    ).fetchone()[0]
    conn.close()
    typer.echo("Pillars (data-flow layers):")
    for r in rows:
        typer.echo(f"  {r['ord']}. {r['name']:<18} [{r['status']}]")
    typer.echo(f"Spend to date: ${spend / 100:.2f}")


@app.command("capture-run")
def capture_run(slug: str = "minerals-barter", top_n: int = 5) -> None:
    """Capture engine dry-run: discover -> qualify -> synth top-N plays. Nothing sends.

    Writes data/capture/<slug>/ (targets.json, plays.json, review.md). Read review.md to rate."""
    from engine.capture import run as cap
    out = cap.run_play(slug, top_n=top_n)
    typer.echo(f"discovered {out['discovered']} targets, built {out['plays']} plays")
    typer.echo(f"review: {out['dir']}/review.md")


@app.command("capture-resynth")
def capture_resynth(slug: str, index: int, note: str) -> None:
    """Re-draft ONE play (by index) with a revision note folded in, then rewrite review.md."""
    from engine.capture import run as cap
    p = cap.resynth(slug, index, note)
    typer.echo(f"resynthed play {index} for {p.target.name}; review.md updated")


@app.command("capture-replies")
def capture_replies(slug: str, limit: int = 30) -> None:
    """OWNER-ONLY. Read recent replies from YOUR Stalwart inbox (JMAP, read-only), match them to
    drafted plays, and queue the next move as a DRAFT. Sends nothing. Not a chat/agent tool."""
    from engine.capture import inbox
    out = inbox.process_replies(slug, limit=limit)
    typer.echo(f"scanned {out['scanned']} messages, matched {out['matched']} to plays")
    typer.echo(f"draft next-moves: {out['file']}")


if __name__ == "__main__":
    app()

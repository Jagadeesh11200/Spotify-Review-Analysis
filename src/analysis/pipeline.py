from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

from src.analysis.aggregation import aggregate_analysis
from src.analysis.dashboard_insights import default_dashboard_insights, generate_dashboard_insights
from src.analysis.gemini_client import DEFAULT_GEMINI_MODEL, GeminiClient, GeminiLike, extract_records_with_gemini
from src.analysis.reporting import render_markdown_report
from src.analysis.session_loader import load_session_manifest, load_usable_records
from src.config import AppSettings


ANALYSIS_CACHE_VERSION = "phase2_controlled_freshness_v1"


def run_review_analysis(
    settings: AppSettings,
    session_dir: str | Path,
    output_base_dir: str | Path = "data/analysis",
    gemini: GeminiLike | None = None,
    batch_size: int = 20,
    max_workers: int = 2,
    use_cache: bool = True,
) -> dict[str, Any]:
    records = load_usable_records(session_dir)
    if not records:
        raise ValueError("No usable records found for analysis. Run ingestion first.")
    source_manifest = load_session_manifest(session_dir)
    cached = load_cached_analysis(session_dir, output_base_dir) if use_cache else None
    if cached:
        return cached
    if gemini is None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        gemini = GeminiClient(api_key=settings.gemini_api_key, model=DEFAULT_GEMINI_MODEL)

    extractions, errors = extract_records_with_gemini(records, gemini=gemini, batch_size=batch_size, max_workers=max_workers)
    aggregate = aggregate_analysis(extractions)
    dashboard_insights, insight_errors = generate_dashboard_insights(aggregate, gemini)
    errors.extend(insight_errors)
    markdown = render_markdown_report(aggregate)
    paths = save_analysis_outputs(session_dir, output_base_dir, records, extractions, aggregate, markdown, errors, source_manifest, dashboard_insights)
    return {
        "records": records,
        "extractions": extractions,
        "aggregate": aggregate,
        "markdown": markdown,
        "errors": errors,
        "paths": paths,
        "source_manifest": source_manifest,
        "dashboard_insights": dashboard_insights,
    }


def load_cached_analysis(session_dir: str | Path, output_base_dir: str | Path) -> dict[str, Any] | None:
    session_path = Path(session_dir)
    output_dir = Path(output_base_dir) / session_path.name
    extraction_path = output_dir / "extractions.json"
    aggregate_path = output_dir / "analysis.json"
    report_path = output_dir / "report.md"
    if not extraction_path.exists():
        return None
    extraction_payload = json.loads(extraction_path.read_text(encoding="utf-8"))
    if extraction_payload.get("analysis_cache_version") != ANALYSIS_CACHE_VERSION:
        return None
    extractions = extraction_payload.get("extractions", [])
    if not isinstance(extractions, list):
        return None
    errors = extraction_payload.get("errors", [])
    dashboard_insights = extraction_payload.get("dashboard_insights")
    if not isinstance(dashboard_insights, dict):
        dashboard_insights = default_dashboard_insights()
    aggregate = aggregate_analysis(extractions)
    markdown = render_markdown_report(aggregate)
    source_manifest = load_session_manifest(session_dir)
    try:
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        if not aggregate_path.exists():
            aggregate_path.write_text(
                json.dumps(
                    {
                        "analysis_cache_version": ANALYSIS_CACHE_VERSION,
                        "source_session": str(session_path),
                        "source_manifest": source_manifest,
                        "aggregate": aggregate,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        if not report_path.exists():
            report_path.write_text(markdown, encoding="utf-8")
    except OSError:
        pass
    return {
        "records": load_usable_records(session_dir),
        "extractions": extractions,
        "aggregate": aggregate,
        "markdown": markdown,
        "errors": errors if isinstance(errors, list) else [],
        "paths": {"extractions": str(extraction_path), "analysis": str(aggregate_path), "report": str(report_path)},
        "source_manifest": source_manifest,
        "dashboard_insights": dashboard_insights,
        "cached": True,
    }


def save_analysis_outputs(
    session_dir: str | Path,
    output_base_dir: str | Path,
    records: list[dict[str, Any]],
    extractions: list[dict[str, Any]],
    aggregate: dict[str, Any],
    markdown: str,
    errors: list[str],
    source_manifest: dict[str, Any] | None = None,
    dashboard_insights: dict[str, str] | None = None,
) -> dict[str, str]:
    session_path = Path(session_dir)
    output_dir = Path(output_base_dir) / session_path.name
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    extraction_path = output_dir / "extractions.json"
    aggregate_path = output_dir / "analysis.json"
    report_path = output_dir / "report.md"

    extraction_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "analysis_cache_version": ANALYSIS_CACHE_VERSION,
                "source_session": str(session_path),
                "source_manifest": source_manifest or {},
                "records_analyzed": len(records),
                "errors": errors,
                "dashboard_insights": dashboard_insights or default_dashboard_insights(),
                "extractions": extractions,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    aggregate_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "analysis_cache_version": ANALYSIS_CACHE_VERSION,
                "source_session": str(session_path),
                "source_manifest": source_manifest or {},
                "aggregate": aggregate,
                "dashboard_insights": dashboard_insights or default_dashboard_insights(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path.write_text(markdown, encoding="utf-8")

    return {"extractions": str(extraction_path), "analysis": str(aggregate_path), "report": str(report_path)}

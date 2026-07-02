from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Protocol

from google import genai
from google.genai import types

from src.analysis.prompts import SYSTEM_INSTRUCTION
from src.analysis.question_prompts import QUESTION_KEYS, build_question_prompt


DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class GeminiLike(Protocol):
    def generate_json(self, prompt: str) -> dict[str, Any]:
        ...


class GeminiExtractionError(RuntimeError):
    pass


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        max_retries: int = 3,
        retry_delay_seconds: float = 4.0,
    ) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def generate_json(self, prompt: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=24000,
                    ),
                )
                return parse_json_response(response.text or "")
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_seconds * (attempt + 1))
        raise GeminiExtractionError(f"Gemini request failed after retries: {last_error}")


def parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise GeminiExtractionError("Gemini returned an empty response.")
    match = JSON_BLOCK_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GeminiExtractionError(f"Could not parse Gemini JSON: {exc}") from exc


def extract_records_with_gemini(
    records: list[dict[str, Any]],
    gemini: GeminiLike,
    batch_size: int = 10,
    max_workers: int = 2,
) -> tuple[list[dict[str, Any]], list[str]]:
    extractions_by_id = {str(record["record_id"]): fallback_extraction(record, "pending_question_passes") for record in records}
    errors: list[str] = []

    worker_count = max(1, min(max_workers, len(QUESTION_KEYS)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(run_question_pass, records, gemini, question_key, batch_size): question_key for question_key in QUESTION_KEYS}
        for future in as_completed(futures):
            partials, question_errors = future.result()
            errors.extend(question_errors)
            question_key = futures[future]
            for partial in partials:
                record_id = str(partial.get("record_id"))
                if record_id in extractions_by_id:
                    merge_question_partial(extractions_by_id[record_id], partial, question_key)

    return [finalize_merged_extraction(extractions_by_id[str(record["record_id"])]) for record in records], errors


def run_question_pass(
    records: list[dict[str, Any]],
    gemini: GeminiLike,
    question_key: str,
    batch_size: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    partials: list[dict[str, Any]] = []
    errors: list[str] = []
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        try:
            payload = gemini.generate_json(build_question_prompt(question_key, batch))
            partials.extend(normalize_question_payload(payload, batch))
        except Exception as exc:
            errors.append(f"{question_key} batch {start // batch_size + 1}: {exc}")
            if len(batch) == 1:
                partials.append({"record_id": batch[0]["record_id"], f"{question_key}_confidence": 0.0, "extraction_error": str(exc)})
                continue
            for record in batch:
                try:
                    payload = gemini.generate_json(build_question_prompt(question_key, [record]))
                    partials.extend(normalize_question_payload(payload, [record]))
                except Exception as single_exc:
                    errors.append(f"{question_key} record {record.get('record_id')}: {single_exc}")
                    partials.append({"record_id": record["record_id"], f"{question_key}_confidence": 0.0, "extraction_error": str(single_exc)})
    return partials, errors


def normalize_question_payload(payload: dict[str, Any], batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = payload.get("analyses")
    if not isinstance(values, list):
        raise GeminiExtractionError("Gemini JSON did not contain an 'analyses' list.")

    by_id = {str(item.get("record_id")): item for item in values if isinstance(item, dict)}
    normalized: list[dict[str, Any]] = []
    for record in batch:
        record_id = str(record["record_id"])
        item = by_id.get(record_id)
        if item is None:
            normalized.append({"record_id": record_id, "extraction_error": "missing_from_gemini_response"})
            continue
        normalized.append(dict(item))
    return normalized


def fallback_extraction(record: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "source": record.get("source"),
        "source_query": record.get("source_query"),
        "word_count": record.get("word_count"),
        "specificity_score": record.get("specificity_score", 0.0),
        "engagement_score": record.get("engagement_score", 0.0),
        "conversation_score": record.get("conversation_score", 0.0),
        "signal_weight": record.get("signal_weight", 1.0),
        "source_metadata": record.get("metadata", {}),
        "quality_for_analysis": False,
        "primary_barrier_type": "unclear",
        "primary_discovery_barrier": "unclear",
        "novelty_safety_state": "unclear",
        "barrier_evidence_quote": "",
        "secondary_barrier_type": "unclear",
        "discovery_failure_modes": [],
        "named_features": [],
        "frustrations": [],
        "recommendation_frustration_themes": [],
        "activity_context": "unclear",
        "discovery_mode": "unclear",
        "user_goals": [],
        "effort_tolerance": "unclear",
        "desired_outcome": "",
        "intent_evidence_quote": "",
        "repetition_type": "unclear",
        "repetition_drivers": [],
        "repetition_intentional": False,
        "desire_to_change_repetition": False,
        "repetition_evidence_quote": "",
        "segment_scores": {},
        "segment_evidence": {},
        "top_segment": "unclassified",
        "segment_confidence_gap": 0.0,
        "listening_intensity": "low",
        "intensity_evidence_quote": "",
        "subscription_signal": "unknown",
        "subscription_evidence_quote": "",
        "churn_risk": False,
        "churn_signal_type": "none",
        "churn_evidence_quote": "",
        "workarounds": [],
        "competitive_displacements": [],
        "resignation_signals": [],
        "unmet_need_tags": [],
        "opportunity_area": "unclear",
        "overall_severity": 1,
        "ongoing_vs_resolved": "unclear",
        "best_verbatim_quote": "",
        "extraction_confidence": 0.0,
        "extraction_error": reason,
    }


def merge_question_partial(base: dict[str, Any], partial: dict[str, Any], question_key: str) -> None:
    base.pop("extraction_error", None)
    base["quality_for_analysis"] = True
    base[f"{question_key}_confidence"] = clamp_float(partial.get(f"{question_key}_confidence"), 0.0, 1.0, 0.0)

    fields_by_question = {
        "q1": ["primary_barrier_type", "primary_discovery_barrier", "novelty_safety_state", "barrier_evidence_quote", "secondary_barrier_type", "discovery_failure_modes", "named_features"],
        "q2": ["frustrations", "recommendation_frustration_themes", "overall_severity", "ongoing_vs_resolved", "best_verbatim_quote"],
        "q3": ["activity_context", "discovery_mode", "user_goals", "effort_tolerance", "desired_outcome", "intent_evidence_quote"],
        "q4": ["repetition_type", "repetition_drivers", "repetition_intentional", "desire_to_change_repetition", "repetition_evidence_quote"],
        "q5": ["segment_scores", "segment_evidence", "top_segment", "segment_confidence_gap", "listening_intensity", "intensity_evidence_quote", "subscription_signal", "subscription_evidence_quote", "churn_risk", "churn_signal_type", "churn_evidence_quote"],
        "q6": ["workarounds", "competitive_displacements", "resignation_signals", "unmet_need_tags", "opportunity_area"],
    }
    for field in fields_by_question[question_key]:
        if field in partial:
            base[field] = partial[field]


def finalize_merged_extraction(item: dict[str, Any]) -> dict[str, Any]:
    question_confidences = [
        clamp_float(item.get(f"{question_key}_confidence"), 0.0, 1.0, 0.0)
        for question_key in QUESTION_KEYS
    ]
    if any(confidence > 0 for confidence in question_confidences):
        item["extraction_confidence"] = round(sum(question_confidences) / len(question_confidences), 3)
    else:
        item["quality_for_analysis"] = False
        item["extraction_confidence"] = 0.0
    return coerce_extraction(item, item)


def coerce_extraction(item: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    item["record_id"] = str(item.get("record_id") or record["record_id"])
    item["source"] = str(item.get("source") or record.get("source") or "unknown")
    item["signal_weight"] = clamp_float(item.get("signal_weight"), 1.0, 3.0, 1.0)
    item["specificity_score"] = clamp_float(item.get("specificity_score"), 0.0, 1.0, 0.0)
    item["engagement_score"] = clamp_float(item.get("engagement_score"), 0.0, 1.0, 0.0)
    item["conversation_score"] = clamp_float(item.get("conversation_score"), 0.0, 1.0, 0.0)
    item["frustrations"] = item.get("frustrations") if isinstance(item.get("frustrations"), list) else []
    item["named_features"] = item.get("named_features") if isinstance(item.get("named_features"), list) else []
    item["discovery_failure_modes"] = item.get("discovery_failure_modes") if isinstance(item.get("discovery_failure_modes"), list) else []
    item["recommendation_frustration_themes"] = item.get("recommendation_frustration_themes") if isinstance(item.get("recommendation_frustration_themes"), list) else []
    item["user_goals"] = item.get("user_goals") if isinstance(item.get("user_goals"), list) else []
    item["repetition_drivers"] = item.get("repetition_drivers") if isinstance(item.get("repetition_drivers"), list) else []
    item["workarounds"] = item.get("workarounds") if isinstance(item.get("workarounds"), list) else []
    item["competitive_displacements"] = item.get("competitive_displacements") if isinstance(item.get("competitive_displacements"), list) else []
    item["resignation_signals"] = item.get("resignation_signals") if isinstance(item.get("resignation_signals"), list) else []
    item["unmet_need_tags"] = item.get("unmet_need_tags") if isinstance(item.get("unmet_need_tags"), list) else []
    item["overall_severity"] = clamp_int(item.get("overall_severity"), 1, 5, 1)
    item["extraction_confidence"] = clamp_float(item.get("extraction_confidence"), 0.0, 1.0, 0.0)
    item["segment_confidence_gap"] = clamp_float(item.get("segment_confidence_gap"), 0.0, 1.0, 0.0)
    if item.get("listening_intensity") not in {"high", "medium", "low"}:
        item["listening_intensity"] = "low"
    if item.get("subscription_signal") not in {"premium", "free", "unknown"}:
        item["subscription_signal"] = "unknown"
    if item.get("churn_signal_type") not in {"none", "disengagement", "switching", "exit_intent", "cancelled"}:
        item["churn_signal_type"] = "none"
    item["churn_risk"] = bool(item.get("churn_risk"))
    return item


def clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def clamp_float(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))

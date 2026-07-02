from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import httpx


APIFY_RETRY_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}
APIFY_KEY_FALLBACK_STATUSES = {401, 402, 403, 429}


class ApifyError(RuntimeError):
    pass


def is_apify_hard_limit_error(error: object) -> bool:
    text = str(error).lower()
    return "platform-feature-disabled" in text or "monthly usage hard limit exceeded" in text


@dataclass
class ApifyClient:
    api_keys: list[str]
    base_url: str = "https://api.apify.com/v2"
    timeout: float = 180.0
    max_retries_per_key: int = 1
    retry_delay_seconds: float = 4.0
    client: httpx.Client | None = None

    def run_actor_items(
        self,
        actor_id: str,
        actor_input: dict[str, Any],
        *,
        limit: int,
        timeout_seconds: int = 180,
        max_items: int | None = None,
        max_total_charge_usd: float | None = None,
    ) -> list[dict[str, Any]]:
        if not self.api_keys:
            raise ApifyError("No Apify API keys configured.")

        path_actor_id = actor_id.replace("/", "~")
        errors: list[str] = []
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            for index, api_key in enumerate(self.api_keys, start=1):
                for attempt in range(self.max_retries_per_key + 1):
                    try:
                        response = client.post(
                            f"{self.base_url}/acts/{path_actor_id}/run-sync-get-dataset-items",
                            params={
                                "token": api_key,
                                "format": "json",
                                "clean": "true",
                                "limit": max(1, limit),
                                "timeout": timeout_seconds,
                                **({"maxItems": max_items} if max_items is not None else {}),
                                **({"maxTotalChargeUsd": max_total_charge_usd} if max_total_charge_usd is not None else {}),
                            },
                            json=actor_input,
                            headers={"Content-Type": "application/json", "Accept": "application/json"},
                        )
                    except httpx.HTTPError as exc:
                        errors.append(f"key_{index} attempt_{attempt + 1}: {exc}")
                        if attempt < self.max_retries_per_key:
                            self._sleep(attempt)
                            continue
                        break

                    if response.status_code < 400:
                        return self._parse_items(response)

                    message = f"key_{index} attempt_{attempt + 1}: HTTP {response.status_code} {response.text[:200]}"
                    errors.append(message)
                    if response.status_code in APIFY_RETRY_STATUSES and attempt < self.max_retries_per_key:
                        self._sleep(attempt)
                        continue
                    if response.status_code in APIFY_KEY_FALLBACK_STATUSES:
                        break
                    raise ApifyError(f"Apify actor {actor_id} failed: {message}")
        finally:
            if owns_client:
                client.close()

        raise ApifyError(f"All Apify keys failed for actor {actor_id}: " + "; ".join(errors))

    def _parse_items(self, response: httpx.Response) -> list[dict[str, Any]]:
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _sleep(self, attempt: int) -> None:
        if self.retry_delay_seconds <= 0:
            return
        time.sleep(self.retry_delay_seconds * (attempt + 1))

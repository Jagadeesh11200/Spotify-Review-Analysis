from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


COLLECT_PAGE = "Collect & Analyze"
DASHBOARD_PAGE = "Dashboard"
PAGE_OPTIONS = [COLLECT_PAGE, DASHBOARD_PAGE]
PAGE_STATE_KEY = "app_page"
NEXT_PAGE_KEY = "_next_app_page"


def prepare_page_state(state: MutableMapping[str, Any]) -> None:
    next_page = state.pop(NEXT_PAGE_KEY, None)
    if next_page in PAGE_OPTIONS:
        state[PAGE_STATE_KEY] = next_page
    elif state.get(PAGE_STATE_KEY) not in PAGE_OPTIONS:
        state[PAGE_STATE_KEY] = COLLECT_PAGE


def request_page_navigation(state: MutableMapping[str, Any], page: str) -> None:
    if page not in PAGE_OPTIONS:
        raise ValueError(f"Unknown page: {page}")
    state[NEXT_PAGE_KEY] = page

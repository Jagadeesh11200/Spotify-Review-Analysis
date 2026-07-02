import pytest

from src.ui_navigation import COLLECT_PAGE, DASHBOARD_PAGE, NEXT_PAGE_KEY, PAGE_STATE_KEY, prepare_page_state, request_page_navigation


def test_prepare_page_state_defaults_to_collect_page():
    state = {}

    prepare_page_state(state)

    assert state[PAGE_STATE_KEY] == COLLECT_PAGE


def test_requested_navigation_is_applied_on_next_prepare():
    state = {PAGE_STATE_KEY: COLLECT_PAGE}

    request_page_navigation(state, DASHBOARD_PAGE)
    assert state[NEXT_PAGE_KEY] == DASHBOARD_PAGE

    prepare_page_state(state)

    assert state[PAGE_STATE_KEY] == DASHBOARD_PAGE
    assert NEXT_PAGE_KEY not in state


def test_request_page_navigation_rejects_unknown_page():
    with pytest.raises(ValueError):
        request_page_navigation({}, "Bad Page")

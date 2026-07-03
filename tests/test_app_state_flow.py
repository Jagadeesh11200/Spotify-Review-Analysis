from types import SimpleNamespace

import app


def test_fresh_tool_request_clears_default_run_only_once(monkeypatch):
    state = {
        "app_page": app.COLLECT_PAGE,
        "current_ingestion_result": "default ingestion",
        "current_session_dir": "default raw dir",
        "analysis_result": "default analysis",
        "loaded_default_session_id": "session_default",
    }
    fake_streamlit = SimpleNamespace(query_params={"fresh_run": "1"}, session_state=state)
    monkeypatch.setattr(app, "st", fake_streamlit)

    app.apply_fresh_tool_request()

    assert state[app.FRESH_TOOL_KEY] is True
    assert "current_ingestion_result" not in state
    assert "analysis_result" not in state

    state["current_ingestion_result"] = "fresh ingestion"
    state["current_session_dir"] = "fresh raw dir"

    app.apply_fresh_tool_request()

    assert state["current_ingestion_result"] == "fresh ingestion"
    assert state["current_session_dir"] == "fresh raw dir"


def test_fresh_run_query_parser_accepts_streamlit_list_values():
    assert app.is_fresh_run_requested({"fresh_run": ["0", "1"]})
    assert app.is_fresh_run_requested({"fresh_run": "1"})
    assert not app.is_fresh_run_requested({"fresh_run": "0"})
    assert not app.is_fresh_run_requested({})

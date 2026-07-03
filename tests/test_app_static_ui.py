from pathlib import Path


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_default_target_record_input_allows_up_to_300_and_fresh_runs_cap_at_25():
    assert '"Target meaningful records / source"' in APP_SOURCE
    assert "DEFAULT_TARGET_RECORD_LIMIT = 300" in APP_SOURCE
    assert "FRESH_RUN_TARGET_RECORD_LIMIT = 25" in APP_SOURCE
    assert "target_record_limit = FRESH_RUN_TARGET_RECORD_LIMIT if st.session_state.get(FRESH_TOOL_KEY) else DEFAULT_TARGET_RECORD_LIMIT" in APP_SOURCE
    assert "max_value=target_record_limit" in APP_SOURCE
    assert "value=min(target_record_limit" in APP_SOURCE
    assert "The default loaded dashboard still uses the saved 300-record-per-source analysis." in APP_SOURCE


def test_dashboard_iframe_avoids_inner_scrollbars():
    assert "FULL_DASHBOARD_IFRAME_HEIGHT = 4800" in APP_SOURCE
    assert "height=FULL_DASHBOARD_IFRAME_HEIGHT" in APP_SOURCE
    assert "scrolling=False" in APP_SOURCE


def test_default_analysis_prompt_offers_blank_tool_link():
    assert "Executed analysis loaded by default" in APP_SOURCE
    assert "Start with the ready dashboard" in APP_SOURCE
    assert "?fresh_run=1" in APP_SOURCE
    assert "Open a blank tool and run Collect + Analyze" in APP_SOURCE
    assert "may use live API quota" in APP_SOURCE
    assert "default-analysis-layout" in APP_SOURCE
    assert "default-analysis-stat" in APP_SOURCE
    assert "font-size: 18px;" in APP_SOURCE
    assert "border-radius: 999px;" in APP_SOURCE
    assert "box-shadow: 0 5px 14px" in APP_SOURCE


def test_homepage_exposes_repository_reference():
    assert "repo-reference" in APP_SOURCE
    assert "Project repository" in APP_SOURCE
    assert "https://github.com/Jagadeesh11200/Spotify-Review-Analysis/" in APP_SOURCE
    assert "render_repo_reference()" in APP_SOURCE

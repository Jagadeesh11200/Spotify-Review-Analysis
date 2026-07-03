from pathlib import Path


WORKFLOW = Path(".github/workflows/streamlit-deploy-check.yml").read_text(encoding="utf-8")


def test_github_workflow_validates_streamlit_deployment_on_push():
    assert "on:" in WORKFLOW
    assert "push:" in WORKFLOW
    assert "pull_request:" in WORKFLOW
    assert "python-version: \"3.12\"" in WORKFLOW
    assert "pip install -r requirements.txt" in WORKFLOW
    assert "pip check" in WORKFLOW
    assert "python -m pytest -q" in WORKFLOW
    assert "streamlit run app.py" in WORKFLOW
    assert "http://localhost:8501/_stcore/health" in WORKFLOW


def test_github_workflow_checks_packaged_default_data():
    assert "data/default_session.json" in WORKFLOW
    assert "data/raw/session_20260622_145954/manifest.json" in WORKFLOW
    assert "data/analysis/session_20260622_145954/extractions.json" in WORKFLOW
    assert "ingestion.total_usable == 1500" in WORKFLOW

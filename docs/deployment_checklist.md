# Deployment Checklist

Use this checklist before publishing the Streamlit app.

## Runtime

- Python runtime: `python-3.12` from `runtime.txt`.
- Start command: `streamlit run app.py`.
- Install dependencies with `pip install -r requirements.txt`.

## Secrets

Do not commit `.env` or `.streamlit/secrets.toml`.

Required for fresh live runs:

- `GEMINI_API_KEY`
- `YOUTUBE_API_KEY`
- At least one Apify token, preferably `APIFY_API_KEY_1`

Supported Apify aliases:

- `APIFY_API_KEY_1` through `APIFY_API_KEY_4`
- `APIFY_KEY_0`, `APIFY_KEY_1`
- `APPIFY_KEY_0`, `APPIFY_KEY_1`
- `APIFY_API_TOKEN_1` through `APIFY_API_TOKEN_4`

The default loaded dashboard can open without live API secrets because the curated run is packaged with the app.

## Packaged Demo Data

The deployment must include:

- `data/default_session.json`
- `data/raw/session_20260622_145954/*.json`
- `data/analysis/session_20260622_145954/*.json`
- `data/analysis/session_20260622_145954/report.md`

Other generated sessions under `data/raw/session_*`, `data/analysis/session_*`, and `data/smoke/` are intentionally ignored.

## Validation Commands

```powershell
python -m py_compile app.py src\config.py src\analysis\pipeline.py src\default_session.py src\analysis\interactive_dashboard.py
python -m pytest -q
streamlit run app.py
```

For a headless smoke test, start Streamlit on a temporary port and confirm the root URL returns HTTP 200.

# Spotify Review Analysis

Demo Streamlit app for AI-powered analysis of Spotify user feedback about music discovery, recommendations, and repetitive listening behavior.

This repository currently contains Phase 1 live feedback ingestion and Phase 2 AI review analysis.

## Target Sources

- App Store reviews
- Google Play Store reviews
- Reddit discussions
- Spotify Community forum posts
- YouTube comments

For now, the product scope is English-language feedback only.

## Required Secrets

These values must never be committed. Use `.env` locally, `.streamlit/secrets.toml` locally for Streamlit, or the secrets manager in the deployment platform.

| Secret | Required For | Notes |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini 2.5 Pro analysis | Required. Can come from Google AI Studio or Google Cloud. |
| `APIFY_API_KEY_1` through `APIFY_API_KEY_4` | Reddit via Apify actor | At least one is required for Reddit. `APPIFY_KEY_0`, `APPIFY_KEY_1`, `APIFY_KEY_0`, `APIFY_KEY_1`, and `APIFY_API_TOKEN_1` through `APIFY_API_TOKEN_4` are also supported aliases. The app will try keys in order when a key is invalid, rate-limited, or out of credits. |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Required for live YouTube comment collection. |

## Sources That Usually Do Not Need Secrets

| Source | Credential Need |
| --- | --- |
| Google Play reviews | Usually no secret for public reviews when using `google-play-scraper`. |
| App Store reviews | Usually no secret for public review RSS/endpoints. |
| Spotify Community forum | No secret. The app tries public Khoros API v2 search first, then public HTML scraping with BeautifulSoup if API access is blocked. |

## Apify Notes

Reddit collection uses an Apify actor instead of the direct Reddit API. Create Apify API tokens and store them as `APIFY_API_KEY_1` through `APIFY_API_KEY_4`. Existing local names `APPIFY_KEY_0` and `APPIFY_KEY_1` are also supported.

Current actors:

- `trudax/reddit-scraper-lite`

Apify uses usage-based billing and actor-specific rate/runtime limits. For a demo, keep the meaningful target conservative until the expected query volume is clear. Multiple keys are used for controlled fallback and rotation, not to bypass rate limits.

## Optional Secrets / Settings

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Environment label such as `local`, `demo`, or `production`. |
| `DEFAULT_LOOKBACK_DAYS` | Default date window shown in the app. Defaults to `90`. |
| `MAX_ITEMS_PER_SOURCE` | Default meaningful-record target per source. The UI can override it for each run, as low as `5`. |
| `CANDIDATE_OVERFETCH_MULTIPLIER` | Internal candidate buffer multiplier used by the UI so post-filter meaningful records can land close to the target. Defaults to `2`. |
| `CANDIDATE_OVERFETCH_MAX` | Maximum internal candidate cap per source. Defaults to `2000`. |
| `CANDIDATE_ITEMS_PER_SOURCE` | Legacy lower-level candidate cap used when running ingestion directly. The Streamlit UI now derives its cap from the meaningful target. |
| `HTTP_PROXY`, `HTTPS_PROXY` | Optional network proxy settings if required by deployment/network. |

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run app.py
```

## Deployment Notes

- Do not upload `.env` or `.streamlit/secrets.toml`.
- Add all required secrets in the deployment platform.
- For Streamlit Community Cloud, add secrets in the app settings using the TOML keys from `.streamlit/secrets.toml.example`.
- For other platforms, set environment variables with the names shown in `.env.example`.
- Start command: `streamlit run app.py`.
- Python runtime: `python-3.12` from `runtime.txt`.
- The app ships with one curated default demo run: `data/default_session.json`, `data/raw/session_20260622_145954/`, and `data/analysis/session_20260622_145954/`.
- Fresh user-triggered runs write new generated files under `data/raw/session_*` and `data/analysis/session_*`. These generated runs are intentionally ignored by Git.
- The default dashboard can open without live API secrets. Fresh collection and analysis require the relevant source secrets listed above.

## GitHub Automation

The repository includes `.github/workflows/streamlit-deploy-check.yml`.

On every push or pull request to `main`, GitHub Actions:

- installs dependencies on Python 3.12,
- runs `pip check`,
- compiles deployment-critical modules,
- verifies the packaged default dashboard data,
- runs the full test suite,
- starts Streamlit headlessly and checks the health endpoint.

When the app is connected to Streamlit Community Cloud, pushes to the deployed branch trigger Streamlit's normal app update flow. The GitHub workflow is the deployment safety gate that catches broken code or missing packaged data before the deployed app is reviewed.

## Phase 1 Output

Each run creates a folder under `data/raw/session_YYYYMMDD_HHMMSS` with one JSON file per enabled source and a `manifest.json`. The Streamlit UI asks for a meaningful-record target per source, then over-collects candidates internally so the post-filter count can land within about 5% of that target when enough public feedback is available.

See `docs/phase1_ingestion_contract.md` for the quality gate, normalized fields, and future AI extraction schema.

## Phase 2 Output

After collection, click `Run analysis` to execute six separate Gemini question passes, merge the outputs, and display the review-analysis dashboard. The run also writes `extractions.json`, `analysis.json`, and `report.md` under `data/analysis/<session_id>/`.

See `docs/phase2_analysis_contract.md` for the extraction schema, retry behavior, and aggregation contract.

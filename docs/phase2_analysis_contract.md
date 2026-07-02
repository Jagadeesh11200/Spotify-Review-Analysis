# Phase 2 Analysis Contract

Phase 2 runs after data collection in the same app flow and consumes only `usable_records` from the just-created Phase 1 output folder.

The analysis uses Gemini 2.5 Pro to run six separate question-specific LLM passes, then merges the six partial outputs into one structured extraction per feedback item. Aggregation happens from those merged extraction records.

## Execution Model

- Load `usable_records` from each source JSON in a selected `data/raw/session_*` folder.
- Send records to Gemini in batches for Q1, then Q2, Q3, Q4, Q5, and Q6 as separate LLM passes.
- Each pass has its own detailed taxonomy prompt and returns only the fields needed for that question.
- Merge the six partial outputs by `record_id`.
- If a pass batch fails after retries, split that batch into single-record calls for the same question.
- If an individual record still fails, keep a low-confidence fallback extraction so the pipeline can finish.
- Exclude low-confidence merged extractions from quantitative aggregation.
- Run independent question passes with bounded parallelism to reduce wall-clock latency.
- Reuse cached analysis files for the same raw session when available.

## Gemini Defaults

- Model: `gemini-2.5-pro`
- Response format: JSON
- Temperature: `0.1`
- Retries: 3
- Retry delay: increasing delay per attempt
- Batch size: 20 records per request by default
- Text sent per record is capped to keep API calls efficient while preserving review signal

## Weighting Method

Dashboard rankings use `overall_severity x signal_weight`, where `signal_weight` comes from Phase 1 specificity, upvote/like strength, and reply/conversation strength. Counts remain visible, but prioritization favors the most legitimate and information-rich feedback.

## Extracted Fields

Each record extraction includes:

- Q1 dominant barrier, evidence quote, secondary barrier, named Spotify features
- Q2 recommendation frustration categories, severity, status, evidence quote
- Q3 activity context, discovery mode, desired outcome
- Q4 repetition type, intentionality, desire-to-change flag
- Q5 segment proxy scores and evidence
- Q5 listening intensity, intensity evidence, churn risk flag, churn signal type, churn evidence
- Q6 workarounds, competitive displacement, resignation signals
- overall severity
- ongoing/resolved flag
- best verbatim quote
- extraction confidence

## Outputs

Each analysis run writes files under `data/analysis/<session_id>/`:

- `extractions.json`
- `analysis.json`
- `report.md`

The Streamlit dashboard displays:

- source filters over the real high-confidence extraction set
- segment x listening-intensity targeting matrix for interview prioritization
- strategic synthesis and cross-source convergence
- Q1 barrier breakdown by severity and source
- Q2 frustration priority ranking and severity distribution
- Q3 listening-intent matrix
- Q4 intentional vs unintentional repetition split
- Q5 segment-proxy matrix, classification rate, intensity distribution, and interview recommendations
- Q6 unmet-needs evidence from workarounds, displacement, and resignation
- verbatim evidence from the currently filtered population

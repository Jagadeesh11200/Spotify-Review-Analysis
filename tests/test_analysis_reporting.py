from src.analysis.aggregation import aggregate_analysis
from src.analysis.reporting import render_markdown_report
from tests.test_analysis_aggregation import sample_extractions


def test_report_renders_weighted_unmet_need_mentions():
    aggregate = aggregate_analysis(sample_extractions())

    markdown = render_markdown_report(aggregate)

    assert "weighted mentions" in markdown
    assert "discovery memory layer" in markdown

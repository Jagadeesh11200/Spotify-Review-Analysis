from src.home_docs import ARCHITECTURE_ROUTE, DOC_PAGES, USER_GUIDE_ROUTE, architecture_flow_html, flowchart_html, get_doc_page


def test_home_doc_routes_are_available_with_clear_labels():
    user_guide = get_doc_page(USER_GUIDE_ROUTE)
    architecture = get_doc_page(ARCHITECTURE_ROUTE)

    assert user_guide is not None
    assert user_guide.link_label == "How to operate this tool"
    assert "Open the `Dashboard` page first" in user_guide.markdown
    assert "Hide Unclassified or weak signal records" in user_guide.markdown
    assert "Collect data" in user_guide.markdown
    assert "Use the dashboard like a product discovery room" in user_guide.markdown
    assert architecture is not None
    assert architecture.link_label == "Backend architecture one-pager"
    assert "System Intelligence And Method" in architecture.markdown
    assert "Gemini 2.5 Pro" in architecture.markdown
    assert "PM Takeaway" not in architecture.markdown
    assert "product discovery map" not in architecture.markdown
    assert set(DOC_PAGES) == {USER_GUIDE_ROUTE, ARCHITECTURE_ROUTE}


def test_home_doc_flowcharts_include_all_major_steps():
    user_flow = flowchart_html()
    architecture_flow = architecture_flow_html()

    for step in ["Open dashboard", "Filter evidence", "Read Q1-Q6", "Run fresh sample", "Use evidence"]:
        assert step in user_flow
    for layer in ["Source adapters", "Shared feedback schema", "Quality gates", "Gemini product passes", "Aggregation logic", "Dashboard evidence"]:
        assert layer in architecture_flow


def test_unknown_home_doc_route_returns_none():
    assert get_doc_page("missing") is None

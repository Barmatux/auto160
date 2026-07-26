def test_build_analytics_summary_imports_site_event_out():
    from app.analytics import build_analytics_summary
    from app.schemas import SiteEventOut

    assert SiteEventOut is not None
    assert callable(build_analytics_summary)

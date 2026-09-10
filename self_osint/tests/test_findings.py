"""اختبارات منطق التجميع والفرز والتقرير."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from findings import Finding, ScanReport, severity_rank  # noqa: E402
from report import to_json, to_markdown  # noqa: E402


def make_report():
    report = ScanReport(identity={"emails": ["me@example.com"], "usernames": ["me"], "repos": []})
    report.add(Finding(source="gravatar", target="me@example.com", title="ملف عام", severity="low"))
    report.add(Finding(source="hibp", target="me@example.com", title="تسريب", severity="critical"))
    report.add(Finding(source="usernames", target="me", title="حساب", severity="medium"))
    return report


def test_severity_rank_orders_levels():
    assert severity_rank("critical") > severity_rank("high") > severity_rank("medium")
    assert severity_rank("low") > severity_rank("info")


def test_unknown_severity_falls_back_to_info():
    assert severity_rank("bogus") == severity_rank("info")


def test_sorted_findings_puts_critical_first():
    report = make_report()
    assert [f.severity for f in report.sorted_findings()] == ["critical", "medium", "low"]


def test_max_severity_and_counts():
    report = make_report()
    assert report.max_severity == "critical"
    counts = report.counts_by_severity()
    assert counts["critical"] == 1 and counts["medium"] == 1 and counts["low"] == 1
    assert counts["high"] == 0


def test_empty_report_is_info():
    assert ScanReport().max_severity == "info"


def test_errors_do_not_count_as_findings():
    report = ScanReport()
    report.add_error("hibp", "لا يوجد مفتاح")
    assert report.findings == []
    assert report.errors[0]["source"] == "hibp"


def test_markdown_contains_titles_and_advice():
    report = make_report()
    report.findings[0].advice = "احذف البيانات"
    text = to_markdown(report)
    assert "تسريب" in text and "احذف البيانات" in text


def test_json_is_valid_and_sorted():
    import json

    data = json.loads(to_json(make_report()))
    assert data["max_severity"] == "critical"
    assert data["findings"][0]["severity"] == "critical"

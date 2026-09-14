"""اختبارات نموذج البيانات والتخزين والتصفية."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ErrorRecord  # noqa: E402
from store import ErrorStore, filter_records, sort_records  # noqa: E402
import report as report_mod  # noqa: E402


def _rec(**kw):
    base = dict(source="claude_code", kind="tool_error", severity="medium",
                message="فشل", occurred_at="2026-01-01T10:00:00+00:00")
    base.update(kw)
    return ErrorRecord(**base)


def test_append_and_load_roundtrip(tmp_path):
    store = ErrorStore(tmp_path / "errors.jsonl")
    assert store.append(_rec(message="خطأ أول")) is True
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].message == "خطأ أول"
    assert loaded[0].id


def test_duplicate_is_not_appended_twice(tmp_path):
    store = ErrorStore(tmp_path / "errors.jsonl")
    store.append(_rec(message="نفس الخطأ"))
    assert store.append(_rec(message="نفس الخطأ")) is False
    assert len(store.load()) == 1


def test_extend_reports_only_new_records(tmp_path):
    store = ErrorStore(tmp_path / "errors.jsonl")
    first = [_rec(message="أ"), _rec(message="ب")]
    assert store.extend(first) == 2
    assert store.extend(first + [_rec(message="ج")]) == 1
    assert len(store.load()) == 3


def test_corrupt_lines_are_skipped(tmp_path):
    path = tmp_path / "errors.jsonl"
    store = ErrorStore(path)
    store.append(_rec(message="سليم"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ليس JSON}\n\n")
    assert len(store.load()) == 1


def test_filters_by_severity_source_and_search():
    records = [
        _rec(message="عالٍ", severity="high"),
        _rec(message="منخفض", severity="low"),
        _rec(message="من الويب", source="claude_web", severity="critical"),
    ]
    assert len(filter_records(records, min_severity="high")) == 2
    assert len(filter_records(records, source="claude_web")) == 1
    assert len(filter_records(records, search="منخفض")) == 1
    assert filter_records(records, kind="api_error") == []


def test_filter_since_uses_occurred_at():
    records = [
        _rec(message="قديم", occurred_at="2025-01-01T00:00:00+00:00"),
        _rec(message="جديد", occurred_at="2026-06-01T00:00:00+00:00"),
    ]
    kept = filter_records(records, since="2026-01-01")
    assert [r.message for r in kept] == ["جديد"]


def test_sort_newest_first():
    old = _rec(message="قديم", occurred_at="2025-01-01T00:00:00+00:00")
    new = _rec(message="جديد", occurred_at="2026-01-01T00:00:00+00:00")
    assert [r.message for r in sort_records([old, new])] == ["جديد", "قديم"]
    assert [r.message for r in sort_records([old, new], newest_first=False)] == ["قديم", "جديد"]


def test_reports_render_without_crashing():
    records = [_rec(message="فشل الأمر", detail="Error: boom", session="s1")]
    assert "فشل الأمر" in report_mod.render(records, fmt="text", detail=True)
    assert "| الوقت |" in report_mod.render(records, fmt="markdown")
    assert "فشل الأمر" in report_mod.render(records, fmt="json")
    assert "إجمالي الأخطاء: 1" in report_mod.render_stats(records)
    assert report_mod.render_stats([]) == "السجل فارغ."

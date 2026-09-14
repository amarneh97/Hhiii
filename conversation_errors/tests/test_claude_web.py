"""اختبارات استيراد أخطاء محادثات claude.ai من ملف التصدير."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources import claude_web  # noqa: E402


def _export(tmp_path, data, name="conversations.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_user_correction_captures_preceding_claude_reply(tmp_path):
    path = _export(tmp_path, [{
        "uuid": "c1",
        "name": "نقاش عن Git",
        "created_at": "2026-02-01T08:00:00Z",
        "chat_messages": [
            {"sender": "assistant", "text": "استخدم git push --force على main",
             "created_at": "2026-02-01T08:01:00Z"},
            {"sender": "human", "text": "هذا خطأ وخطير، لا تقترح force على main",
             "created_at": "2026-02-01T08:02:00Z"},
        ],
    }])
    records = claude_web.parse_export(path)
    assert len(records) == 1
    rec = records[0]
    assert rec.source == "claude_web"
    assert rec.kind == "user_correction"
    assert rec.session == "نقاش عن Git"
    assert "force" in rec.context["claude_reply_excerpt"]


def test_normal_conversation_produces_no_records(tmp_path):
    path = _export(tmp_path, [{
        "uuid": "c2", "name": "سؤال عادي",
        "chat_messages": [
            {"sender": "human", "text": "اشرح لي الـ decorators", "created_at": "2026-02-02T08:00:00Z"},
            {"sender": "assistant", "text": "الـ decorator دالة تغلّف دالة أخرى…",
             "created_at": "2026-02-02T08:00:30Z"},
        ],
    }])
    assert claude_web.parse_export(path) == []


def test_content_blocks_are_read_when_text_is_missing(tmp_path):
    path = _export(tmp_path, [{
        "uuid": "c3", "name": "كتل محتوى",
        "chat_messages": [
            {"sender": "assistant", "content": [{"type": "text", "text": "الجواب 5"}],
             "created_at": "2026-02-03T08:00:00Z"},
            {"sender": "human", "content": [{"type": "text", "text": "غلط، الجواب 6"}],
             "created_at": "2026-02-03T08:01:00Z"},
        ],
    }])
    records = claude_web.parse_export(path)
    assert len(records) == 1
    assert "الجواب 5" in records[0].context["claude_reply_excerpt"]


def test_output_errors_are_opt_in(tmp_path):
    path = _export(tmp_path, [{
        "uuid": "c4", "name": "تشغيل كود",
        "chat_messages": [
            {"sender": "assistant", "text": "Traceback (most recent call last): ZeroDivisionError",
             "created_at": "2026-02-04T08:00:00Z"},
        ],
    }])
    assert claude_web.parse_export(path) == []
    records = claude_web.parse_export(path, include_output_errors=True)
    assert len(records) == 1
    assert records[0].severity == "high"


def test_single_conversation_object_is_accepted(tmp_path):
    path = _export(tmp_path, {
        "uuid": "c5", "name": "محادثة مفردة",
        "chat_messages": [
            {"sender": "assistant", "text": "جرّب هذا", "created_at": "2026-02-05T08:00:00Z"},
            {"sender": "human", "text": "ما اشتغل", "created_at": "2026-02-05T08:01:00Z"},
        ],
    })
    assert len(claude_web.parse_export(path)) == 1


def test_broken_file_raises_clear_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ليس JSON}", encoding="utf-8")
    with pytest.raises(ValueError):
        claude_web.parse_export(path)

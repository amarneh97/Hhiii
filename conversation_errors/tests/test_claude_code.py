"""اختبارات استخراج الأخطاء من سجلات جلسات Claude Code."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources import claude_code  # noqa: E402


def _write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return path


def test_tool_result_error_is_captured_with_tool_name(tmp_path):
    path = _write(tmp_path / "proj" / "sess.jsonl", [
        {"type": "assistant", "sessionId": "s1", "cwd": "/repo", "timestamp": "2026-01-01T10:00:00Z",
         "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash"}]}},
        {"type": "user", "sessionId": "s1", "cwd": "/repo", "timestamp": "2026-01-01T10:00:05Z",
         "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                                  "content": "bash: npm: command not found"}]}},
    ])
    records = claude_code.parse_transcript(path)
    assert len(records) == 1
    rec = records[0]
    assert rec.source == "claude_code"
    assert rec.kind == "tool_error"
    assert rec.context["tool"] == "Bash"
    assert rec.session == "s1"
    assert rec.project == "/repo"
    assert "command not found" in rec.detail


def test_successful_tool_result_is_ignored(tmp_path):
    path = _write(tmp_path / "sess.jsonl", [
        {"type": "user", "sessionId": "s1", "timestamp": "2026-01-01T10:00:00Z",
         "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "تم بنجاح"}]}},
    ])
    assert claude_code.parse_transcript(path) == []


def test_api_error_entry_is_captured(tmp_path):
    path = _write(tmp_path / "sess.jsonl", [
        {"type": "assistant", "sessionId": "s2", "timestamp": "2026-01-02T09:00:00Z",
         "isApiErrorMessage": True,
         "message": {"content": [{"type": "text", "text": "API Error: 529 overloaded_error"}]}},
    ])
    records = claude_code.parse_transcript(path)
    assert len(records) == 1
    assert records[0].kind == "api_error"


def test_user_correction_is_captured_and_can_be_disabled(tmp_path):
    path = _write(tmp_path / "sess.jsonl", [
        {"type": "user", "sessionId": "s3", "timestamp": "2026-01-03T09:00:00Z",
         "message": {"content": "لا، هذا خطأ — الملف الذي عدّلته ليس المطلوب"}},
    ])
    records = claude_code.parse_transcript(path)
    assert [r.kind for r in records] == ["user_correction"]
    assert records[0].severity == "high"
    assert claude_code.parse_transcript(path, include_corrections=False) == []


def test_ordinary_user_message_is_not_flagged(tmp_path):
    path = _write(tmp_path / "sess.jsonl", [
        {"type": "user", "sessionId": "s4", "timestamp": "2026-01-04T09:00:00Z",
         "message": {"content": "أضف اختبارًا لهذه الدالة من فضلك"}},
    ])
    assert claude_code.parse_transcript(path) == []


def test_tool_use_result_stderr_is_captured(tmp_path):
    path = _write(tmp_path / "sess.jsonl", [
        {"type": "user", "sessionId": "s5", "timestamp": "2026-01-05T09:00:00Z",
         "message": {"content": []},
         "toolUseResult": {"stderr": "fatal: not a git repository", "toolName": "Bash"}},
    ])
    records = claude_code.parse_transcript(path)
    assert len(records) == 1
    assert "not a git repository" in records[0].detail


def test_malformed_lines_do_not_break_parsing(tmp_path):
    path = tmp_path / "sess.jsonl"
    path.write_text(
        "ليس JSON\n\n"
        + json.dumps({"type": "user", "sessionId": "s6", "timestamp": "2026-01-06T09:00:00Z",
                      "message": {"content": [{"type": "tool_result", "is_error": True,
                                               "content": "Error: boom"}]}})
        + "\n",
        encoding="utf-8",
    )
    assert len(claude_code.parse_transcript(path)) == 1


def test_scan_walks_directory_tree(tmp_path):
    _write(tmp_path / "a" / "one.jsonl", [
        {"type": "user", "sessionId": "a1", "timestamp": "2026-01-07T09:00:00Z",
         "message": {"content": [{"type": "tool_result", "is_error": True, "content": "Error: x"}]}},
    ])
    _write(tmp_path / "b" / "two.jsonl", [
        {"type": "user", "sessionId": "b1", "timestamp": "2026-01-08T09:00:00Z",
         "message": {"content": [{"type": "tool_result", "is_error": True, "content": "Error: y"}]}},
    ])
    records = claude_code.scan(root=tmp_path)
    assert len(records) == 2
    assert {r.session for r in records} == {"a1", "b1"}


def test_scan_of_missing_root_returns_empty(tmp_path):
    assert claude_code.scan(root=tmp_path / "لا-يوجد") == []

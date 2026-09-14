"""اختبارات خطّاف Claude Code وكشف الأخطاء في النصوص."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import detect  # noqa: E402
import hook  # noqa: E402
from store import ErrorStore  # noqa: E402

HOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hook.py")
MAIN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")


def test_failed_tool_payload_becomes_record():
    record = hook.record_from_payload({
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "cwd": "/repo",
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": {"is_error": True, "content": "sh: npm: command not found"},
    })
    assert record is not None
    assert record.kind == "tool_error"
    assert record.context["tool"] == "Bash"
    assert "npm" in record.detail


def test_successful_tool_payload_is_ignored():
    assert hook.record_from_payload({
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": {"content": "محتوى الملف"},
    }) is None


def test_prompt_is_recorded_only_when_it_is_a_correction():
    assert hook.record_from_payload({
        "hook_event_name": "UserPromptSubmit",
        "prompt": "أضف اختبارًا جديدًا",
    }) is None
    record = hook.record_from_payload({
        "hook_event_name": "UserPromptSubmit",
        "prompt": "لا، هذا خطأ — أعد كتابة الدالة",
    })
    assert record is not None and record.kind == "user_correction"


def test_permission_notification_is_recorded():
    record = hook.record_from_payload({
        "hook_event_name": "Notification",
        "message": "Claude needs your permission to use Bash",
    })
    assert record is not None and record.kind == "permission"


def test_unknown_event_is_ignored():
    assert hook.record_from_payload({"hook_event_name": "SessionStart"}) is None


def test_hook_writes_to_log_and_never_fails(tmp_path):
    log = tmp_path / "errors.jsonl"
    env = dict(os.environ, CLAUDE_ERROR_LOG=str(log))
    payload = json.dumps({
        "hook_event_name": "PostToolUse",
        "session_id": "s2",
        "tool_name": "Edit",
        "tool_response": {"is_error": True, "content": "Error: file not found"},
    })
    result = subprocess.run([sys.executable, HOOK_PATH], input=payload, text=True,
                            capture_output=True, env=env)
    assert result.returncode == 0
    assert len(ErrorStore(log).load()) == 1

    # حتى مع مدخل تالف يجب ألا يفشل الخطّاف ولا يعطّل الجلسة.
    broken = subprocess.run([sys.executable, HOOK_PATH], input="ليس JSON", text=True,
                            capture_output=True, env=env)
    assert broken.returncode == 0
    assert len(ErrorStore(log).load()) == 1


def test_cli_log_and_list_roundtrip(tmp_path):
    log = tmp_path / "errors.jsonl"
    add = subprocess.run(
        [sys.executable, MAIN_PATH, "--log-file", str(log), "log",
         "--message", "اقترح أمرًا خاطئًا", "--source", "claude_web", "--severity", "high"],
        text=True, capture_output=True)
    assert add.returncode == 0, add.stderr
    listed = subprocess.run(
        [sys.executable, MAIN_PATH, "--log-file", str(log), "list", "--min-severity", "high"],
        text=True, capture_output=True)
    assert "اقترح أمرًا خاطئًا" in listed.stdout
    stats = subprocess.run([sys.executable, MAIN_PATH, "--log-file", str(log), "stats"],
                           text=True, capture_output=True)
    assert "إجمالي الأخطاء: 1" in stats.stdout


def test_install_hook_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"PostToolUse": []}, "model": "opus"}), encoding="utf-8")
    first = subprocess.run([sys.executable, MAIN_PATH, "install-hook", "--settings", str(settings)],
                           text=True, capture_output=True)
    assert first.returncode == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "opus"  # لا نُتلف بقية الإعدادات
    assert len(data["hooks"]["PostToolUse"]) == 1
    assert data["hooks"]["PostToolUse"][0]["matcher"] == "*"

    second = subprocess.run([sys.executable, MAIN_PATH, "install-hook", "--settings", str(settings)],
                            text=True, capture_output=True)
    assert "مسبقًا" in second.stdout
    assert len(json.loads(settings.read_text(encoding="utf-8"))["hooks"]["PostToolUse"]) == 1

    removed = subprocess.run([sys.executable, MAIN_PATH, "uninstall-hook", "--settings", str(settings)],
                             text=True, capture_output=True)
    assert removed.returncode == 0
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" not in after and after["model"] == "opus"


def test_detect_helpers():
    assert detect.looks_like_correction("هذا غلط تمامًا")
    assert detect.looks_like_correction("that's wrong")
    assert not detect.looks_like_correction("شكرًا، ممتاز")
    assert detect.classify("API Error: overloaded") == "api_error"
    # رفض صلاحية داخل Claude Code يُصنَّف permission، بينما فشل صدفة يبقى tool_error.
    assert detect.classify("Claude needs your permission to use Bash") == "permission"
    assert detect.classify("bash: /etc/shadow: Permission denied") == "tool_error"
    assert detect.classify("Traceback (most recent call last)") == "tool_error"
    assert detect.summarize("سطر عادي\nError: انفجار") == "Error: انفجار"

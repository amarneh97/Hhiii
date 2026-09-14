#!/usr/bin/env python3
"""نقطة دخول خطّافات (hooks) Claude Code لتسجيل الأخطاء لحظة وقوعها.

يستقبل حمولة JSON على stdin ويكتب الخطأ في السجل ثم يخرج بالرمز 0 دائمًا،
حتى لا يعطّل الجلسة مهما حدث.

التركيب: python main.py install-hook   (أو --global للتركيب لكل المشاريع)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detect                      # noqa: E402
from models import ErrorRecord     # noqa: E402
from store import ErrorStore       # noqa: E402


def _response_text(response) -> str:
    """يحوّل ردّ الأداة إلى نص قابل للفحص."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("error", "stderr", "content", "output", "message", "result"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                return "\n".join(str(v) for v in value)
        return json.dumps(response, ensure_ascii=False)[:4000]
    return str(response)


def _is_error(response) -> bool:
    if isinstance(response, dict):
        if response.get("is_error") or response.get("isError") or response.get("error"):
            return True
        status = str(response.get("status", "")).lower()
        if status in ("error", "failed"):
            return True
    return detect.looks_like_error(_response_text(response))


def record_from_payload(payload: dict):
    """يحوّل حمولة الخطّاف إلى سجل خطأ، أو None إن لم يكن فيها خطأ."""
    event = payload.get("hook_event_name", "") or payload.get("hook_event", "")
    session = payload.get("session_id", "")
    project = payload.get("cwd", "")
    common = dict(source="claude_code", session=session, project=project)

    if event == "PostToolUse":
        response = payload.get("tool_response")
        if not _is_error(response):
            return None
        text = _response_text(response)
        kind = detect.classify(text, flagged_error=True)
        return ErrorRecord(
            kind=kind,
            severity=detect.severity_for(kind, text),
            message=detect.summarize(text) or f"فشل الأداة {payload.get('tool_name', '')}",
            detail=text[:8000],
            context={
                "tool": payload.get("tool_name", ""),
                "tool_input": json.dumps(payload.get("tool_input", {}), ensure_ascii=False)[:1500],
                "hook": event,
            },
            **common,
        )

    if event == "UserPromptSubmit":
        prompt = payload.get("prompt", "") or ""
        if not detect.looks_like_correction(prompt):
            return None
        return ErrorRecord(
            kind="user_correction",
            severity=detect.severity_for("user_correction", prompt),
            message=detect.summarize(prompt) or "تصحيح من المستخدم",
            detail=prompt[:8000],
            context={"hook": event},
            **common,
        )

    if event == "Notification":
        text = payload.get("message", "") or ""
        if not text.strip():
            return None
        kind = detect.classify(text)
        if kind not in ("permission", "api_error") and not detect.looks_like_error(text):
            return None
        return ErrorRecord(
            kind=kind if kind != "other" else "permission",
            severity=detect.severity_for(kind, text),
            message=detect.summarize(text) or text[:160],
            detail=text[:4000],
            context={"hook": event},
            **common,
        )

    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if isinstance(payload, dict):
            record = record_from_payload(payload)
            if record is not None:
                ErrorStore().append(record)
    except Exception:
        # الخطّاف لا يُفشل الجلسة أبدًا مهما كان سبب العطل.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""استخراج الأخطاء من محادثات كلود العادي (claude.ai) عبر ملف التصدير.

كيف تحصل على الملف: claude.ai ← Settings ← Privacy ← Export data،
يصلك بريد فيه أرشيف يحوي conversations.json. مرّره لهذه الأداة.

ما يُلتقَط: كل رسالة منك تقول فيها إن الرد كان خاطئًا (مع اقتباس ردّ كلود
الذي سبقها)، واختياريًا أي رسالة تحمل أثر خطأ تقني.
"""
import json
from pathlib import Path

import detect
from models import ErrorRecord


def _message_text(message) -> str:
    """نص الرسالة سواء كان في text أو في كتل content."""
    if not isinstance(message, dict):
        return ""
    text = message.get("text") or ""
    if text:
        return str(text)
    parts = []
    for block in message.get("content") or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block.get("type") == "tool_result":
                inner = block.get("content")
                parts.append(inner if isinstance(inner, str) else json.dumps(inner, ensure_ascii=False))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(p for p in parts if p)


def _sender(message) -> str:
    return str(message.get("sender") or message.get("role") or "")


def _conversations(data) -> list:
    """يقبل ملف تصدير كامل (قائمة) أو محادثة واحدة (قاموس)."""
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if isinstance(data, dict):
        if "chat_messages" in data or "messages" in data:
            return [data]
        for key in ("conversations", "data"):
            if isinstance(data.get(key), list):
                return [c for c in data[key] if isinstance(c, dict)]
    return []


def parse_export(path, include_output_errors=False) -> list:
    """يستخرج الأخطاء من ملف تصدير claude.ai."""
    path = Path(path).expanduser()
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"تعذّرت قراءة ملف التصدير {path}: {exc}") from exc

    records = []
    for convo in _conversations(data):
        title = convo.get("name") or convo.get("title") or convo.get("uuid", "")
        messages = convo.get("chat_messages") or convo.get("messages") or []
        previous_assistant = ""
        for message in messages:
            if not isinstance(message, dict):
                continue
            text = _message_text(message)
            sender = _sender(message).lower()
            when = message.get("created_at") or convo.get("created_at") or ""
            common = dict(
                source="claude_web",
                session=str(title),
                project="claude.ai",
                occurred_at=str(when),
            )

            if sender in ("human", "user"):
                if text.strip() and detect.looks_like_correction(text):
                    records.append(ErrorRecord(
                        kind="user_correction",
                        severity=detect.severity_for("user_correction", text),
                        message=detect.summarize(text) or "تصحيح من المستخدم",
                        detail=text,
                        context={
                            "conversation": str(title),
                            "conversation_id": convo.get("uuid", ""),
                            # ردّ كلود الذي أثار التصحيح — هو محلّ الخطأ فعليًا.
                            "claude_reply_excerpt": previous_assistant[:600],
                        },
                        **common,
                    ))
            else:
                previous_assistant = text

            # أخطاء تقنية ظاهرة في نص الرسالة (اختياري لأنها قد تكون مجرد نقاش عن خطأ).
            if include_output_errors and text.strip() and detect.looks_like_error(text):
                kind = detect.classify(text)
                records.append(ErrorRecord(
                    kind=kind,
                    severity=detect.severity_for(kind, text),
                    message=detect.summarize(text),
                    detail=text,
                    context={
                        "conversation": str(title),
                        "conversation_id": convo.get("uuid", ""),
                        "sender": sender,
                    },
                    **common,
                ))
    return records

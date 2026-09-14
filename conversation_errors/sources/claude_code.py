"""استخراج الأخطاء من سجلات جلسات Claude Code (ملفات transcript بصيغة JSONL).

يقرأ الملفات من ~/.claude/projects/<مشروع>/<جلسة>.jsonl افتراضيًا،
ويلتقط: فشل الأدوات، أخطاء الـ API، رفض الصلاحيات، وتصحيحاتك أنت.
التحليل متسامح مع اختلاف الإصدارات: أي حقل مفقود يُتجاوَز بدل أن يُسقط الفحص.
"""
import json
from pathlib import Path

import detect
from models import ErrorRecord


DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def transcript_files(root=None, since="") -> list:
    """كل ملفات الجلسات تحت المجلد الجذر، الأحدث أولًا."""
    base = Path(root).expanduser() if root else DEFAULT_ROOT
    if not base.exists():
        return []
    if base.is_file():
        return [base]
    files = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _text_of(content) -> str:
    """يحوّل محتوى رسالة (نص أو قائمة كتل) إلى نص واحد."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _text_of(content.get("content", "")) or str(content.get("text", ""))
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_result":
                    parts.append(_text_of(block.get("content", "")))
        return "\n".join(p for p in parts if p)
    return ""


def _error_blocks(entry) -> list:
    """كتل tool_result المعلَّمة كخطأ داخل رسالة واحدة."""
    message = entry.get("message") or {}
    content = message.get("content")
    blocks = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                blocks.append(block)
    return blocks


def _tool_name_for(entry, tool_use_id, tool_names) -> str:
    """اسم الأداة المقابلة لنتيجة الخطأ، إن عرفناه من رسالة سابقة."""
    return tool_names.get(tool_use_id, entry.get("toolName", "") or "")


def parse_transcript(path, include_corrections=True) -> list:
    """يستخرج أخطاء جلسة واحدة من ملف transcript."""
    path = Path(path)
    records = []
    tool_names = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return records

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue

        session = entry.get("sessionId", "") or path.stem
        project = entry.get("cwd", "") or path.parent.name
        when = entry.get("timestamp", "")
        etype = entry.get("type", "")
        message = entry.get("message") or {}
        common = dict(source="claude_code", session=session, project=project, occurred_at=when)

        # نتتبّع أسماء الأدوات لربط كل نتيجة خطأ بالأداة التي أنتجتها.
        if isinstance(message.get("content"), list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_names[block.get("id", "")] = block.get("name", "")

        # 1) فشل أداة: كتلة tool_result معلَّمة is_error.
        for block in _error_blocks(entry):
            text = _text_of(block.get("content", ""))
            tool = _tool_name_for(entry, block.get("tool_use_id", ""), tool_names)
            kind = detect.classify(text, flagged_error=True)
            records.append(ErrorRecord(
                kind=kind,
                severity=detect.severity_for(kind, text),
                message=detect.summarize(text) or f"فشل الأداة {tool or 'غير معروفة'}",
                detail=text,
                context={"tool": tool, "transcript": str(path), "tool_use_id": block.get("tool_use_id", "")},
                **common,
            ))

        # 2) خطأ API أو رسالة نظام معلَّمة كخطأ.
        raw_text = _text_of(message.get("content", entry.get("content", "")))
        is_api_error = bool(entry.get("isApiErrorMessage"))
        is_sys_error = etype == "system" and str(entry.get("level", "")).lower() == "error"
        if (is_api_error or is_sys_error) and raw_text.strip():
            kind = "api_error" if is_api_error else detect.classify(raw_text, flagged_error=True)
            records.append(ErrorRecord(
                kind=kind,
                severity=detect.severity_for(kind, raw_text),
                message=detect.summarize(raw_text) or "خطأ في الجلسة",
                detail=raw_text,
                context={"transcript": str(path), "entry_type": etype},
                **common,
            ))

        # 3) نتيجة أداة مخزّنة في toolUseResult بصيغة قديمة.
        result = entry.get("toolUseResult")
        if isinstance(result, dict) and (result.get("is_error") or result.get("stderr")):
            text = _text_of(result.get("content", "")) or str(result.get("stderr", ""))
            if text.strip():
                kind = detect.classify(text, flagged_error=True)
                records.append(ErrorRecord(
                    kind=kind,
                    severity=detect.severity_for(kind, text),
                    message=detect.summarize(text) or "فشل تنفيذ أداة",
                    detail=text,
                    context={"transcript": str(path), "tool": result.get("toolName", "")},
                    **common,
                ))

        # 4) تصحيح منك: رسالة مستخدم نصية تقول إن كلود أخطأ.
        if include_corrections and etype == "user" and not _error_blocks(entry):
            typed = _text_of(message.get("content", ""))
            if typed.strip() and detect.looks_like_correction(typed):
                records.append(ErrorRecord(
                    kind="user_correction",
                    severity=detect.severity_for("user_correction", typed),
                    message=detect.summarize(typed) or "تصحيح من المستخدم",
                    detail=typed,
                    context={"transcript": str(path)},
                    **common,
                ))

    return records


def scan(root=None, include_corrections=True, limit_files=0) -> list:
    """يفحص كل الجلسات ويُعيد قائمة الأخطاء."""
    files = transcript_files(root)
    if limit_files:
        files = files[:limit_files]
    records = []
    for path in files:
        records.extend(parse_transcript(path, include_corrections=include_corrections))
    return records

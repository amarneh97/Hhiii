"""عرض سجل الأخطاء: نص للطرفية، Markdown، أو JSON."""
import json
from collections import Counter

from models import SEVERITY_ORDER, severity_rank


SEVERITY_LABEL = {
    "critical": "حرج",
    "high": "عالٍ",
    "medium": "متوسط",
    "low": "منخفض",
    "info": "معلومة",
}

KIND_LABEL = {
    "tool_error": "فشل أداة",
    "api_error": "خطأ API",
    "user_correction": "تصحيح منك",
    "permission": "صلاحية",
    "manual": "تسجيل يدوي",
    "other": "أخرى",
}

SOURCE_LABEL = {
    "claude_code": "Claude Code",
    "claude_web": "claude.ai",
    "manual": "يدوي",
}


def _label(mapping, key):
    return mapping.get(key, key)


def summarize(records) -> dict:
    """إحصاءات السجل: الإجمالي وتوزيعه على المصدر والنوع والخطورة."""
    return {
        "total": len(records),
        "by_source": dict(Counter(r.source for r in records)),
        "by_kind": dict(Counter(r.kind for r in records)),
        "by_severity": dict(Counter(r.severity for r in records)),
        "by_session": dict(Counter(r.session for r in records if r.session).most_common(10)),
        "first": min((r.occurred_at for r in records), default=""),
        "last": max((r.occurred_at for r in records), default=""),
    }


def render_text(records, detail=False) -> str:
    """جدول مختصر للطرفية."""
    if not records:
        return "لا توجد أخطاء مسجّلة بهذه المعايير."
    lines = []
    for rec in records:
        when = (rec.occurred_at or "")[:19].replace("T", " ")
        head = (
            f"[{rec.id}] {when}  {_label(SEVERITY_LABEL, rec.severity)}  "
            f"{_label(SOURCE_LABEL, rec.source)} / {_label(KIND_LABEL, rec.kind)}"
        )
        lines.append(head)
        lines.append(f"    {rec.message}")
        if rec.session:
            lines.append(f"    الجلسة: {rec.session}")
        if detail and rec.detail:
            body = rec.detail if len(rec.detail) < 2000 else rec.detail[:2000] + " …"
            for line in body.splitlines():
                lines.append(f"      | {line}")
            if rec.context:
                lines.append(f"      سياق: {json.dumps(rec.context, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_stats(records) -> str:
    """ملخّص رقمي للسجل."""
    stats = summarize(records)
    if not stats["total"]:
        return "السجل فارغ."
    lines = [f"إجمالي الأخطاء: {stats['total']}"]
    if stats["first"]:
        lines.append(f"المدى الزمني: {stats['first'][:19]} ← {stats['last'][:19]}")

    def block(title, counts, labels):
        lines.append("")
        lines.append(title)
        for key, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {_label(labels, key)}: {count}")

    block("حسب المصدر:", stats["by_source"], SOURCE_LABEL)
    block("حسب النوع:", stats["by_kind"], KIND_LABEL)
    by_sev = dict(sorted(stats["by_severity"].items(), key=lambda kv: -severity_rank(kv[0])))
    block("حسب الخطورة:", by_sev, SEVERITY_LABEL)
    if stats["by_session"]:
        lines.append("")
        lines.append("أكثر الجلسات أخطاءً:")
        for session, count in stats["by_session"].items():
            lines.append(f"  {session}: {count}")
    return "\n".join(lines)


def render_markdown(records) -> str:
    """تقرير Markdown صالح للحفظ أو المشاركة."""
    stats = summarize(records)
    lines = ["# سجل أخطاء المحادثات", ""]
    lines.append(f"- إجمالي الأخطاء: **{stats['total']}**")
    if stats["first"]:
        lines.append(f"- المدى الزمني: {stats['first'][:19]} ← {stats['last'][:19]}")
    for title, counts, labels in (
        ("المصادر", stats["by_source"], SOURCE_LABEL),
        ("الأنواع", stats["by_kind"], KIND_LABEL),
        ("الخطورة", stats["by_severity"], SEVERITY_LABEL),
    ):
        if counts:
            parts = ", ".join(f"{_label(labels, k)}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
            lines.append(f"- {title}: {parts}")
    lines.append("")

    if not records:
        lines.append("لا توجد أخطاء مسجّلة.")
        return "\n".join(lines)

    lines.append("| الوقت | المصدر | النوع | الخطورة | الخطأ |")
    lines.append("| --- | --- | --- | --- | --- |")
    for rec in records:
        when = (rec.occurred_at or "")[:19].replace("T", " ")
        message = rec.message.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {when} | {_label(SOURCE_LABEL, rec.source)} | {_label(KIND_LABEL, rec.kind)} | "
            f"{_label(SEVERITY_LABEL, rec.severity)} | {message} |"
        )

    lines.append("")
    lines.append("## التفاصيل")
    for rec in records:
        lines.append("")
        lines.append(f"### `{rec.id}` — {rec.message}")
        lines.append(f"- المصدر: {_label(SOURCE_LABEL, rec.source)} / {_label(KIND_LABEL, rec.kind)}")
        lines.append(f"- الخطورة: {_label(SEVERITY_LABEL, rec.severity)}")
        if rec.session:
            lines.append(f"- الجلسة: {rec.session}")
        if rec.project:
            lines.append(f"- المشروع: {rec.project}")
        lines.append(f"- الوقت: {rec.occurred_at}")
        if rec.tags:
            lines.append(f"- وسوم: {', '.join(rec.tags)}")
        if rec.detail:
            lines.append("")
            lines.append("```")
            lines.append(rec.detail[:4000])
            lines.append("```")
    return "\n".join(lines)


def render_json(records) -> str:
    return json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2)


def render(records, fmt="text", detail=False) -> str:
    if fmt == "json":
        return render_json(records)
    if fmt == "markdown":
        return render_markdown(records)
    return render_text(records, detail=detail)


__all__ = ["render", "render_stats", "summarize", "SEVERITY_ORDER"]

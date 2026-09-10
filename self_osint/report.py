"""عرض نتائج الفحص: جدول في الطرفية، أو Markdown، أو JSON."""
import json

from tabulate import tabulate

from findings import ScanReport, SEVERITY_ORDER

SEVERITY_LABEL = {
    "critical": "حرِج",
    "high": "عالٍ",
    "medium": "متوسط",
    "low": "منخفض",
    "info": "معلومة",
}


def to_json(report: ScanReport, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent)


def to_markdown(report: ScanReport) -> str:
    lines = ["# تقرير البصمة الرقمية الذاتية", ""]
    identity = report.identity
    if identity.get("emails"):
        lines.append(f"- **الإيميلات المفحوصة:** {', '.join(identity['emails'])}")
    if identity.get("usernames"):
        lines.append(f"- **أسماء المستخدمين:** {', '.join(identity['usernames'])}")
    if identity.get("repos"):
        lines.append(f"- **المستودعات المفحوصة:** {', '.join(identity['repos'])}")
    lines.append(f"- **وقت الفحص:** {report.started_at} → {report.finished_at}")
    lines.append("")

    counts = report.counts_by_severity()
    summary = " | ".join(
        f"{SEVERITY_LABEL[level]}: {counts[level]}" for level in reversed(SEVERITY_ORDER)
    )
    lines.append(f"**الملخّص:** {len(report.findings)} نتيجة — {summary}")
    lines.append("")

    if not report.findings:
        lines.append("لم يُعثر على أي انكشاف عبر المصادر المفعّلة.")

    current_severity = None
    for finding in report.sorted_findings():
        if finding.severity != current_severity:
            current_severity = finding.severity
            lines.append(f"\n## خطورة: {SEVERITY_LABEL.get(current_severity, current_severity)}\n")
        lines.append(f"### {finding.title}")
        lines.append(f"- **المصدر:** {finding.source} — **الهدف:** {finding.target}")
        if finding.detail:
            lines.append(f"- **التفاصيل:** {finding.detail}")
        if finding.url:
            lines.append(f"- **الرابط:** {finding.url}")
        if finding.advice:
            lines.append(f"- **الإجراء المقترح:** {finding.advice}")
        lines.append("")

    if report.errors:
        lines.append("## مصادر تعذّر تشغيلها\n")
        for error in report.errors:
            lines.append(f"- **{error['source']}:** {error['message']}")
        lines.append("")

    return "\n".join(lines)


def to_console(report: ScanReport) -> str:
    counts = report.counts_by_severity()
    header = [
        "",
        "=" * 72,
        "  تقرير البصمة الرقمية الذاتية (Self-OSINT)",
        "=" * 72,
    ]
    identity = report.identity
    for label, key in (("الإيميلات", "emails"), ("أسماء المستخدمين", "usernames"), ("المستودعات", "repos")):
        if identity.get(key):
            header.append(f"  {label}: {', '.join(identity[key])}")
    header.append(
        "  الملخّص: "
        + " | ".join(f"{SEVERITY_LABEL[l]}={counts[l]}" for l in reversed(SEVERITY_ORDER))
    )
    header.append("")

    if not report.findings:
        header.append("  لم يُعثر على أي انكشاف عبر المصادر المفعّلة.\n")
        return "\n".join(header)

    rows = [
        [
            SEVERITY_LABEL.get(f.severity, f.severity),
            f.source,
            f.title,
            (f.detail[:80] + "…") if len(f.detail) > 80 else f.detail,
        ]
        for f in report.sorted_findings()
    ]
    table = tabulate(
        rows, headers=["الخطورة", "المصدر", "النتيجة", "التفاصيل"], tablefmt="github"
    )

    tail = []
    if report.errors:
        tail.append("\n  مصادر تعذّر تشغيلها:")
        for error in report.errors:
            tail.append(f"    - {error['source']}: {error['message']}")
    tail.append("\n  استخدم --format markdown أو --output تقرير.md للحصول على التفاصيل الكاملة والنصائح.\n")

    return "\n".join(header) + table + "\n" + "\n".join(tail)

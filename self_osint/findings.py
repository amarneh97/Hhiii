"""نماذج البيانات المشتركة لنتائج فحص البصمة الرقمية الذاتية."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


# مستويات الخطورة مرتّبة تصاعديًا؛ تُستخدم للفرز وتلوين التقرير.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


def severity_rank(severity: str) -> int:
    """رتبة رقمية للخطورة (الأعلى = أخطر). أي قيمة غير معروفة تُعامَل كـ info."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return 0


@dataclass
class Finding:
    """نتيجة واحدة اكتُشفت عن الهوية المفحوصة.

    source: اسم المصدر (hibp, gravatar, usernames, ...).
    target: المعرّف المفحوص (إيميل، اسم مستخدم، مسار مستودع).
    title:  عنوان مختصر لما وُجد.
    detail: تفاصيل إضافية تُعرض في التقرير.
    severity: أحد SEVERITY_ORDER.
    url: رابط مرجعي إن وُجد.
    advice: خطوة عملية مقترحة لتقليل الانكشاف.
    data: حقول خام إضافية تُحفظ في مخرجات JSON.
    """

    source: str
    target: str
    title: str
    detail: str = ""
    severity: str = "info"
    url: str = ""
    advice: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanReport:
    """تجميعة نتائج فحص كامل."""

    identity: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def add_error(self, source: str, message: str) -> None:
        """يسجّل فشل مصدر دون إسقاط بقية الفحص (مفتاح مفقود، شبكة، حد طلبات)."""
        self.errors.append({"source": source, "message": message})

    def sorted_findings(self) -> list:
        """الأخطر أولًا، ثم أبجديًا حسب المصدر لثبات الترتيب."""
        return sorted(
            self.findings,
            key=lambda f: (-severity_rank(f.severity), f.source, f.title),
        )

    def counts_by_severity(self) -> dict:
        counts = {level: 0 for level in SEVERITY_ORDER}
        for finding in self.findings:
            key = finding.severity if finding.severity in counts else "info"
            counts[key] += 1
        return counts

    @property
    def max_severity(self) -> str:
        if not self.findings:
            return "info"
        return max(self.findings, key=lambda f: severity_rank(f.severity)).severity

    def to_dict(self) -> dict:
        return {
            "identity": self.identity,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "max_severity": self.max_severity,
            "counts_by_severity": self.counts_by_severity(),
            "findings": [f.to_dict() for f in self.sorted_findings()],
            "errors": self.errors,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

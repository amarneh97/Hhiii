"""نماذج البيانات المشتركة لسجل أخطاء المحادثات."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib


# مستويات الخطورة مرتّبة تصاعديًا؛ تُستخدم للفرز والتصفية.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# أنواع الأخطاء التي تُسجَّل.
KINDS = [
    "tool_error",       # فشل أداة داخل Claude Code (أمر، قراءة ملف، تعديل...)
    "api_error",        # خطأ من الـ API نفسه (انقطاع، حد طلبات، رفض)
    "user_correction",  # تصحيح منك: قلت لكلود إنه أخطأ
    "manual",           # خطأ سجّلته أنت يدويًا
    "permission",       # رفض صلاحية أو أداة محظورة
    "other",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def severity_rank(severity: str) -> int:
    """رتبة رقمية للخطورة (الأعلى = أخطر). أي قيمة غير معروفة تُعامَل كـ info."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return 0


@dataclass
class ErrorRecord:
    """خطأ واحد وقع في محادثة.

    source:      claude_code | claude_web | manual
    kind:        أحد KINDS.
    severity:    أحد SEVERITY_ORDER.
    message:     سطر مختصر يصف الخطأ.
    detail:      النص الكامل (مخرجات الأداة، رسالة الـ API، اقتباس منك).
    session:     معرّف الجلسة أو عنوان المحادثة.
    project:     مسار المشروع أو مصدر المحادثة.
    occurred_at: وقت وقوع الخطأ كما ورد في المحادثة.
    logged_at:   وقت تسجيله في هذا السجل.
    context:     حقول خام إضافية (اسم الأداة، رقم السطر، مقتطف الطلب...).
    tags:        وسوم حرة للتصنيف لاحقًا.
    """

    source: str
    kind: str = "other"
    severity: str = "medium"
    message: str = ""
    detail: str = ""
    session: str = ""
    project: str = ""
    occurred_at: str = ""
    logged_at: str = field(default_factory=utcnow)
    context: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    id: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = self.logged_at
        if not self.id:
            self.id = self.fingerprint()

    def fingerprint(self) -> str:
        """بصمة ثابتة تمنع تكرار نفس الخطأ عند إعادة الفحص."""
        raw = "|".join([
            self.source,
            self.kind,
            self.session,
            self.occurred_at,
            self.message[:300],
            self.detail[:300],
        ])
        return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorRecord":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

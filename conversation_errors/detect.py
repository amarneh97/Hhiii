"""كشف الأخطاء داخل نصوص المحادثة (مخرجات أدوات، رسائل API، تصحيحات منك)."""
import re


# عبارات تدل على أنك صحّحت لكلود خطأ — عربية وإنجليزية.
CORRECTION_PATTERNS = [
    r"\bهذا خطأ\b", r"\bهذا غلط\b", r"\bغلط\b", r"\bخطأ\b", r"\bأخطأت\b",
    r"\bخطا\b", r"\bما ضبط\b", r"\bما اشتغل\b", r"\bلا يعمل\b", r"\bما زبط\b",
    r"\bصحّح\b", r"\bصحح\b", r"\bعدّل هذا\b", r"\bأعد المحاولة\b", r"\bكسرت\b",
    r"\bليس ما طلبت\b", r"\bلم أطلب\b", r"\bمو هيك\b",
    r"\bthat'?s wrong\b", r"\bthis is wrong\b", r"\byou'?re wrong\b",
    r"\bincorrect\b", r"\byou broke\b", r"\bdoesn'?t work\b", r"\bdidn'?t work\b",
    r"\bstill failing\b", r"\bstill broken\b", r"\bnot what i asked\b",
    r"\byou made a mistake\b", r"\bwrong again\b", r"\bfix it\b",
]
_CORRECTION_RE = re.compile("|".join(CORRECTION_PATTERNS), re.IGNORECASE)

# عبارات تدل على خطأ تقني في نص مخرجات.
ERROR_MARKERS = [
    "traceback (most recent call last)", "error:", "errno", "exception",
    "failed", "fatal:", "command not found", "no such file or directory",
    "permission denied", "syntaxerror", "typeerror", "valueerror",
    "segmentation fault", "timed out", "connection refused", "not found",
]

# عبارات خاصة بأخطاء الـ API / الحدود.
API_MARKERS = [
    "api error", "rate limit", "overloaded", "529", "500 internal",
    "request timed out", "context low", "usage limit",
]

# عبارات رفض صلاحية داخل Claude Code.
PERMISSION_MARKERS = [
    "permission to use", "requested permissions", "user denied",
    "operation not permitted", "blocked by hook", "not allowed",
]


def looks_like_correction(text: str) -> bool:
    """هل تبدو رسالتك تصحيحًا لخطأ ارتكبه كلود؟"""
    if not text:
        return False
    return bool(_CORRECTION_RE.search(text))


def _has(text_low: str, markers) -> bool:
    return any(marker in text_low for marker in markers)


def classify(text: str, flagged_error: bool = False) -> str:
    """يصنّف نص خطأ إلى أحد الأنواع في models.KINDS."""
    low = (text or "").lower()
    if _has(low, PERMISSION_MARKERS):
        return "permission"
    if _has(low, API_MARKERS):
        return "api_error"
    if flagged_error or _has(low, ERROR_MARKERS):
        return "tool_error"
    return "other"


def looks_like_error(text: str) -> bool:
    """هل يحتوي النص على أثر خطأ تقني؟"""
    low = (text or "").lower()
    return _has(low, ERROR_MARKERS) or _has(low, API_MARKERS) or _has(low, PERMISSION_MARKERS)


def severity_for(kind: str, text: str) -> str:
    """تقدير خطورة مبدئي؛ يبقى قابلًا للتعديل يدويًا في السجل."""
    low = (text or "").lower()
    if kind == "api_error":
        return "high" if "usage limit" in low or "rate limit" in low else "medium"
    if kind == "permission":
        return "low"
    if kind == "user_correction":
        return "high"
    if "traceback" in low or "fatal:" in low or "segmentation fault" in low:
        return "high"
    return "medium"


def summarize(text: str, limit: int = 160) -> str:
    """يستخرج سطرًا مختصرًا يصلح كعنوان للخطأ."""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    # نفضّل أول سطر يحوي أثر خطأ، وإلا فأول سطر غير فارغ.
    for line in lines:
        if looks_like_error(line):
            return line[:limit]
    return lines[0][:limit]

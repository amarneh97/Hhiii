"""فحص الإيميل مقابل Have I Been Pwned: التسريبات، اللصقات (pastes)، وسجلات برامج سرقة البيانات.

يتطلب مفتاح HIBP API (متغير البيئة HIBP_API_KEY) — المفتاح مدفوع ومرتبط بحساب،
ولذلك تسمح شروط الخدمة باستخدامه لفحص عناوينك أنت.
"""
import time

import requests

from findings import Finding

API_BASE = "https://haveibeenpwned.com/api/v3"
USER_AGENT = "self-osint-cli"

# HIBP يعيد 429 مع رأس Retry-After عند تجاوز حد الطلبات؛ نحترمه بدل الفشل الفوري.
MAX_RETRIES = 3

# فئات بيانات تستدعي تحذيرًا أشد عند ظهورها في تسريب.
SENSITIVE_CLASSES = {
    "Passwords",
    "Password hints",
    "Security questions and answers",
    "Credit cards",
    "Bank account numbers",
    "Government issued IDs",
    "Passport numbers",
    "Social security numbers",
    "Partial credit card data",
    "Auth tokens",
    "Private messages",
}


class HibpError(RuntimeError):
    pass


def _get(path: str, api_key: str, params: dict = None) -> object:
    """طلب GET إلى HIBP. يعيد None عند 404 (لا نتائج) ويرفع HibpError عند بقية الأخطاء."""
    headers = {"hibp-api-key": api_key, "user-agent": USER_AGENT}
    url = f"{API_BASE}/{path}"
    for attempt in range(MAX_RETRIES):
        response = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            wait = int(response.headers.get("retry-after", 2 ** attempt))
            time.sleep(min(wait, 60))
            continue
        if response.status_code == 401:
            raise HibpError("مفتاح HIBP غير صالح أو منتهي الصلاحية (401).")
        if response.status_code == 403:
            raise HibpError("طلب مرفوض من HIBP (403) — تحقق من المفتاح والـ user-agent.")
        raise HibpError(f"خطأ من HIBP ({response.status_code}): {response.text[:200]}")
    raise HibpError("تجاوز حد الطلبات في HIBP بعد عدة محاولات.")


def _breach_severity(breach: dict) -> str:
    """يرفع الخطورة حسب حساسية البيانات المسرَّبة وحداثة التسريب."""
    classes = set(breach.get("DataClasses") or [])
    if classes & {"Passwords", "Credit cards", "Bank account numbers", "Government issued IDs"}:
        return "critical"
    if classes & SENSITIVE_CLASSES:
        return "high"
    return "medium"


def check_email(email: str, api_key: str) -> list:
    """يعيد قائمة Finding عن تسريبات ولصقات وسجلات سرقة تخص الإيميل."""
    findings = []

    breaches = _get(f"breachedaccount/{email}", api_key, {"truncateResponse": "false"}) or []
    for breach in breaches:
        classes = ", ".join(breach.get("DataClasses") or [])
        findings.append(
            Finding(
                source="hibp",
                target=email,
                title=f"تسريب: {breach.get('Title') or breach.get('Name')}",
                detail=(
                    f"تاريخ التسريب: {breach.get('BreachDate', 'غير معروف')} — "
                    f"عدد الحسابات: {breach.get('PwnCount', 0):,} — "
                    f"البيانات المسرَّبة: {classes or 'غير محددة'}"
                ),
                severity=_breach_severity(breach),
                url=f"https://haveibeenpwned.com/PwnedWebsites#{breach.get('Name', '')}",
                advice=(
                    "غيّر كلمة المرور لهذا الموقع وأي موقع استُخدمت فيه نفس الكلمة، وفعّل المصادقة الثنائية."
                    if "Passwords" in (breach.get("DataClasses") or [])
                    else "راجع الحساب وفعّل المصادقة الثنائية إن كان لا يزال مستخدمًا."
                ),
                data={
                    "name": breach.get("Name"),
                    "breach_date": breach.get("BreachDate"),
                    "pwn_count": breach.get("PwnCount"),
                    "data_classes": breach.get("DataClasses"),
                    "is_verified": breach.get("IsVerified"),
                },
            )
        )

    pastes = _get(f"pasteaccount/{email}", api_key) or []
    for paste in pastes:
        findings.append(
            Finding(
                source="hibp",
                target=email,
                title=f"لصقة عامة على {paste.get('Source', 'مصدر غير معروف')}",
                detail=(
                    f"العنوان: {paste.get('Title') or 'بدون عنوان'} — "
                    f"التاريخ: {paste.get('Date') or 'غير معروف'} — "
                    f"عدد الإيميلات في اللصقة: {paste.get('EmailCount', 0):,}"
                ),
                severity="high",
                url=f"https://pastebin.com/{paste.get('Id')}" if paste.get("Source") == "Pastebin" else "",
                advice="اللصقات غالبًا تنشر إيميلات مع كلمات مرور — غيّر كلمة المرور المرتبطة فورًا.",
                data={"source": paste.get("Source"), "id": paste.get("Id"), "date": paste.get("Date")},
            )
        )

    # سجلات stealer logs متاحة فقط لبعض اشتراكات HIBP؛ نتجاهل فشلها بهدوء.
    try:
        domains = _get(f"stealerlogsbyemail/{email}", api_key) or []
    except HibpError:
        domains = []
    if domains:
        findings.append(
            Finding(
                source="hibp",
                target=email,
                title="ظهور الإيميل في سجلات برامج سرقة بيانات (stealer logs)",
                detail="مواقع سُجّل الدخول إليها بهذا الإيميل من جهاز مصاب: " + ", ".join(domains[:20]),
                severity="critical",
                url="https://haveibeenpwned.com/",
                advice=(
                    "افحص أجهزتك ببرنامج مكافحة برمجيات خبيثة، غيّر كلمات المرور لهذه المواقع من جهاز نظيف، "
                    "وأنهِ كل الجلسات النشطة."
                ),
                data={"domains": domains},
            )
        )

    return findings

"""فحص ما يكشفه حساب X (تويتر) العام لزائر غير مسجَّل الدخول.

X يحجب قراءة الملفات الشخصية آليًا دون تسجيل دخول، لذا لا تحاول هذه الوحدة
الالتفاف على ذلك. تستخدم مصدرين علنيّين فقط:

1. واجهة oEmbed الرسمية (publish.twitter.com) — تعيد الاسم المعروض للحسابات القائمة.
2. صفحة الملف نفسها — لتأكيد الوجود من رمز الحالة فقط.

حين يحجب X كليهما تُبلّغ الأداة بذلك صراحةً بدل التخمين.
"""
import requests

from findings import Finding

PROFILE_URL = "https://x.com/{username}"
OEMBED_URL = "https://publish.twitter.com/oembed"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
BLOCKED_STATUSES = (401, 402, 403, 429)


def interpret_oembed(payload: dict) -> dict:
    """يستخرج الاسم المعروض والمعرّف من رد oEmbed. دالة نقية — تُختبَر بلا شبكة."""
    result = {"exists": False, "display_name": "", "username": ""}
    if not isinstance(payload, dict):
        return result

    author = (payload.get("author_name") or "").strip()
    author_url = (payload.get("author_url") or "").strip()
    if author or author_url:
        result["exists"] = True
        result["display_name"] = author
        if author_url:
            result["username"] = author_url.rstrip("/").rsplit("/", 1)[-1]
    return result


def _fetch_oembed(username: str, timeout: int) -> dict:
    try:
        response = requests.get(
            OEMBED_URL,
            params={"url": PROFILE_URL.format(username=username), "omit_script": "true"},
            timeout=timeout,
            headers={"user-agent": USER_AGENT},
        )
    except requests.RequestException:
        return {}
    if response.status_code != 200:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def check_username(username: str, timeout: int = 15) -> list:
    """يعيد نتائج عن حساب X، أو يرفع RuntimeError حين يحجب X كل المصادر العلنية."""
    url = PROFILE_URL.format(username=username)
    profile = interpret_oembed(_fetch_oembed(username, timeout))

    page_status = None
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"user-agent": USER_AGENT, "accept-language": "en-US,en;q=0.9"},
            allow_redirects=True,
        )
        page_status = response.status_code
    except requests.RequestException:
        pass

    if page_status == 404 and not profile["exists"]:
        return []

    if not profile["exists"] and (page_status is None or page_status in BLOCKED_STATUSES):
        raise RuntimeError(
            f"X حجب القراءة الآلية (HTTP {page_status}) ولم تُرجع واجهة oEmbed بيانات. "
            f"افتح {url} في متصفح غير مسجَّل الدخول لترى ما يظهر للغرباء."
        )

    exposed = []
    if profile.get("display_name"):
        exposed.append(f"الاسم المعروض: {profile['display_name']}")
    if profile.get("username"):
        exposed.append(f"المعرّف: @{profile['username']}")

    return [
        Finding(
            source="x",
            target=username,
            title="حساب X عام مرتبط باسم المستخدم",
            detail=(
                " | ".join(exposed)
                if exposed
                else "الحساب موجود، لكن X لا يتيح قراءة تفاصيله آليًا دون تسجيل دخول."
            ),
            # اسم معروض حقيقي يربط المعرّف بهويتك؛ مجرد الوجود أقل خطورة.
            severity="medium" if profile.get("display_name") else "low",
            url=url,
            advice=(
                "راجع الملف من متصفح غير مسجَّل الدخول: الاسم، النبذة، الموقع الجغرافي، "
                "وتاريخ الانضمام كلها ظاهرة للجميع. أزل ما لا تريد ربطه بهويتك."
            ),
            data={k: v for k, v in profile.items() if v not in ("", None, False)},
        )
    ]

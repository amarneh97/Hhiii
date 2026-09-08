"""فحص ما يكشفه ملف إنستغرام العام لزائر غير مسجَّل الدخول.

يُقرأ ما تضعه إنستغرام نفسها في وسوم Open Graph داخل صفحة الملف — وهي البيانات
التي يراها أي رابط معاينة (Slack، واتساب، تويتر) عند لصق رابط حسابك. لا تسجيل
دخول ولا واجهات خاصة: ما تراه هذه الدالة هو حرفيًا ما يراه أي غريب.
"""
import re

import requests

from findings import Finding

PROFILE_URL = "https://www.instagram.com/{username}/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# نلتقط كل وسم meta كاملًا أولًا، ثم نقرأ سماته من داخله فقط. التقاط المحتوى
# بنمط واحد ممتد عبر الوسوم يجعل التعبير يقفز من وسم إلى آخر ويعيد نصًا مخلوطًا.
_META_TAG = re.compile(r"<meta\s[^>]*>", re.I)
_ATTR = r'{name}\s*=\s*["\']([^"\']*)["\']'

# "1,234 Followers, 567 Following, 89 Posts - See Instagram photos and videos from ..."
_COUNTS = re.compile(
    r"([\d,.KMkm]+)\s+Followers?,\s*([\d,.KMkm]+)\s+Following,\s*([\d,.KMkm]+)\s+Posts?",
    re.I,
)
# "الاسم (@handle) • Instagram photos and videos"
_TITLE_NAME = re.compile(r"^(.*?)\s*\(@([^)]+)\)")


def _meta(html: str, prop: str) -> str:
    """يستخرج محتوى وسم meta بأي ترتيب للسمات (property قبل content أو بعده)."""
    for tag in _META_TAG.findall(html):
        key = re.search(_ATTR.format(name="(?:property|name)"), tag, re.I)
        if not key or key.group(1).strip().lower() != prop.lower():
            continue
        content = re.search(_ATTR.format(name="content"), tag, re.I)
        if content:
            return content.group(1).strip()
    return ""


def parse_profile_html(html: str) -> dict:
    """يحوّل صفحة الملف العام إلى حقول منظَّمة. دالة نقية — تُختبَر بلا شبكة."""
    title = _meta(html, "og:title")
    description = _meta(html, "og:description")

    profile = {
        "exists": bool(title or description),
        "full_name": "",
        "username": "",
        "followers": "",
        "following": "",
        "posts": "",
        "bio": "",
        "is_private": None,
        "is_verified": False,
        "external_url": "",
        "has_profile_photo": bool(_meta(html, "og:image")),
    }

    name_match = _TITLE_NAME.search(title)
    if name_match:
        profile["full_name"] = name_match.group(1).strip()
        profile["username"] = name_match.group(2).strip()

    counts = _COUNTS.search(description)
    if counts:
        profile["followers"], profile["following"], profile["posts"] = counts.groups()

    # النبذة تأتي بعد الشرطة في وصف Open Graph حين تكون موجودة.
    if description and ":" in description:
        tail = description.split(":", 1)[1].strip().strip('"')
        # نتجاهل النص الترويجي الثابت الذي تضعه إنستغرام حين لا توجد نبذة.
        if tail and "See Instagram photos" not in tail:
            profile["bio"] = tail

    if '"is_private":true' in html or "This account is private" in html:
        profile["is_private"] = True
    elif '"is_private":false' in html:
        profile["is_private"] = False

    if '"is_verified":true' in html:
        profile["is_verified"] = True

    external = re.search(r'"external_url":"(.*?)"', html)
    if external and external.group(1):
        profile["external_url"] = external.group(1).replace("\\/", "/")

    return profile


def build_findings(username: str, profile: dict) -> list:
    """يحوّل الحقول المستخرَجة إلى نتائج مرتَّبة حسب الخطورة."""
    if not profile.get("exists"):
        return []

    url = PROFILE_URL.format(username=username)
    findings = []

    exposed = []
    if profile.get("full_name"):
        exposed.append(f"الاسم المعروض: {profile['full_name']}")
    if profile.get("bio"):
        exposed.append(f"النبذة: {profile['bio']}")
    if profile.get("external_url"):
        exposed.append(f"رابط خارجي: {profile['external_url']}")
    if profile.get("followers"):
        exposed.append(
            f"المتابعون: {profile['followers']} | يتابع: {profile['following']} | المنشورات: {profile['posts']}"
        )
    if profile.get("has_profile_photo"):
        exposed.append("صورة شخصية ظاهرة")

    if exposed:
        # الاسم الحقيقي أو رابط خارجي يربط الحساب بهويتك خارج المنصة.
        links_identity = bool(profile.get("full_name") or profile.get("external_url"))
        findings.append(
            Finding(
                source="instagram",
                target=username,
                title="بيانات ظاهرة في ملف إنستغرام لأي زائر غير مسجَّل",
                detail=" | ".join(exposed),
                severity="medium" if links_identity else "low",
                url=url,
                advice=(
                    "هذه الحقول تظهر لأي شخص ولمعاينات الروابط حتى لو كان الحساب خاصًا. "
                    "أزل الاسم الحقيقي أو الرابط الخارجي إن لم ترد ربط الحساب بهويتك."
                ),
                data={k: v for k, v in profile.items() if v not in ("", None)},
            )
        )

    if profile.get("is_private") is False:
        findings.append(
            Finding(
                source="instagram",
                target=username,
                title="حساب إنستغرام عام (غير خاص)",
                detail="كل المنشورات والقصص المؤرشفة متاحة لأي شخص دون متابعة أو تسجيل دخول.",
                severity="medium",
                url=url,
                advice="حوّل الحساب إلى خاص من الإعدادات إن لم يكن حسابًا عامًا بغرض مقصود.",
                data={"is_private": False},
            )
        )
    elif profile.get("is_private") is True:
        findings.append(
            Finding(
                source="instagram",
                target=username,
                title="حساب إنستغرام خاص",
                detail="المنشورات محمية، لكن الاسم والصورة والنبذة تبقى ظاهرة للجميع.",
                severity="info",
                url=url,
                advice="لا إجراء مطلوب على المنشورات — راجع فقط ما يظهر في الملف نفسه.",
                data={"is_private": True},
            )
        )

    return findings


def check_username(username: str, timeout: int = 15) -> list:
    """يجلب الملف العام ويحوّله إلى نتائج. يرفع RuntimeError عند حجب المنصة."""
    try:
        response = requests.get(
            PROFILE_URL.format(username=username),
            timeout=timeout,
            headers={"user-agent": USER_AGENT, "accept-language": "en-US,en;q=0.9"},
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"تعذر الوصول إلى إنستغرام: {type(exc).__name__}") from exc

    if response.status_code == 404:
        return []
    if response.status_code in (401, 403, 429):
        raise RuntimeError(
            f"إنستغرام حجب الطلب (HTTP {response.status_code}). "
            f"شائع من الشبكات السحابية — شغّل الأداة من جهازك، أو افتح "
            f"{PROFILE_URL.format(username=username)} في متصفح غير مسجَّل الدخول."
        )
    if response.status_code != 200:
        raise RuntimeError(f"رد غير متوقع من إنستغرام (HTTP {response.status_code}).")

    return build_findings(username, parse_profile_html(response.text))

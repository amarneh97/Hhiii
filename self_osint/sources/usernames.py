"""فحص وجود اسم مستخدم على منصات عامة — مع معايرة ذاتية ضد الإيجابيات الكاذبة.

الفكرة: اسم المستخدم الموحّد عبر المنصات يسمح لأي شخص بربط حساباتك ببعضها.
الفحص يعتمد على طلب صفحة الملف العام فقط — لا تسجيل دخول ولا التفاف على حماية.

المشكلة التي تعالجها المعايرة: كثير من المنصات تُعيد HTTP 200 مع صفحة "غير موجود"
(soft-404)، فاعتبار كل 200 حسابًا موجودًا ينتج إيجابيات كاذبة بالكامل. لذلك تُفحص
كل منصة مرتين: مرة باسم المستخدم الهدف، ومرة باسم عشوائي مؤكَّد عدم وجوده (control).
لا يُعتبر الحساب موجودًا إلا إذا ميّزت المنصة بين الاثنين فعليًا.
"""
import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from findings import Finding

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# absence_text: نص يظهر في صفحة "غير موجود" على منصات تُعيد 200 دائمًا.
PLATFORMS = [
    {"name": "GitHub", "url": "https://github.com/{username}"},
    {"name": "GitLab", "url": "https://gitlab.com/{username}"},
    {"name": "X (Twitter)", "url": "https://x.com/{username}"},
    {"name": "Instagram", "url": "https://www.instagram.com/{username}/"},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{username}", "absence_text": "Couldn't find this account"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{username}/about.json"},
    {"name": "Telegram", "url": "https://t.me/{username}", "absence_text": "tgme_page_not_found"},
    {"name": "YouTube", "url": "https://www.youtube.com/@{username}"},
    {"name": "Medium", "url": "https://medium.com/@{username}"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{username}/"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{username}"},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{username}", "absence_text": "The specified profile could not be found"},
    {"name": "Keybase", "url": "https://keybase.io/{username}"},
    {"name": "Docker Hub", "url": "https://hub.docker.com/v2/users/{username}/"},
    {"name": "PyPI", "url": "https://pypi.org/user/{username}/"},
    {"name": "npm", "url": "https://www.npmjs.com/~{username}"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{username}"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{username}"},
    {"name": "Behance", "url": "https://www.behance.net/{username}"},
]

BLOCKED_STATUSES = (401, 403, 429, 451)


def _random_username() -> str:
    """اسم مستخدم عشوائي طويل — يُفترض عدم وجوده على أي منصة."""
    body = "".join(random.choices(string.ascii_lowercase + string.digits, k=18))
    return f"zz{body}qx"


def _probe(url: str, timeout: int) -> dict:
    """طلب واحد. يعيد الحالة وطول الصفحة، أو خطأ الشبكة."""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"user-agent": USER_AGENT, "accept-language": "en-US,en;q=0.9"},
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return {"error": type(exc).__name__}
    return {"status": response.status_code, "text": response.text, "length": len(response.text)}


def _classify(platform: dict, target: dict, control: dict) -> tuple:
    """يقارن استجابة الهدف باستجابة الاسم العشوائي.

    يعيد (exists, note) حيث exists إما True أو False أو None عند تعذر الحسم.
    القاعدة: لا يُعلن الوجود إلا إذا أثبتت المنصة قدرتها على نفي اسم غير موجود.
    """
    if "error" in target:
        return None, f"تعذر الفحص: {target['error']}"
    if target["status"] in BLOCKED_STATUSES:
        return None, f"المنصة حجبت الطلب (HTTP {target['status']}) — افحص الرابط يدويًا"
    if target["status"] == 404:
        return False, ""
    if target["status"] != 200:
        return None, f"رد غير متوقع (HTTP {target['status']})"

    absence_text = platform.get("absence_text")
    if absence_text and absence_text in target["text"]:
        return False, ""

    # المنصة ردّت 200 على الهدف — هل ترد 404 على اسم غير موجود؟
    if "error" in control or control.get("status") in BLOCKED_STATUSES:
        return None, "تعذّرت معايرة المنصة — افحص الرابط يدويًا"
    if control.get("status") == 404:
        return True, ""
    if absence_text and control.get("status") == 200 and absence_text in control["text"]:
        # المنصة تُميّز عبر النص، والهدف لا يحمل نص الغياب ⇒ موجود.
        return True, ""

    # المنصة تُعيد 200 للاسمين ولا نملك علامة غياب موثوقة ⇒ لا نخمّن.
    return None, "المنصة تُعيد 200 حتى للحسابات غير الموجودة — افحص الرابط يدويًا"


def _check_one(platform: dict, username: str, control_username: str, timeout: int) -> dict:
    url = platform["url"].format(username=username)
    target = _probe(url, timeout)
    # المعايرة مطلوبة فقط عندما يردّ الهدف 200 دون علامة غياب حاسمة.
    control = {}
    if target.get("status") == 200:
        control = _probe(platform["url"].format(username=control_username), timeout)
    exists, note = _classify(platform, target, control)
    return {"platform": platform["name"], "url": url, "exists": exists, "note": note}


def check_username(username: str, timeout: int = 15, workers: int = 8, platforms: list = None) -> list:
    """يفحص اسم المستخدم على كل المنصات ويعيد Finding لكل حساب مؤكَّد أو غير حاسم."""
    platforms = platforms if platforms is not None else PLATFORMS
    control_username = _random_username()
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_check_one, p, username, control_username, timeout) for p in platforms
        ]
        for future in as_completed(futures):
            results.append(future.result())

    findings = []
    found = [r for r in results if r["exists"] is True]
    unknown = [r for r in results if r["exists"] is None]

    for result in sorted(found, key=lambda r: r["platform"]):
        findings.append(
            Finding(
                source="usernames",
                target=username,
                title=f"حساب عام باسم المستخدم على {result['platform']}",
                detail="الملف الشخصي متاح للعموم على الرابط أدناه.",
                severity="low",
                url=result["url"],
                advice="راجع ما يعرضه هذا الملف علنًا (اسم حقيقي، صورة، موقع، إيميل).",
                data={"platform": result["platform"]},
            )
        )

    # ربط الهوية عبر منصات متعددة هو الخطر الحقيقي، وليس أي حساب بمفرده.
    if len(found) >= 3:
        findings.append(
            Finding(
                source="usernames",
                target=username,
                title=f"اسم المستخدم نفسه مستخدَم على {len(found)} منصات",
                detail=(
                    "تكرار الاسم يسمح بربط حساباتك ببعضها ببحث واحد: "
                    + ", ".join(sorted(r["platform"] for r in found))
                ),
                severity="medium",
                advice=(
                    "استخدم أسماء مستخدمين مختلفة للحسابات التي لا تريد ربطها بهويتك المهنية أو العامة."
                ),
                data={"platforms": sorted(r["platform"] for r in found)},
            )
        )

    if unknown:
        findings.append(
            Finding(
                source="usernames",
                target=username,
                title=f"{len(unknown)} منصات تعذّر حسمها آليًا",
                detail="; ".join(f"{r['platform']}: {r['note']}" for r in unknown),
                severity="info",
                advice="افتح روابط هذه المنصات يدويًا للتأكد — الفحص الآلي لا يستطيع الجزم هنا.",
                data={"platforms": [r["platform"] for r in unknown]},
            )
        )

    return findings

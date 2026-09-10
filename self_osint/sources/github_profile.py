"""فحص ما يكشفه حسابك العام على GitHub — عبر الـ API العامة فقط (بدون توثيق)."""
import requests

from findings import Finding

API = "https://api.github.com"
HEADERS = {"user-agent": "self-osint-cli", "accept": "application/vnd.github+json"}


def _get(path: str, timeout: int, token: str = ""):
    headers = dict(HEADERS)
    if token:
        headers["authorization"] = f"Bearer {token}"
    response = requests.get(f"{API}/{path}", headers=headers, timeout=timeout)
    if response.status_code == 404:
        return None
    if response.status_code == 403:
        raise RuntimeError("تجاوز حد طلبات GitHub العامة — أعد المحاولة لاحقًا أو مرّر GITHUB_TOKEN.")
    response.raise_for_status()
    return response.json()


def check_user(username: str, timeout: int = 15, token: str = "") -> list:
    """يعيد Finding عن الحقول العامة في الملف وعن إيميلات مكشوفة في commits عامة."""
    findings = []
    profile = _get(f"users/{username}", timeout, token)
    if not profile:
        return findings

    public_fields = {
        "الاسم": profile.get("name"),
        "الإيميل": profile.get("email"),
        "الشركة": profile.get("company"),
        "الموقع الجغرافي": profile.get("location"),
        "الموقع الإلكتروني": profile.get("blog"),
        "حساب تويتر": profile.get("twitter_username"),
    }
    exposed = {k: v for k, v in public_fields.items() if v}
    if exposed:
        # إيميل معلن في الملف العام يُحصد آليًا من قِبل السبام وحملات التصيّد.
        severity = "medium" if profile.get("email") else "low"
        findings.append(
            Finding(
                source="github",
                target=username,
                title="بيانات شخصية معلنة في ملف GitHub العام",
                detail=" | ".join(f"{k}: {v}" for k, v in exposed.items()),
                severity=severity,
                url=profile.get("html_url", ""),
                advice="أزل ما لا تريد نشره من إعدادات الملف الشخصي، وخصوصًا الإيميل والموقع الجغرافي.",
                data=exposed,
            )
        )

    events = _get(f"users/{username}/events/public", timeout, token) or []
    emails = {}
    for event in events:
        for commit in (event.get("payload") or {}).get("commits") or []:
            author = commit.get("author") or {}
            email = (author.get("email") or "").lower()
            if email and "noreply" not in email:
                emails.setdefault(email, set()).add(event.get("repo", {}).get("name", ""))

    for email, repos in sorted(emails.items()):
        findings.append(
            Finding(
                source="github",
                target=username,
                title=f"إيميل مكشوف في نشاط GitHub العام: {email}",
                detail="ظهر في commits على: " + ", ".join(sorted(r for r in repos if r)),
                severity="medium",
                url=f"https://github.com/{username}",
                advice=(
                    "فعّل Settings → Emails → Keep my email address private "
                    "و Block command line pushes that expose my email."
                ),
                data={"email": email, "repos": sorted(repos)},
            )
        )

    return findings

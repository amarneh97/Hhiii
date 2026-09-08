"""فحص مستودع Git محلي بحثًا عن بيانات شخصية مسرَّبة في السجل.

أكثر تسريب شائع عند المطورين: إيميلك الشخصي الحقيقي مثبَّت في كل commit دفعته
إلى مستودع عام — ويبقى هناك حتى لو غيّرت إعدادات Git لاحقًا.
"""
import re
import subprocess

from findings import Finding

# عناوين لا تكشف هوية: noreply من GitHub/GitLab أو حسابات آلية.
NOREPLY_PATTERNS = [
    re.compile(r"@users\.noreply\.github\.com$", re.I),
    re.compile(r"^noreply@", re.I),
    re.compile(r"@noreply\.", re.I),
]

SECRET_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env$", re.I),
    re.compile(r"(^|/)\.env\.(local|production|prod)$", re.I),
    re.compile(r"\.pem$", re.I),
    re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$", re.I),
    re.compile(r"(^|/)credentials(\.json)?$", re.I),
    re.compile(r"(^|/)\.npmrc$", re.I),
    re.compile(r"(^|/)\.pypirc$", re.I),
    re.compile(r"(^|/)service[-_]?account.*\.json$", re.I),
]


def _git(args: list, repo_path: str) -> str:
    """ينفّذ أمر git في المستودع ويعيد المخرجات النصية."""
    result = subprocess.run(
        ["git", "-C", repo_path] + args,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"فشل الأمر: git {' '.join(args)}")
    return result.stdout


def _is_noreply(email: str) -> bool:
    return any(pattern.search(email) for pattern in NOREPLY_PATTERNS)


def scan_repo(repo_path: str, own_emails: list = None) -> list:
    """يفحص سجل المستودع: إيميلات مكشوفة وملفات أسرار سبق تتبّعها."""
    own_emails = [e.lower() for e in (own_emails or [])]
    findings = []

    authors = _git(["log", "--all", "--format=%an <%ae>"], repo_path)
    committers = _git(["log", "--all", "--format=%cn <%ce>"], repo_path)

    identities = {}
    for line in (authors + committers).splitlines():
        line = line.strip()
        if not line or "<" not in line:
            continue
        name, _, email = line.rpartition("<")
        email = email.rstrip(">").strip().lower()
        if not email:
            continue
        identities.setdefault(email, set()).add(name.strip())

    for email, names in sorted(identities.items()):
        if _is_noreply(email):
            continue
        # إيميل يخصّك أنت مكشوف = خطورة أعلى من إيميل مساهم آخر (وهذا فحص ذاتي).
        is_own = email in own_emails or not own_emails
        findings.append(
            Finding(
                source="git-history",
                target=repo_path,
                title=f"إيميل مكشوف في سجل الـ commits: {email}",
                detail=f"مرتبط بالأسماء: {', '.join(sorted(n for n in names if n)) or 'غير محدد'}",
                severity="medium" if is_own else "low",
                advice=(
                    "إن كان المستودع عامًا، فعّل خيار إخفاء الإيميل في GitHub واضبط "
                    "git config user.email على عنوان users.noreply.github.com. "
                    "السجل القديم يبقى مكشوفًا ما لم تُعِد كتابته."
                ),
                data={"email": email, "names": sorted(names)},
            )
        )

    tracked = _git(["log", "--all", "--name-only", "--format="], repo_path)
    flagged = set()
    for path in tracked.splitlines():
        path = path.strip()
        if not path:
            continue
        if any(pattern.search(path) for pattern in SECRET_FILE_PATTERNS):
            flagged.add(path)

    for path in sorted(flagged):
        findings.append(
            Finding(
                source="git-history",
                target=repo_path,
                title=f"ملف حسّاس ظهر في سجل المستودع: {path}",
                detail="الملف مُتتبَّع في تاريخ الـ commits — قد يحتوي مفاتيح أو كلمات مرور حتى لو حُذف لاحقًا.",
                severity="high",
                advice=(
                    "اعتبر أي سر بداخله مكشوفًا: أبطِله وأصدر بديلًا، ثم أزل الملف من التاريخ "
                    "(git filter-repo) وأضفه إلى .gitignore."
                ),
                data={"path": path},
            )
        )

    return findings

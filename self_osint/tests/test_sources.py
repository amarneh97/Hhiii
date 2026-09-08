"""اختبارات منطق المصادر (بدون طلبات شبكة حقيقية)."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.gravatar import email_hashes  # noqa: E402
from sources.git_history import _is_noreply, scan_repo  # noqa: E402
from sources.hibp import _breach_severity  # noqa: E402


def test_gravatar_hash_normalizes_case_and_spaces():
    a = email_hashes("  Me@Example.COM ")
    b = email_hashes("me@example.com")
    assert a == b
    # قيمة MD5 المعروفة لـ me@example.com للتأكد من مطابقة صيغة Gravatar.
    assert a["md5"] == "2e0d5407ce8609047b8255c50405d7b1"
    assert len(a["sha256"]) == 64


def test_noreply_detection():
    assert _is_noreply("128783827+user@users.noreply.github.com")
    assert _is_noreply("noreply@anthropic.com")
    assert not _is_noreply("real.person@gmail.com")


def test_breach_severity_escalates_with_passwords():
    assert _breach_severity({"DataClasses": ["Email addresses", "Passwords"]}) == "critical"
    assert _breach_severity({"DataClasses": ["Email addresses", "Private messages"]}) == "high"
    assert _breach_severity({"DataClasses": ["Email addresses"]}) == "medium"
    assert _breach_severity({}) == "medium"


def _init_repo(path, email, name="Tester"):
    subprocess.run(["git", "init", "-q", path], check=True)
    for key, value in (("user.email", email), ("user.name", name)):
        subprocess.run(["git", "-C", path, "config", key, value], check=True)


def test_scan_repo_flags_real_email_but_not_noreply():
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, "real.person@gmail.com")
        open(os.path.join(repo, "a.txt"), "w").close()
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)

        findings = scan_repo(repo, own_emails=["real.person@gmail.com"])
        emails = [f.data.get("email") for f in findings if f.data.get("email")]
        assert "real.person@gmail.com" in emails

    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, "1+user@users.noreply.github.com")
        open(os.path.join(repo, "a.txt"), "w").close()
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)

        findings = scan_repo(repo)
        assert [f for f in findings if f.data.get("email")] == []


def test_scan_repo_flags_tracked_secret_file():
    with tempfile.TemporaryDirectory() as repo:
        _init_repo(repo, "1+user@users.noreply.github.com")
        with open(os.path.join(repo, ".env"), "w") as handle:
            handle.write("API_KEY=secret\n")
        subprocess.run(["git", "-C", repo, "add", "-f", ".env"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "oops"], check=True)

        findings = scan_repo(repo)
        assert any(f.data.get("path") == ".env" and f.severity == "high" for f in findings)


# ---- منطق تصنيف وجود اسم المستخدم (بدون شبكة) ----

from sources.usernames import _classify  # noqa: E402

PLAIN = {"name": "Plain", "url": "https://x/{username}"}
MARKED = {"name": "Marked", "url": "https://x/{username}", "absence_text": "not_found_marker"}


def test_hard_404_means_absent():
    assert _classify(PLAIN, {"status": 404, "text": "", "length": 0}, {}) == (False, "")


def test_soft_404_platform_is_inconclusive_not_found():
    """المنصة تُعيد 200 للهدف وللاسم العشوائي ⇒ لا يجوز إعلان الوجود."""
    target = {"status": 200, "text": "page", "length": 4}
    control = {"status": 200, "text": "page", "length": 4}
    exists, note = _classify(PLAIN, target, control)
    assert exists is None and "يدويًا" in note


def test_real_404_platform_confirms_existence():
    target = {"status": 200, "text": "profile", "length": 7}
    control = {"status": 404, "text": "", "length": 0}
    assert _classify(PLAIN, target, control) == (True, "")


def test_absence_marker_detects_missing_account():
    target = {"status": 200, "text": "hello not_found_marker here", "length": 27}
    assert _classify(MARKED, target, {}) == (False, "")


def test_absence_marker_confirms_existence_on_soft_404_platform():
    target = {"status": 200, "text": "real profile", "length": 12}
    control = {"status": 200, "text": "not_found_marker", "length": 16}
    assert _classify(MARKED, target, control) == (True, "")


def test_blocked_status_is_inconclusive():
    for status in (401, 403, 429):
        exists, note = _classify(PLAIN, {"status": status, "text": "", "length": 0}, {})
        assert exists is None and str(status) in note


def test_network_error_is_inconclusive():
    exists, note = _classify(PLAIN, {"error": "ConnectTimeout"}, {})
    assert exists is None and "ConnectTimeout" in note


def test_uncalibratable_platform_is_inconclusive():
    target = {"status": 200, "text": "page", "length": 4}
    exists, note = _classify(PLAIN, target, {"status": 403, "text": "", "length": 0})
    assert exists is None and "معايرة" in note

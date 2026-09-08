"""اختبارات مصادر إنستغرام وX — تحليل نصوص محضَّرة، بلا أي طلب شبكة."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.instagram import build_findings, parse_profile_html  # noqa: E402
from sources.x_twitter import interpret_oembed  # noqa: E402

PUBLIC_HTML = '''
<meta property="og:title" content="Mohammad Amarneh (@some_user) &bull; Instagram photos and videos" />
<meta property="og:description" content="1,234 Followers, 567 Following, 89 Posts - See Instagram photos and videos from Mohammad Amarneh (@some_user)" />
<meta property="og:image" content="https://example.com/pic.jpg" />
<script>{"is_private":false,"is_verified":false,"external_url":"https:\\/\\/example.com\\/me"}</script>
'''

PRIVATE_HTML = '''
<meta content="Some Person (@priv_user) &bull; Instagram photos and videos" property="og:title" />
<meta content="10 Followers, 20 Following, 0 Posts - See Instagram photos and videos from Some Person (@priv_user)" property="og:description" />
<script>{"is_private":true}</script>
'''

EMPTY_HTML = "<html><body>nothing here</body></html>"


# ---- إنستغرام: التحليل ----

def test_parses_name_handle_and_counts():
    profile = parse_profile_html(PUBLIC_HTML)
    assert profile["exists"] is True
    assert profile["full_name"] == "Mohammad Amarneh"
    assert profile["username"] == "some_user"
    assert profile["followers"] == "1,234"
    assert profile["following"] == "567"
    assert profile["posts"] == "89"


def test_parses_privacy_and_external_url():
    assert parse_profile_html(PUBLIC_HTML)["is_private"] is False
    assert parse_profile_html(PUBLIC_HTML)["external_url"] == "https://example.com/me"
    assert parse_profile_html(PRIVATE_HTML)["is_private"] is True


def test_meta_tags_parse_with_attributes_in_either_order():
    """PRIVATE_HTML يضع content قبل property — يجب أن يُحلَّل بنفس الطريقة."""
    profile = parse_profile_html(PRIVATE_HTML)
    assert profile["full_name"] == "Some Person"
    assert profile["followers"] == "10"


def test_page_without_meta_tags_is_not_a_profile():
    assert parse_profile_html(EMPTY_HTML)["exists"] is False


def test_boilerplate_description_is_not_treated_as_bio():
    assert parse_profile_html(PUBLIC_HTML)["bio"] == ""


# ---- إنستغرام: النتائج ----

def test_nonexistent_profile_yields_no_findings():
    assert build_findings("ghost", parse_profile_html(EMPTY_HTML)) == []


def test_public_account_flagged_medium_with_both_findings():
    findings = build_findings("some_user", parse_profile_html(PUBLIC_HTML))
    titles = [f.title for f in findings]
    assert any("بيانات ظاهرة" in t for t in titles)
    assert any("عام (غير خاص)" in t for t in titles)
    assert all(f.severity == "medium" for f in findings)


def test_private_account_privacy_finding_is_info_only():
    findings = build_findings("priv_user", parse_profile_html(PRIVATE_HTML))
    privacy = [f for f in findings if "خاص" in f.title and "بيانات" not in f.title]
    assert len(privacy) == 1 and privacy[0].severity == "info"


def test_real_name_raises_severity_over_bare_profile():
    bare = {"exists": True, "has_profile_photo": True}
    named = {"exists": True, "has_profile_photo": True, "full_name": "Real Name"}
    assert build_findings("u", bare)[0].severity == "low"
    assert build_findings("u", named)[0].severity == "medium"


# ---- X ----

def test_oembed_with_author_marks_account_as_existing():
    result = interpret_oembed(
        {"author_name": "Mohammad", "author_url": "https://twitter.com/m_amarneh"}
    )
    assert result == {"exists": True, "display_name": "Mohammad", "username": "m_amarneh"}


def test_empty_or_malformed_oembed_is_not_an_account():
    for payload in ({}, None, [], {"html": "<blockquote/>"}):
        assert interpret_oembed(payload)["exists"] is False

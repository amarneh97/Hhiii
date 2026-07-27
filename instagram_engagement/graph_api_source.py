"""
جلب بيانات التفاعل عبر Instagram Graph API الرسمي.

يتطلب:
  - حساب Instagram Business أو Creator مرتبط بصفحة فيسبوك.
  - رمز وصول (Access Token) صالح بصلاحيات instagram_basic و
    instagram_manage_insights، صادر عن تطبيق مسجَّل في Meta for Developers.

هذا المسار هو الطريقة المدعومة رسميًا من إنستغرام، ويعمل فقط على الحسابات
التي يملكها/يديرها صاحب التوكن (لا يمكن استخدامه لجلب بيانات حسابات أخرى).
"""
import requests

from engagement import EngagementReport, PostStats

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class GraphAPIError(RuntimeError):
    pass


def _get(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    if resp.status_code != 200 or "error" in data:
        message = data.get("error", {}).get("message", resp.text)
        raise GraphAPIError(f"طلب Graph API فشل: {message}")
    return data


def fetch_engagement_report(
    ig_user_id: str,
    access_token: str,
    limit: int = 25,
) -> EngagementReport:
    """يبني تقرير تفاعل لحساب Instagram Business/Creator عبر Graph API."""
    account = _get(
        f"{GRAPH_API_BASE}/{ig_user_id}",
        {"fields": "username,followers_count", "access_token": access_token},
    )

    media = _get(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        {
            "fields": "id,like_count,comments_count,timestamp,permalink",
            "limit": limit,
            "access_token": access_token,
        },
    )

    posts = [
        PostStats(
            post_id=item["id"],
            likes=item.get("like_count", 0) or 0,
            comments=item.get("comments_count", 0) or 0,
            timestamp=item.get("timestamp", ""),
            permalink=item.get("permalink", ""),
        )
        for item in media.get("data", [])
    ]

    return EngagementReport(
        account=account.get("username", ig_user_id),
        followers=account.get("followers_count", 0),
        posts=posts,
    )

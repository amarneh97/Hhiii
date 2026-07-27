"""
جلب بيانات التفاعل لحساب عام (Public) عبر مكتبة instaloader.

ملاحظات مهمة:
  - يعمل فقط مع الحسابات العامة (غير الخاصة).
  - يعتمد على واجهات إنستغرام غير الرسمية، لذا قد يخضع لحدود معدل الطلبات
    (rate limiting) أو يتوقف عن العمل إذا غيّرت إنستغرام بنيتها الداخلية.
  - استخدمه بمسؤولية وبما يتوافق مع شروط استخدام إنستغرام وسياسات الخصوصية،
    ولأغراض بحثية/تحليلية مشروعة فقط.
"""
import instaloader

from engagement import EngagementReport, PostStats


def fetch_engagement_report(
    username: str,
    limit: int = 25,
    session_username: str | None = None,
) -> EngagementReport:
    """يبني تقرير تفاعل لحساب عام عبر instaloader.

    session_username: اسم مستخدم لجلسة instaloader محفوظة مسبقًا (اختياري)،
    يُستخدم لرفع حدود معدل الطلبات عند الحاجة، وليس لتجاوز خصوصية الحسابات.
    """
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    if session_username:
        loader.load_session_from_file(session_username)

    profile = instaloader.Profile.from_username(loader.context, username)

    if profile.is_private:
        raise PermissionError(
            f"الحساب @{username} خاص، ولا يمكن جلب تفاعله بدون متابعته والحصول على إذن."
        )

    posts = []
    for post in profile.get_posts():
        posts.append(
            PostStats(
                post_id=post.shortcode,
                likes=post.likes,
                comments=post.comments,
                timestamp=post.date_utc.isoformat(),
                permalink=f"https://www.instagram.com/p/{post.shortcode}/",
                caption=post.caption or "",
            )
        )
        if len(posts) >= limit:
            break

    return EngagementReport(
        account=profile.username,
        followers=profile.followers,
        posts=posts,
    )


def fetch_comments(
    shortcode: str,
    limit: int = 20,
    session_username: str | None = None,
) -> list:
    """يجلب أحدث التعليقات على منشور عام معيّن عبر رمزه القصير (shortcode)."""
    loader = instaloader.Instaloader(download_pictures=False)
    if session_username:
        loader.load_session_from_file(session_username)

    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    comments = []
    for comment in post.get_comments():
        comments.append(
            {
                "id": str(comment.id),
                "username": comment.owner.username,
                "text": comment.text,
                "timestamp": comment.created_at_utc.isoformat(),
            }
        )
        if len(comments) >= limit:
            break
    return comments

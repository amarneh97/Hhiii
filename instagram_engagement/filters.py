"""بحث وفلترة نتائج التفاعل (منشورات وتعليقات)."""
from datetime import datetime
from typing import Iterable, Optional

from engagement import PostStats

_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")

SORT_KEYS = {
    "likes": lambda p: p.likes,
    "comments": lambda p: p.comments,
    "interactions": lambda p: p.interactions,
    "date": lambda p: p.timestamp,
}


def _parse_date(value: str) -> datetime:
    """يحوّل نص تاريخ (YYYY-MM-DD أو YYYY-MM-DDTHH:MM:SS) إلى datetime بدون منطقة زمنية."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"صيغة تاريخ غير مدعومة: {value!r} (استخدم YYYY-MM-DD)")


def _post_datetime(post: PostStats) -> Optional[datetime]:
    if not post.timestamp:
        return None
    try:
        return datetime.fromisoformat(post.timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def filter_posts(
    posts: Iterable[PostStats],
    keyword: Optional[str] = None,
    min_likes: Optional[int] = None,
    max_likes: Optional[int] = None,
    min_comments: Optional[int] = None,
    max_comments: Optional[int] = None,
    min_interactions: Optional[int] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> list:
    """يرجع المنشورات المطابقة لكل الشروط الممرَّرة (تُهمَل الشروط غير المحددة)."""
    since_dt = _parse_date(since) if since else None
    until_dt = _parse_date(until) if until else None
    keyword_lower = keyword.lower() if keyword else None

    matches = []
    for post in posts:
        if keyword_lower:
            haystack = f"{post.caption} {post.permalink} {post.post_id}".lower()
            if keyword_lower not in haystack:
                continue
        if min_likes is not None and post.likes < min_likes:
            continue
        if max_likes is not None and post.likes > max_likes:
            continue
        if min_comments is not None and post.comments < min_comments:
            continue
        if max_comments is not None and post.comments > max_comments:
            continue
        if min_interactions is not None and post.interactions < min_interactions:
            continue
        if since_dt is not None or until_dt is not None:
            post_dt = _post_datetime(post)
            if post_dt is None:
                continue
            if since_dt is not None and post_dt < since_dt:
                continue
            if until_dt is not None and post_dt > until_dt:
                continue
        matches.append(post)
    return matches


def sort_posts(posts: list, sort_by: str = "interactions", descending: bool = True) -> list:
    key = SORT_KEYS.get(sort_by)
    if key is None:
        raise ValueError(f"معيار ترتيب غير معروف: {sort_by!r}")
    return sorted(posts, key=key, reverse=descending)


def search_comments(
    comments: Iterable[dict],
    keyword: Optional[str] = None,
    author: Optional[str] = None,
) -> list:
    """يفلتر قائمة تعليقات (dict فيها username/text/...) بكلمة مفتاحية و/أو اسم مستخدم دقيق."""
    keyword_lower = keyword.lower() if keyword else None
    author_lower = author.lower() if author else None

    matches = []
    for comment in comments:
        if keyword_lower and keyword_lower not in (comment.get("text") or "").lower():
            continue
        if author_lower and author_lower != (comment.get("username") or "").lower():
            continue
        matches.append(comment)
    return matches

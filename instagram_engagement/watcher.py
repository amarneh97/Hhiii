"""مراقبة حساب إنستغرام واكتشاف تفاعل جديد (لايك/تعليق/متابعة) وإرسال إشعار."""
import time

from state_store import load_state, report_to_state, save_state


def run_check(fetch_report, fetch_comments, state_file: str, notifier) -> None:
    """يجري فحصًا واحدًا: يقارن الحالة الحالية بالحالة المحفوظة ويُصدر إشعارات للتفاعل الجديد."""
    report = fetch_report()
    previous = load_state(state_file)

    if previous is None:
        save_state(state_file, report_to_state(report))
        notifier.notify(
            "بدء المراقبة",
            f"تم تسجيل الحالة الأولية لحساب @{report.account} "
            f"({report.followers:,} متابع، {len(report.posts)} منشور). "
            "سيتم إرسال إشعارات بالتفاعل الجديد اعتبارًا من الفحص القادم.",
        )
        return

    # متابعون جدد
    followers_delta = report.followers - previous.get("followers", report.followers)
    if followers_delta > 0:
        notifier.notify(
            "متابعون جدد",
            f"حساب @{report.account} اكتسب {followers_delta} متابع جديد "
            f"(الإجمالي الآن {report.followers:,}).",
        )

    previous_posts = previous.get("posts", {})

    for post in report.posts:
        prev_post = previous_posts.get(post.post_id)

        if prev_post is None:
            # منشور جديد ظهر منذ آخر فحص: نسجّل حالته كخط أساس بدل اعتبار كل
            # لايكاته وتعليقاته الحالية "جديدة دفعة واحدة".
            notifier.notify(
                "منشور جديد",
                f"منشور جديد من @{report.account}: {post.permalink or post.post_id}",
            )
            continue

        like_delta = post.likes - prev_post.get("likes", 0)
        comment_delta = post.comments - prev_post.get("comments", 0)

        if like_delta > 0:
            notifier.notify(
                "لايكات جديدة",
                f"منشور {post.permalink or post.post_id} حصل على {like_delta} لايك جديد "
                f"(الإجمالي الآن {post.likes}).",
            )

        if comment_delta > 0:
            new_comments = []
            if fetch_comments is not None:
                try:
                    new_comments = fetch_comments(post.post_id, comment_delta)
                except Exception as exc:  # أفضل جهد: لا نوقف الفحص بسبب فشل جلب التعليقات
                    print(f"تعذّر جلب تفاصيل التعليقات الجديدة: {exc}")

            if new_comments:
                for comment in new_comments:
                    notifier.notify(
                        "تعليق جديد",
                        f"@{comment.get('username', '?')} علّق على "
                        f"{post.permalink or post.post_id}: {comment.get('text', '')}",
                    )
            else:
                notifier.notify(
                    "تعليقات جديدة",
                    f"منشور {post.permalink or post.post_id} حصل على {comment_delta} تعليق جديد "
                    f"(الإجمالي الآن {post.comments}).",
                )

    save_state(state_file, report_to_state(report))


def watch_loop(fetch_report, fetch_comments, state_file: str, notifier, interval: int) -> None:
    """يشغّل الفحص بشكل دوري كل `interval` ثانية حتى إيقافه (Ctrl+C)."""
    while True:
        try:
            run_check(fetch_report, fetch_comments, state_file, notifier)
        except Exception as exc:
            print(f"خطأ أثناء الفحص: {exc}")
        time.sleep(interval)

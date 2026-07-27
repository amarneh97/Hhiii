#!/usr/bin/env python3
"""
أداة سطر أوامر للبحث عن تفاعل حساب معيّن في إنستغرام وحساب معدل التفاعل.

أمثلة الاستخدام:

  # حساب تملكه/تديره (عبر Instagram Graph API الرسمي)
  python main.py graph-api --ig-user-id 17841400000000000 \
      --access-token "EAAG..." --limit 25

  # حساب عام (عبر instaloader)
  python main.py public --username some_public_account --limit 25
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from tabulate import tabulate

from engagement import EngagementReport

load_dotenv()


def print_report(report: EngagementReport) -> None:
    print(f"\nالحساب: @{report.account}")
    print(f"عدد المتابعين: {report.followers:,}")
    print(f"عدد المنشورات المحلَّلة: {len(report.posts)}")
    print(f"متوسط اللايكات: {report.avg_likes:.1f}")
    print(f"متوسط التعليقات: {report.avg_comments:.1f}")
    print(f"معدل التفاعل (Engagement Rate): {report.engagement_rate:.2f}%\n")

    rows = [
        [p.timestamp, p.likes, p.comments, p.interactions, p.permalink]
        for p in report.top_posts(5)
    ]
    print("أفضل 5 منشورات من حيث التفاعل:")
    print(
        tabulate(
            rows,
            headers=["التاريخ", "لايكات", "تعليقات", "إجمالي التفاعل", "الرابط"],
            tablefmt="github",
        )
    )


def run_graph_api(args: argparse.Namespace) -> EngagementReport:
    from graph_api_source import fetch_engagement_report

    access_token = args.access_token or os.getenv("IG_ACCESS_TOKEN")
    if not access_token:
        sys.exit("خطأ: يجب تمرير --access-token أو تعيين IG_ACCESS_TOKEN في البيئة.")

    return fetch_engagement_report(
        ig_user_id=args.ig_user_id,
        access_token=access_token,
        limit=args.limit,
    )


def run_public(args: argparse.Namespace) -> EngagementReport:
    from public_source import fetch_engagement_report

    return fetch_engagement_report(
        username=args.username,
        limit=args.limit,
        session_username=args.session_username,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="أداة تحليل معدل تفاعل حساب إنستغرام."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    graph_parser = subparsers.add_parser(
        "graph-api", help="حساب تملكه/تديره عبر Instagram Graph API الرسمي"
    )
    graph_parser.add_argument("--ig-user-id", required=True, help="معرّف حساب Instagram Business/Creator")
    graph_parser.add_argument("--access-token", help="رمز الوصول (أو عبر متغير البيئة IG_ACCESS_TOKEN)")
    graph_parser.add_argument("--limit", type=int, default=25, help="عدد المنشورات المراد تحليلها")
    graph_parser.set_defaults(func=run_graph_api)

    public_parser = subparsers.add_parser(
        "public", help="حساب عام (Public) عبر بيانات إنستغرام المتاحة للعامة"
    )
    public_parser.add_argument("--username", required=True, help="اسم المستخدم في إنستغرام")
    public_parser.add_argument("--limit", type=int, default=25, help="عدد المنشورات المراد تحليلها")
    public_parser.add_argument(
        "--session-username",
        help="اسم مستخدم جلسة instaloader محفوظة مسبقًا (اختياري)",
    )
    public_parser.set_defaults(func=run_public)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = args.func(args)
    print_report(report)


if __name__ == "__main__":
    main()

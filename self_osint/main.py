#!/usr/bin/env python3
"""
أداة فحص البصمة الرقمية الذاتية (Self-OSINT).

الغرض: أن ترى ما هو مكشوف عنك أنت في المصادر المفتوحة، لتقلّله.
هذه الأداة مخصّصة لفحص معرّفاتك أنت (أو معرّفات تملك تفويضًا صريحًا بفحصها) فقط.

أمثلة:

  # فحص كامل لإيميل واسم مستخدم
  python main.py scan --email you@example.com --username your_handle

  # فحص مستودع محلي بحثًا عن إيميلات وأسرار في السجل
  python main.py scan --repo /path/to/repo

  # تقرير Markdown محفوظ في ملف
  python main.py scan --email you@example.com --format markdown --output report.md
"""
import argparse
import os
import sys

from dotenv import load_dotenv

from findings import ScanReport, utc_now
from report import to_console, to_json, to_markdown

load_dotenv()

ALL_SOURCES = ["hibp", "gravatar", "usernames", "github", "instagram", "x", "git-history"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="فحص ما هو مكشوف عنك في المصادر المفتوحة (لمعرّفاتك أنت فقط).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="تشغيل فحص على المعرّفات المعطاة")
    scan.add_argument("--email", action="append", default=[], help="إيميل تملكه (يمكن تكراره)")
    scan.add_argument("--username", action="append", default=[], help="اسم مستخدم تملكه (يمكن تكراره)")
    scan.add_argument("--repo", action="append", default=[], help="مسار مستودع Git محلي (يمكن تكراره)")
    scan.add_argument(
        "--sources",
        default="all",
        help=f"مصادر مفصولة بفواصل، أو all. المتاح: {', '.join(ALL_SOURCES)}",
    )
    scan.add_argument(
        "--format", choices=["console", "markdown", "json"], default="console", help="صيغة المخرجات"
    )
    scan.add_argument("--output", help="مسار ملف لحفظ التقرير بدل الطباعة")
    scan.add_argument("--timeout", type=int, default=15, help="مهلة كل طلب شبكة بالثواني")
    scan.add_argument("--hibp-key", default="", help="مفتاح HIBP API (أو متغير البيئة HIBP_API_KEY)")
    scan.add_argument(
        "--github-token", default="", help="رمز GitHub لرفع حد الطلبات (أو GITHUB_TOKEN)"
    )
    scan.add_argument(
        "--fail-on",
        choices=["never", "low", "medium", "high", "critical"],
        default="never",
        help="أعِد رمز خروج 1 إذا بلغت أعلى خطورة هذا المستوى أو تجاوزته (مفيد في CI)",
    )
    return parser


def resolve_sources(value: str) -> list:
    if value.strip().lower() == "all":
        return list(ALL_SOURCES)
    requested = [s.strip().lower() for s in value.split(",") if s.strip()]
    unknown = [s for s in requested if s not in ALL_SOURCES]
    if unknown:
        raise SystemExit(f"مصادر غير معروفة: {', '.join(unknown)}. المتاح: {', '.join(ALL_SOURCES)}")
    return requested


def run_scan(args: argparse.Namespace) -> ScanReport:
    sources = resolve_sources(args.sources)
    report = ScanReport(
        identity={"emails": args.email, "usernames": args.username, "repos": args.repo},
        started_at=utc_now(),
    )

    hibp_key = args.hibp_key or os.getenv("HIBP_API_KEY", "")
    github_token = args.github_token or os.getenv("GITHUB_TOKEN", "")

    if "hibp" in sources and args.email:
        if not hibp_key:
            report.add_error("hibp", "لا يوجد مفتاح HIBP — مرّر --hibp-key أو اضبط HIBP_API_KEY.")
        else:
            from sources import hibp

            for email in args.email:
                try:
                    for finding in hibp.check_email(email, hibp_key):
                        report.add(finding)
                except Exception as exc:  # مصدر واحد لا يجب أن يُسقط الفحص كله
                    report.add_error("hibp", f"{email}: {exc}")

    if "gravatar" in sources and args.email:
        from sources import gravatar

        for email in args.email:
            try:
                for finding in gravatar.check_email(email, timeout=args.timeout):
                    report.add(finding)
            except Exception as exc:
                report.add_error("gravatar", f"{email}: {exc}")

    if "usernames" in sources and args.username:
        from sources import usernames as usernames_source

        for username in args.username:
            try:
                for finding in usernames_source.check_username(username, timeout=args.timeout):
                    report.add(finding)
            except Exception as exc:
                report.add_error("usernames", f"{username}: {exc}")

    if "github" in sources and args.username:
        from sources import github_profile

        for username in args.username:
            try:
                for finding in github_profile.check_user(
                    username, timeout=args.timeout, token=github_token
                ):
                    report.add(finding)
            except Exception as exc:
                report.add_error("github", f"{username}: {exc}")

    if "instagram" in sources and args.username:
        from sources import instagram

        for username in args.username:
            try:
                for finding in instagram.check_username(username, timeout=args.timeout):
                    report.add(finding)
            except Exception as exc:
                report.add_error("instagram", f"{username}: {exc}")

    if "x" in sources and args.username:
        from sources import x_twitter

        for username in args.username:
            try:
                for finding in x_twitter.check_username(username, timeout=args.timeout):
                    report.add(finding)
            except Exception as exc:
                report.add_error("x", f"{username}: {exc}")

    if "git-history" in sources and args.repo:
        from sources import git_history

        for repo_path in args.repo:
            try:
                for finding in git_history.scan_repo(repo_path, own_emails=args.email):
                    report.add(finding)
            except Exception as exc:
                report.add_error("git-history", f"{repo_path}: {exc}")

    report.finished_at = utc_now()
    return report


def render(report: ScanReport, output_format: str) -> str:
    if output_format == "json":
        return to_json(report)
    if output_format == "markdown":
        return to_markdown(report)
    return to_console(report)


def main() -> int:
    args = build_parser().parse_args()

    if not (args.email or args.username or args.repo):
        print("حدّد على الأقل --email أو --username أو --repo.", file=sys.stderr)
        return 2

    report = run_scan(args)
    text = render(report, args.format)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"حُفظ التقرير في: {args.output}")
    else:
        print(text)

    if args.fail_on != "never":
        from findings import severity_rank

        if severity_rank(report.max_severity) >= severity_rank(args.fail_on):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

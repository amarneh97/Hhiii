#!/usr/bin/env python3
"""
سجلّ أخطاء المحادثات مع كلود (Claude Code + claude.ai).

الفكرة: كل خطأ يقع في محادثاتنا — فشل أداة، خطأ API، رفض صلاحية، أو تصحيح
منك لردّ خاطئ — يُسجَّل في ملف واحد قابل للبحث والإحصاء، بدل أن يضيع في السجل.

أمثلة:

  # تركيب الخطّافات ليُسجَّل كل خطأ في Claude Code لحظة وقوعه
  python main.py install-hook --global

  # فحص جلسات Claude Code السابقة واستخراج أخطائها
  python main.py scan

  # استيراد أخطاء محادثات claude.ai من ملف التصدير
  python main.py import --file ~/Downloads/conversations.json

  # تسجيل خطأ يدويًا لاحظته أنت
  python main.py log --message "أعطاني أمر git خاطئ" --source claude_web --severity high

  # عرض وإحصاء وتقرير
  python main.py list --min-severity high
  python main.py stats
  python main.py report --format markdown --output errors.md
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report as report_mod                                  # noqa: E402
from models import ErrorRecord, KINDS, SEVERITY_ORDER        # noqa: E402
from store import ErrorStore, filter_records, sort_records, log_path  # noqa: E402
from sources import claude_code, claude_web                  # noqa: E402


HOOK_EVENTS = ["PostToolUse", "UserPromptSubmit", "Notification"]


# ---------- أوامر ----------

def cmd_log(args) -> int:
    """تسجيل خطأ يدويًا."""
    store = ErrorStore(args.log_file)
    detail = args.detail or ""
    if args.detail_file:
        detail = Path(args.detail_file).expanduser().read_text(encoding="utf-8", errors="replace")
    record = ErrorRecord(
        source=args.source,
        kind=args.kind,
        severity=args.severity,
        message=args.message,
        detail=detail,
        session=args.session,
        project=args.project,
        occurred_at=args.at,
        tags=args.tag or [],
    )
    added = store.append(record)
    if added:
        print(f"سُجّل الخطأ [{record.id}] في {store.path}")
    else:
        print(f"الخطأ مسجّل مسبقًا [{record.id}] — لم يُضَف مجددًا.")
    return 0


def cmd_scan(args) -> int:
    """فحص جلسات Claude Code واستخراج أخطائها."""
    store = ErrorStore(args.log_file)
    records = claude_code.scan(
        root=args.transcripts,
        include_corrections=not args.no_corrections,
        limit_files=args.limit_files,
    )
    if args.dry_run:
        print(report_mod.render(sort_records(records), fmt=args.format, detail=args.detail))
        print(f"\n(تجربة فقط) عُثر على {len(records)} خطأ — لم يُكتب شيء.", file=sys.stderr)
        return 0
    added = store.extend(records)
    print(f"فُحصت جلسات Claude Code: {len(records)} خطأ، الجديد منها {added}. السجل: {store.path}")
    return 0


def cmd_import(args) -> int:
    """استيراد أخطاء من ملف تصدير claude.ai."""
    store = ErrorStore(args.log_file)
    try:
        records = claude_web.parse_export(args.file, include_output_errors=args.with_output_errors)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        print(report_mod.render(sort_records(records), fmt=args.format, detail=args.detail))
        print(f"\n(تجربة فقط) عُثر على {len(records)} خطأ — لم يُكتب شيء.", file=sys.stderr)
        return 0
    added = store.extend(records)
    print(f"استُوردت محادثات claude.ai: {len(records)} خطأ، الجديد منها {added}. السجل: {store.path}")
    return 0


def _selected(args) -> list:
    store = ErrorStore(args.log_file)
    records = filter_records(
        store.load(),
        source=args.source or "",
        kind=args.kind or "",
        min_severity=args.min_severity or "",
        since=args.since or "",
        search=args.search or "",
    )
    records = sort_records(records, newest_first=not args.oldest_first)
    if args.limit:
        records = records[: args.limit]
    return records


def cmd_list(args) -> int:
    print(report_mod.render(_selected(args), fmt=args.format, detail=args.detail))
    return 0


def cmd_stats(args) -> int:
    print(report_mod.render_stats(_selected(args)))
    return 0


def cmd_report(args) -> int:
    text = report_mod.render(_selected(args), fmt=args.format, detail=True)
    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"حُفظ التقرير في {out}")
    else:
        print(text)
    return 0


def cmd_path(args) -> int:
    store = ErrorStore(args.log_file)
    print(store.path)
    print(f"موجود: {'نعم' if store.path.exists() else 'لا'}؛ عدد الأخطاء: {len(store.load())}")
    return 0


# ---------- تركيب الخطّافات ----------

def _settings_file(global_scope: bool, target: str = "") -> Path:
    if target:
        return Path(target).expanduser()
    if global_scope:
        return Path.home() / ".claude" / "settings.json"
    return Path.cwd() / ".claude" / "settings.json"


def _hook_command(log_file: str) -> str:
    hook = Path(__file__).resolve().parent / "hook.py"
    prefix = f"CLAUDE_ERROR_LOG={Path(log_file).expanduser()} " if log_file else ""
    return f"{prefix}{sys.executable} {hook}"


def cmd_install_hook(args) -> int:
    """يضيف خطّافات تسجيل الأخطاء إلى إعدادات Claude Code."""
    path = _settings_file(args.global_scope, args.settings)
    settings = {}
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            print(f"ملف الإعدادات {path} غير صالح كـ JSON — أصلحه أولًا.", file=sys.stderr)
            return 1

    command = _hook_command(args.log_file)
    hooks = settings.setdefault("hooks", {})
    changed = False
    for event in HOOK_EVENTS:
        entries = hooks.setdefault(event, [])
        already = any(
            isinstance(entry, dict)
            and any(
                isinstance(h, dict) and "hook.py" in str(h.get("command", "")) and "conversation_errors" in str(h.get("command", ""))
                for h in entry.get("hooks", [])
            )
            for entry in entries
        )
        if already:
            continue
        entry = {"hooks": [{"type": "command", "command": command}]}
        if event == "PostToolUse":
            entry["matcher"] = "*"
        entries.append(entry)
        changed = True

    if not changed:
        print(f"الخطّافات مركّبة مسبقًا في {path}.")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"رُكّبت الخطّافات في {path} للأحداث: {', '.join(HOOK_EVENTS)}")
    print("ابدأ جلسة Claude Code جديدة ليسري المفعول.")
    return 0


def cmd_uninstall_hook(args) -> int:
    """يزيل خطّافات هذه الأداة من إعدادات Claude Code."""
    path = _settings_file(args.global_scope, args.settings)
    if not path.exists():
        print(f"لا يوجد ملف إعدادات في {path}.")
        return 0
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        print(f"ملف الإعدادات {path} غير صالح كـ JSON.", file=sys.stderr)
        return 1

    hooks = settings.get("hooks", {})
    removed = 0
    for event in list(hooks):
        kept = []
        for entry in hooks.get(event, []):
            inner = entry.get("hooks", []) if isinstance(entry, dict) else []
            ours = any(
                isinstance(h, dict) and "conversation_errors" in str(h.get("command", ""))
                for h in inner
            )
            if ours:
                removed += 1
            else:
                kept.append(entry)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks", None)

    if removed:
        path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"أُزيلت {removed} خطّاف من {path}.")
    else:
        print(f"لا توجد خطّافات لهذه الأداة في {path}.")
    return 0


# ---------- الواجهة ----------

def _add_filter_args(parser):
    parser.add_argument("--source", choices=["claude_code", "claude_web", "manual"], help="تصفية حسب المصدر")
    parser.add_argument("--kind", choices=KINDS, help="تصفية حسب نوع الخطأ")
    parser.add_argument("--min-severity", choices=SEVERITY_ORDER, help="أدنى خطورة تُعرض")
    parser.add_argument("--since", default="", help="من تاريخ (ISO مثل 2026-01-01)")
    parser.add_argument("--search", default="", help="بحث نصّي في الرسالة والتفاصيل")
    parser.add_argument("--limit", type=int, default=0, help="حدّ عدد النتائج")
    parser.add_argument("--oldest-first", action="store_true", help="ترتيب تصاعدي بالزمن")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conversation_errors",
        description="سجلّ أخطاء محادثاتك مع كلود (Claude Code و claude.ai).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--log-file", default="", help="مسار ملف السجل (افتراضيًا ~/.claude/error-log/errors.jsonl)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_log = sub.add_parser("log", help="تسجيل خطأ يدويًا")
    p_log.add_argument("--message", required=True, help="وصف مختصر للخطأ")
    p_log.add_argument("--detail", default="", help="تفاصيل كاملة")
    p_log.add_argument("--detail-file", default="", help="ملف يحوي التفاصيل")
    p_log.add_argument("--source", default="manual", choices=["claude_code", "claude_web", "manual"])
    p_log.add_argument("--kind", default="manual", choices=KINDS)
    p_log.add_argument("--severity", default="medium", choices=SEVERITY_ORDER)
    p_log.add_argument("--session", default="", help="معرّف الجلسة أو عنوان المحادثة")
    p_log.add_argument("--project", default="", help="المشروع أو السياق")
    p_log.add_argument("--at", default="", help="وقت وقوع الخطأ (ISO)؛ الافتراضي الآن")
    p_log.add_argument("--tag", action="append", help="وسم (يُكرَّر)")
    p_log.set_defaults(func=cmd_log)

    p_scan = sub.add_parser("scan", help="فحص جلسات Claude Code السابقة")
    p_scan.add_argument("--transcripts", default="", help="مجلد الجلسات (افتراضيًا ~/.claude/projects)")
    p_scan.add_argument("--no-corrections", action="store_true", help="تجاهل تصحيحاتك واكتفِ بالأخطاء التقنية")
    p_scan.add_argument("--limit-files", type=int, default=0, help="عدد ملفات الجلسات المفحوصة (الأحدث أولًا)")
    p_scan.add_argument("--dry-run", action="store_true", help="عرض ما سيُسجَّل دون كتابته")
    p_scan.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    p_scan.add_argument("--detail", action="store_true", help="إظهار التفاصيل الكاملة")
    p_scan.set_defaults(func=cmd_scan)

    p_imp = sub.add_parser("import", help="استيراد أخطاء من تصدير claude.ai")
    p_imp.add_argument("--file", required=True, help="مسار conversations.json من تصدير بياناتك")
    p_imp.add_argument("--with-output-errors", action="store_true", help="التقاط أي نص يحمل أثر خطأ تقني أيضًا")
    p_imp.add_argument("--dry-run", action="store_true", help="عرض ما سيُسجَّل دون كتابته")
    p_imp.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    p_imp.add_argument("--detail", action="store_true", help="إظهار التفاصيل الكاملة")
    p_imp.set_defaults(func=cmd_import)

    p_list = sub.add_parser("list", help="عرض الأخطاء المسجّلة")
    _add_filter_args(p_list)
    p_list.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    p_list.add_argument("--detail", action="store_true", help="إظهار التفاصيل الكاملة")
    p_list.set_defaults(func=cmd_list)

    p_stats = sub.add_parser("stats", help="إحصاءات السجل")
    _add_filter_args(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    p_rep = sub.add_parser("report", help="تقرير كامل (نص/Markdown/JSON)")
    _add_filter_args(p_rep)
    p_rep.add_argument("--format", default="markdown", choices=["text", "markdown", "json"])
    p_rep.add_argument("--output", default="", help="حفظ التقرير في ملف")
    p_rep.set_defaults(func=cmd_report)

    p_path = sub.add_parser("path", help="عرض مسار السجل وحجمه")
    p_path.set_defaults(func=cmd_path)

    p_in = sub.add_parser("install-hook", help="تركيب خطّافات التسجيل التلقائي في Claude Code")
    p_in.add_argument("--global", dest="global_scope", action="store_true", help="تركيب لكل المشاريع (~/.claude/settings.json)")
    p_in.add_argument("--settings", default="", help="مسار ملف إعدادات محدّد")
    p_in.set_defaults(func=cmd_install_hook)

    p_un = sub.add_parser("uninstall-hook", help="إزالة الخطّافات")
    p_un.add_argument("--global", dest="global_scope", action="store_true")
    p_un.add_argument("--settings", default="", help="مسار ملف إعدادات محدّد")
    p_un.set_defaults(func=cmd_uninstall_hook)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

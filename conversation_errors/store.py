"""تخزين سجل الأخطاء في ملف JSONL (سطر واحد لكل خطأ)."""
import json
import os
from pathlib import Path

from models import ErrorRecord, severity_rank


# مسار السجل الافتراضي؛ يمكن تغييره بمتغيّر البيئة CLAUDE_ERROR_LOG.
DEFAULT_LOG = Path.home() / ".claude" / "error-log" / "errors.jsonl"


def log_path(override: str = "") -> Path:
    """يحدّد ملف السجل: الوسيط ثم متغيّر البيئة ثم المسار الافتراضي."""
    if override:
        return Path(override).expanduser()
    env = os.environ.get("CLAUDE_ERROR_LOG", "")
    if env:
        return Path(env).expanduser()
    return DEFAULT_LOG


class ErrorStore:
    """سجل أخطاء يُلحَق به فقط، مع منع التكرار عبر بصمة كل خطأ."""

    def __init__(self, path=None):
        self.path = Path(path).expanduser() if path else log_path()

    # ---------- قراءة ----------

    def load(self) -> list:
        """يقرأ كل الأخطاء المسجّلة، ويتجاهل أي سطر تالف بصمت."""
        records = []
        if not self.path.exists():
            return records
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(ErrorRecord.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return records

    def known_ids(self) -> set:
        return {rec.id for rec in self.load()}

    # ---------- كتابة ----------

    def append(self, record: ErrorRecord) -> bool:
        """يضيف خطأً واحدًا. يُعيد False إذا كان مسجّلًا مسبقًا."""
        return self.extend([record]) == 1

    def extend(self, records) -> int:
        """يضيف عدة أخطاء دفعة واحدة ويُعيد عدد الجديد منها فعليًا."""
        records = list(records)
        if not records:
            return 0
        seen = self.known_ids()
        fresh = []
        for rec in records:
            if rec.id in seen:
                continue
            seen.add(rec.id)
            fresh.append(rec)
        if not fresh:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            for rec in fresh:
                fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        return len(fresh)


def filter_records(records, source="", kind="", min_severity="", since="", search="") -> list:
    """تصفية السجل حسب المصدر/النوع/الخطورة/التاريخ/نص البحث."""
    out = []
    floor = severity_rank(min_severity) if min_severity else -1
    needle = search.lower()
    for rec in records:
        if source and rec.source != source:
            continue
        if kind and rec.kind != kind:
            continue
        if floor >= 0 and severity_rank(rec.severity) < floor:
            continue
        if since and rec.occurred_at < since:
            continue
        if needle and needle not in (rec.message + " " + rec.detail).lower():
            continue
        out.append(rec)
    return out


def sort_records(records, newest_first=True) -> list:
    return sorted(records, key=lambda r: r.occurred_at, reverse=newest_first)

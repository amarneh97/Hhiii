"""تخزين واسترجاع آخر حالة معروفة للحساب (لمقارنة التفاعل الجديد لاحقًا)."""
import json
import os
from typing import Optional


def load_state(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def report_to_state(report) -> dict:
    return {
        "account": report.account,
        "followers": report.followers,
        "posts": {
            p.post_id: {"likes": p.likes, "comments": p.comments}
            for p in report.posts
        },
    }

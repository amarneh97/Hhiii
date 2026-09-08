"""فحص ملف Gravatar المرتبط بالإيميل.

Gravatar يربط بصمة (hash) الإيميل بملف شخصي عام؛ هذا يعني أن أي موقع يعرف إيميلك
قد يستطيع عرض اسمك وصورتك وحساباتك المرتبطة دون علمك — وهو تسريب هوية شائع ومغفول عنه.
"""
import hashlib

import requests

from findings import Finding

PROFILE_URL = "https://gravatar.com/{hash}.json"


def email_hashes(email: str) -> dict:
    """بصمتا الإيميل كما يحسبهما Gravatar: تُصغَّر الحروف وتُزال المسافات."""
    normalized = email.strip().lower().encode("utf-8")
    return {
        "md5": hashlib.md5(normalized).hexdigest(),
        "sha256": hashlib.sha256(normalized).hexdigest(),
    }


def check_email(email: str, timeout: int = 15) -> list:
    """يعيد Finding إن وُجد ملف Gravatar عام مرتبط بالإيميل."""
    hashes = email_hashes(email)
    findings = []

    for algorithm, digest in hashes.items():
        url = PROFILE_URL.format(hash=digest)
        try:
            response = requests.get(
                url, timeout=timeout, headers={"user-agent": "self-osint-cli"}
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"تعذر الوصول إلى Gravatar: {exc}") from exc

        if response.status_code != 200:
            continue

        try:
            entry = (response.json().get("entry") or [{}])[0]
        except (ValueError, IndexError, AttributeError):
            continue

        accounts = [a.get("url", "") for a in (entry.get("accounts") or []) if a.get("url")]
        details = []
        if entry.get("displayName"):
            details.append(f"الاسم المعروض: {entry['displayName']}")
        if entry.get("name"):
            full = entry["name"].get("formatted") if isinstance(entry["name"], dict) else entry["name"]
            if full:
                details.append(f"الاسم الكامل: {full}")
        if entry.get("currentLocation"):
            details.append(f"الموقع: {entry['currentLocation']}")
        if accounts:
            details.append("حسابات مرتبطة: " + ", ".join(accounts))

        findings.append(
            Finding(
                source="gravatar",
                target=email,
                title="ملف Gravatar عام مرتبط بالإيميل",
                detail=(
                    " | ".join(details)
                    or "الملف موجود لكن بلا بيانات شخصية معلنة (صورة فقط غالبًا)."
                ),
                # وجود حسابات مرتبطة أو موقع جغرافي يرفع الخطورة: يربط الإيميل بهويتك عبر منصات.
                severity="medium" if (accounts or entry.get("currentLocation")) else "low",
                url=entry.get("profileUrl") or f"https://gravatar.com/{digest}",
                advice=(
                    "أي موقع يعرف إيميلك يستطيع جلب هذا الملف. احذف البيانات التي لا تريد ربطها علنًا "
                    "من gravatar.com، أو استخدم إيميلًا منفصلًا للتعليقات والمنتديات."
                ),
                data={"hash_algorithm": algorithm, "hash": digest, "linked_accounts": accounts},
            )
        )
        # ملف واحد يكفي — البصمتان تشيران لنفس الحساب.
        break

    return findings

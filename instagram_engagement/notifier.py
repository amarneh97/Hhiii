"""قنوات إرسال الإشعارات عند اكتشاف تفاعل جديد."""
import subprocess
from datetime import datetime


class ConsoleNotifier:
    def notify(self, title: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {title}: {message}")


class DesktopNotifier:
    """إشعار سطح مكتب عبر notify-send (لينكس) أو osascript (ماك). يتجاهل الخطأ بصمت إن لم تتوفر بيئة رسومية."""

    def notify(self, title: str, message: str) -> None:
        try:
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            try:
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(
                    ["osascript", "-e", script],
                    check=False,
                    timeout=5,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (FileNotFoundError, OSError):
                pass  # لا تتوفر بيئة إشعارات سطح مكتب؛ يُفضَّل الاعتماد على ConsoleNotifier أو WebhookNotifier


class WebhookNotifier:
    """يرسل الإشعار إلى ويب هوك متوافق مع Slack أو Discord."""

    def __init__(self, url: str, style: str = "slack"):
        self.url = url
        self.style = style

    def notify(self, title: str, message: str) -> None:
        import requests

        text = f"*{title}*\n{message}"
        payload = {"text": text} if self.style == "slack" else {"content": text}
        try:
            requests.post(self.url, json=payload, timeout=10)
        except requests.RequestException as exc:
            print(f"تعذّر إرسال إشعار الويب هوك: {exc}")


class MultiNotifier:
    def __init__(self, notifiers: list):
        self.notifiers = notifiers

    def notify(self, title: str, message: str) -> None:
        for n in self.notifiers:
            n.notify(title, message)


def build_notifier(channels: list, webhook_url: str = "", webhook_style: str = "slack"):
    notifiers = []
    for channel in channels:
        if channel == "console":
            notifiers.append(ConsoleNotifier())
        elif channel == "desktop":
            notifiers.append(DesktopNotifier())
        elif channel == "webhook":
            if not webhook_url:
                raise ValueError("قناة webhook تتطلب تمرير --webhook-url")
            notifiers.append(WebhookNotifier(webhook_url, style=webhook_style))
        else:
            raise ValueError(f"قناة إشعار غير معروفة: {channel}")
    return MultiNotifier(notifiers)

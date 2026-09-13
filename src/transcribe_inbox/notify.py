from __future__ import annotations
import subprocess


def notify(title: str, message: str) -> None:
    # notify_failed() interpolates str(exc), which can carry arbitrary
    # whisper-cli/ffmpeg stderr -- escape backslash first, then quote, so
    # newly-inserted backslashes don't get double-escaped, or a stray `"`
    # could break the AppleScript source and silently drop the notification.
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    escaped_message = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{escaped_message}" with title "{escaped_title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script], check=False)


def notify_completed(category: str, label: str) -> None:
    notify("전사 완료", f"{category} · {label}")


def notify_failed(category: str, label: str, error_message: str) -> None:
    notify("전사 실패", f"{category} · {label}: {error_message}")


def notify_started(category: str, label: str) -> None:
    notify("전사 시작", f"{category} · {label}")

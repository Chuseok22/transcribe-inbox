from __future__ import annotations
import subprocess


def notify(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script], check=False)


def notify_completed(category: str, label: str) -> None:
    notify("전사 완료", f"{category} · {label}")


def notify_failed(category: str, label: str, error_message: str) -> None:
    notify("전사 실패", f"{category} · {label}: {error_message}")

import requests
from typing import Optional


def send_telegram(token: str, chat_id: str, text: str, thread_id: Optional[int] = None) -> None:
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}

    if thread_id is not None:
        payload["message_thread_id"] = int(thread_id)

    requests.post(url, json=payload, timeout=10)

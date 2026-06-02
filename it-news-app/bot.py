#!/usr/bin/env python3
"""Telegram bot for IT News Mini App."""
import json
import urllib.request
import urllib.error
import sys
import os
import subprocess
from datetime import datetime

import dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
dotenv.load_dotenv(dotenv_path)
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_URL = os.getenv('APP_URL', 'https://freejam.online/it-news-app/')


def api(method, data=None, files=None):
    """Call Telegram Bot API."""
    url = f"{BASE_URL}/{method}"
    if data and not files:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    elif files:
        import mimetypes
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = b""
        for key, value in data.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += str(value).encode() + b"\r\n"
        for key, fpath in files.items():
            fname = os.path.basename(fpath)
            ctype = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"; filename="{fname}"\r\n'.encode()
            body += f"Content-Type: {ctype}\r\n\r\n".encode()
            with open(fpath, "rb") as f:
                body += f.read() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"API error ({method}): {e}", file=sys.stderr)
        return None


def send_message(chat_id, text, reply_markup=None):
    """Send a text message."""
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    return api("sendMessage", data)


def send_welcome(chat_id):
    """Send welcome message with Mini App button."""
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "📰 Открыть IT News",
                    "web_app": {"url": APP_URL},
                }
            ],
            [
                {"text": "🔄 Обновить новости", "callback_data": "refresh"},
            ],
        ]
    }
    text = (
        "⚡ <b>IT News</b>\n\n"
        "Новости из Reddit и Хабра — на русском языке.\n"
        "Нажмите кнопку ниже, чтобы открыть приложение."
    )
    return send_message(chat_id, text, markup)


def send_help(chat_id):
    """Send help message."""
    text = (
        "⚡ <b>IT News — Помощь</b>\n\n"
        "📰 <b>IT News</b> — откройте приложение новостей\n"
        "🔄 <b>Обновить новости</b> — запустить парсер вручную\n"
        "❓ <b>Помощь</b> — это сообщение\n\n"
        "Источники:\n"
        "• 🔴 Reddit r/technology — топ новостей с переводом\n"
        "• 💚 Хабр — топ статей за сутки по рейтингу\n\n"
        "Обновление: автоматически в 07:00"
    )
    return send_message(chat_id, text)


def run_update(chat_id):
    """Run the update script and report."""
    send_message(chat_id, "🔄 Запуск обновления...")
    try:
        result = subprocess.run(
            ["bash", f"{INSTALL_DIR}/update.sh"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        errors = result.stderr.strip()

        # Read counts from API
        reddit_count = 0
        habr_count = 0
        try:
            import urllib.request as _ur
            api_url = "http://127.0.0.1:8018/api/stats"
            with _ur.urlopen(api_url, timeout=10) as resp:
                stats = json.loads(resp.read().decode())
                reddit_count = (stats.get("by_source", {}) or {}).get("reddit", 0)
                habr_count = (stats.get("by_source", {}) or {}).get("habr", 0)
        except:
            pass

        text = (
            f"✅ <b>Обновление завершено</b>\n\n"
            f"🔴 Reddit: {reddit_count} новостей\n"
            f"💚 Хабр: {habr_count} статей\n\n"
            f"<pre>{output[-500:]}</pre>"
        )
        if errors:
            text += f"\n\n⚠️ <pre>{errors[-300:]}</pre>"

        markup = {
            "inline_keyboard": [
                [{"text": "📰 Открыть IT News", "web_app": {"url": APP_URL}}]
            ]
        }
        return send_message(chat_id, text, markup)
    except subprocess.TimeoutExpired:
        return send_message(chat_id, "❌ Таймаут обновления")
    except Exception as e:
        return send_message(chat_id, f"❌ Ошибка: {e}")


def answer_callback(callback_id, text=None):
    """Answer a callback query."""
    data = {"callback_query_id": callback_id}
    if text:
        data["text"] = text
    return api("answerCallbackQuery", data)


def process_update(update):
    """Process a single update."""
    # Callback query
    if "callback_query" in update:
        cq = update["callback_query"]
        cid = cq["id"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        if data == "refresh":
            answer_callback(cid, "🔄 Обновляю...")
            run_update(chat_id)
        return

    # Message
    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        send_welcome(chat_id)
    elif text.startswith("/news") or text.startswith("/refresh"):
        run_update(chat_id)
    elif text.startswith("/help"):
        send_help(chat_id)
    else:
        send_welcome(chat_id)


def main():
    """Long polling loop."""
    print("Bot started (long polling)...", file=sys.stderr)
    offset = 0

    while True:
        try:
            result = api("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]})
            if not result or not result.get("ok"):
                import time
                time.sleep(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                try:
                    process_update(update)
                except Exception as e:
                    print(f"Error processing update: {e}", file=sys.stderr)

        except KeyboardInterrupt:
            print("Bot stopped.", file=sys.stderr)
            break
        except Exception as e:
            print(f"Polling error: {e}", file=sys.stderr)
            import time
            time.sleep(5)


if __name__ == "__main__":
    main()

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Iterable, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# Separate credentials for fetching article data and signing webhook calls.
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
WEBHOOK_SIGNATURE = os.getenv("WEBHOOK_SIGNATURE") or NEWSAPI_KEY
NEWS_API_BASE_URL = os.getenv("NEWS_API_BASE_URL", "").rstrip("/")

DEFAULT_TIMEOUT = float(os.getenv("WEBHOOK_TIMEOUT", 60))
FETCH_TIMEOUT = float(os.getenv("NEWS_FETCH_TIMEOUT", 20))


def _build_session(total_retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """Create a shared requests session with retry/backoff to harden network calls."""
    retry = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        status=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


SESSION = _build_session()


def _missing_config_message(name: str) -> str:
    return f"[{name}] skipped: missing required configuration."


def _validate_payload(payload: Dict[str, Any], required_fields: Iterable[str]) -> Optional[str]:
    missing = [f for f in required_fields if payload.get(f) in (None, "")]
    if missing:
        return f"Payload missing required fields {missing}; aborting webhook call."
    return None


def _log_outgoing(target_url: str, headers: Dict[str, Any], payload: Dict[str, Any], webhook_name: str) -> None:
    try:
        redacted_headers = {**headers, "X-Signature": "***redacted***"} if "X-Signature" in headers else headers
        print(f"[{webhook_name}] Sending webhook POST to: {target_url}")
        # print(f"Headers: {redacted_headers}")
        # print("Payload:", json.dumps(payload, ensure_ascii=False))
    except Exception:
        print(f"[{webhook_name}] Payload (repr):", repr(payload))


def _post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
    webhook_name: str,
) -> Optional[Dict[str, Any]]:
    _log_outgoing(url, headers, payload, webhook_name)
    try:
        response = SESSION.post(url, data=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        print(f"[{webhook_name}] Webhook POST succeeded: {response.status_code} Body: {response.text}")
        if "adminer" in response.text.lower():
            print(f"[{webhook_name}] WARNING: response looks like Adminer HTML, check URL: {url}")
        try:
            return response.json()
        except Exception:
            return None
    except requests.HTTPError as http_err:
        print(
            f"[{webhook_name}] Error sending to webhook: {http_err} "
            f"Status: {response.status_code} Body: {response.text}"
        )
        return None

def send_to_webhook_to_embedding(insert_id, webhook_url=None):
    try:
        target_url = webhook_url or os.getenv("WEBHOOK_URL")
        if not target_url:
            print(_missing_config_message("embedding webhook"))
            return None

        payload = get_news_data(insert_id)
        if not payload:
            print("No data found to send to webhook.")
            return None
        print(f"Fetched payload: {payload}")
        required_fields = ["article_id", "url", "title", "text", "topic", "source", "sentiment", "scraped_at"]
        validation_error = _validate_payload(payload, required_fields)
        if validation_error:
            print(validation_error)
            return None
        
        text_builder = f"Title: {payload.get('title', '')}\n\n Text: {payload.get('text', '')}\n\n Message sent at: {payload.get('scraped_at', '')}\n\n Source: Message from {payload.get('source', '')} in Telegram\n\n URL: {payload.get('url', '')}"
        payload_to_send = {
            "article_id": payload.get("article_id"),
            "url": payload.get("url"),
            "title": payload.get("title"),
            "text": text_builder,
            "topic": payload.get("topic"),
            "source": payload.get("source"),
            "sentiment": payload.get("sentiment"),
            "scraped_at": payload.get("scraped_at"),
        }
        raw_body = json.dumps(
            payload_to_send,
            separators=(",", ":"),  
            ensure_ascii=False
        ).encode("utf-8")
        print(f"Payload for webhook: {raw_body}")
        signature = hmac.new(
            WEBHOOK_SIGNATURE.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Signature": f"sha256={signature}",
        }
        print(f"Headers for webhook: {headers}")

        to_return = _post_json(
            target_url,
            raw_body,
            headers,
            timeout=DEFAULT_TIMEOUT,
            webhook_name="embedding",
        )
        print(f"Webhook response: {to_return}")
        return to_return

    except requests.exceptions.RequestException as e:
        # Network-level errors, timeouts, DNS, etc.
        print(f"Error sending to webhook (network): {e}")
        return None


def send_to_all_webhooks(insert_id, webhook_url=None):
    """Send to both embedding and thread-event webhooks; returns a result map."""
    webhook_urls = webhook_url or {}
    embedding_url = webhook_urls.get("embedding") if isinstance(webhook_urls, dict) else webhook_urls
    thread_url = webhook_urls.get("thread_events") if isinstance(webhook_urls, dict) else None

    embedding_resp = send_to_webhook_to_embedding(insert_id, webhook_url=embedding_url)
    thread_resp = send_to_webhook_thread_events(insert_id, webhook_url=thread_url)

    return {
        "embedding": embedding_resp,
        "thread_events": thread_resp,
    }


def send_to_webhook_thread_events(insert_id, webhook_url=None):
    target_url = webhook_url or os.getenv("WEBHOOK_URL_THREAD_EVENTS")
    if not target_url:
        print(_missing_config_message("thread events webhook"))
        return None

    data = get_news_data(insert_id)
    if not data:
        print("No data found to send to webhooks.")
        return None
    try:
        required_fields = ["article_id", "source", "scraped_at"]
        validation_error = _validate_payload(data, required_fields)
        if validation_error:
            print(validation_error)
            return None
        payload = {
            "article_id": data.get("article_id"),
            "source": data.get("source"),
            "scraped_at": data.get("scraped_at"),
        }
        raw_body = json.dumps(
            payload,
            separators=(",", ":"),  
            ensure_ascii=False
        ).encode("utf-8")
        print(f"Payload for webhook: {raw_body}")
        signature = hmac.new(
            WEBHOOK_SIGNATURE.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature": f"sha256={signature}",
        }
        print(f"Headers for webhook: {headers}")
        return _post_json(
            target_url,
            raw_body,
            headers,
            timeout=DEFAULT_TIMEOUT,
            webhook_name="thread_events",
        )
    except requests.exceptions.RequestException as e:
        # Network-level errors, timeouts, DNS, etc.
        print(f"Error sending to webhook (network): {e}")
        return None


def get_news_data(insert_id: str, timeout: float = FETCH_TIMEOUT) -> Optional[Dict[str, Any]]:
    if not NEWSAPI_KEY:
        print(_missing_config_message("news api key"))
        return None
    if not NEWS_API_BASE_URL:
        print(_missing_config_message("news api base url"))
        return None

    base_url = f"{NEWS_API_BASE_URL}/v1/telegram/{insert_id}?apiKey={NEWSAPI_KEY}"
    try:
        response = SESSION.get(base_url, timeout=timeout)
        response.raise_for_status()
        data_raw = response.json()
        data = data_raw.get("data", {})
        if not data:
            print(f"No news data found for ID: {insert_id}")
            return None
        data_to_return: Dict[str, Any] = {
            "article_id": data.get("id"),
            "url": data.get("telegramUrl"),
            "title": data.get("title"),
            "text": data.get("text"),
            "topic": data.get("topic"),
            "source": data.get("source"),
            "sentiment": data.get("sentiment"),
            "scraped_at": data.get("telegramDate"),
        }
        return data_to_return
    except (requests.exceptions.RequestException, ValueError) as e:
        # ValueError catches JSON decode errors
        print(f"Error fetching news data: {e}")
        return None

"""Thin Gmail REST client using a locally cached, read-only OAuth token.

Only `gmail.readonly` scope is ever requested, and the only calls made are
"list message ids" and "get one message" — nothing here can modify or send
mail. See scripts/gmail_auth.py for the one-time consent flow that produces
the token this reads.
"""
import base64
import re
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailAuthError(RuntimeError):
    pass


def _load_credentials(token_path: Path) -> Credentials:
    if not token_path.exists():
        raise GmailAuthError(
            f"No Gmail token found at {token_path}. Run `python -m scripts.gmail_auth` "
            "once from the backend directory to authorize read-only Gmail access."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        token_path.write_text(creds.to_json())
    return creds


class GmailClient:
    def __init__(self, token_path: Path, timeout: float = 30.0):
        self._creds = _load_credentials(token_path)
        self._timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._creds.token}"}

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        ids: list[str] = []
        page_token = None

        with httpx.Client(timeout=self._timeout) as client:
            while len(ids) < max_results:
                params = {"q": query, "maxResults": min(100, max_results - len(ids))}
                if page_token:
                    params["pageToken"] = page_token

                response = client.get(f"{GMAIL_API}/messages", headers=self._headers(), params=params)
                response.raise_for_status()
                body = response.json()

                ids.extend(m["id"] for m in body.get("messages", []))
                page_token = body.get("nextPageToken")
                if not page_token:
                    break

        return ids

    def get_message(self, message_id: str) -> dict:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(
                f"{GMAIL_API}/messages/{message_id}",
                headers=self._headers(),
                params={"format": "full"},
            )
            response.raise_for_status()
            return response.json()


def extract_fields(message: dict) -> dict:
    payload = message.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    return {
        "id": message["id"],
        "subject": headers.get("subject", ""),
        "sender": headers.get("from", ""),
        "internal_date_ms": int(message.get("internalDate", "0")),
        "body": _extract_body(payload) or "",
    }


def _extract_body(payload: dict) -> str | None:
    mime_type = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and data:
        return _b64_decode(data)
    if mime_type == "text/html" and data:
        return _strip_html(_b64_decode(data))

    plain, html = None, None
    for part in payload.get("parts", []) or []:
        part_type = part.get("mimeType", "")
        part_data = part.get("body", {}).get("data")

        if part_type == "text/plain" and part_data:
            plain = plain or _b64_decode(part_data)
        elif part_type == "text/html" and part_data:
            html = html or _b64_decode(part_data)
        elif part.get("parts"):
            plain = plain or _extract_body(part)

    return plain or (_strip_html(html) if html else None)


def _b64_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

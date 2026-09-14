"""One-time local OAuth flow to authorize read-only Gmail access.

Run once from the backend directory:

    python -m scripts.gmail_auth

This opens a browser for you to sign in and grant read-only Gmail access,
then stores a refresh token on disk so the backend can read transaction
emails without repeating this flow. It does not touch the finance database
or the local LLM — it only produces an OAuth token file.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    settings = get_settings()
    credentials_path = settings.gmail_credentials_file
    token_path = settings.gmail_token_file

    if not credentials_path.exists():
        raise SystemExit(
            f"Missing {credentials_path}. Download your OAuth client (Desktop app) "
            "credentials.json from Google Cloud Console and place it there, or set "
            "FINANCE_GMAIL_CREDENTIALS_PATH to point at it."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f"Saved Gmail token to {token_path}")


if __name__ == "__main__":
    main()

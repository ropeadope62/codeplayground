"""
Shared Google OAuth2 helper for Gmail and Calendar.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

CONFIG_DIR = Path(__file__).parent.parent / "config"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "token.json"


def get_google_credentials() -> Credentials:
    """Get valid Google OAuth2 credentials, refreshing or prompting as needed."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Google credentials not found at {CREDENTIALS_FILE}\n"
            "Follow the README to set up your Google Cloud project and\n"
            "download the OAuth client JSON to config/credentials.json"
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())

    return creds


if __name__ == "__main__":
    print("Authenticating with Google...")
    credentials = get_google_credentials()
    print(f"Authenticated! Token valid: {credentials.valid}")

import os
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

def oauth_config():
    return {
        "base_url": os.getenv("TASTY_BASE_URL", "https://api.tastyworks.com").rstrip("/"),
        "client_id": os.getenv("TASTY_OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("TASTY_OAUTH_CLIENT_SECRET"),
        "refresh_token": os.getenv("TASTY_OAUTH_REFRESH_TOKEN"),
        "access_token": os.getenv("TASTY_OAUTH_ACCESS_TOKEN"),
    }

def get_access_token_from_refresh():
    cfg = oauth_config()

    if not cfg["client_id"] or not cfg["client_secret"] or not cfg["refresh_token"]:
        raise ValueError("Missing OAuth client_id, client_secret, or refresh_token in .env")

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": cfg["refresh_token"],
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
    }

    r = requests.post(
        f"{cfg['base_url']}/oauth/token",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "angad-option-desk/1.0"
        },
        timeout=30
    )

    if r.status_code != 200:
        raise RuntimeError(f"OAuth token refresh failed: {r.status_code} {r.text}")

    return r.json()

def extract_access_token(token_response):
    # Tasty may return either snake_case or kebab-case depending on API wrapper/version
    if "access_token" in token_response:
        return token_response["access_token"]
    if "access-token" in token_response:
        return token_response["access-token"]
    if "data" in token_response:
        data = token_response["data"]
        return data.get("access_token") or data.get("access-token")
    return None

def oauth_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "angad-option-desk/1.0"
    }

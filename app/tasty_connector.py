import os
import requests
from dotenv import load_dotenv

from app.tasty_oauth import get_access_token_from_refresh, extract_access_token, oauth_headers

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

def tasty_config():
    return {
        "auth_mode": os.getenv("TASTY_AUTH_MODE", "password"),
        "env": os.getenv("TASTY_ENV", "sandbox"),
        "base_url": os.getenv("TASTY_BASE_URL", "https://api.cert.tastyworks.com").rstrip("/"),
        "username": os.getenv("TASTY_USERNAME"),
        "password": os.getenv("TASTY_PASSWORD"),
        "account_number": os.getenv("TASTY_ACCOUNT_NUMBER"),
        "read_only": os.getenv("TASTY_READ_ONLY", "true").lower() == "true",
        "order_execution_enabled": os.getenv("TASTY_ORDER_EXECUTION_ENABLED", "false").lower() == "true",
    }

def password_session_token():
    cfg = tasty_config()

    if not cfg["username"] or not cfg["password"]:
        raise ValueError("Missing TASTY_USERNAME or TASTY_PASSWORD in .env")

    url = f"{cfg['base_url']}/sessions"

    payload = {
        "login": cfg["username"],
        "password": cfg["password"],
        "remember-me": False
    }

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code not in [200, 201]:
        raise RuntimeError(f"Tasty session failed: {response.status_code} {response.text}")

    data = response.json()
    return data["data"]["session-token"]

def get_auth_headers():
    cfg = tasty_config()

    if cfg["auth_mode"] == "oauth":
        resp = get_access_token_from_refresh()
        token = extract_access_token(resp)

        if not token:
            raise RuntimeError(f"OAuth response did not contain access token: {resp}")

        return oauth_headers(token)

    token = password_session_token()
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "angad-option-desk/1.0"
    }

def get_accounts():
    cfg = tasty_config()
    url = f"{cfg['base_url']}/customers/me/accounts"
    response = requests.get(url, headers=get_auth_headers(), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch accounts failed: {response.status_code} {response.text}")

    return response.json()

def get_balances(account_number=None):
    cfg = tasty_config()
    account_number = account_number or cfg["account_number"]

    if not account_number:
        raise ValueError("Missing TASTY_ACCOUNT_NUMBER in .env")

    url = f"{cfg['base_url']}/accounts/{account_number}/balances"
    response = requests.get(url, headers=get_auth_headers(), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch balances failed: {response.status_code} {response.text}")

    return response.json()

def get_positions(account_number=None):
    cfg = tasty_config()
    account_number = account_number or cfg["account_number"]

    if not account_number:
        raise ValueError("Missing TASTY_ACCOUNT_NUMBER in .env")

    url = f"{cfg['base_url']}/accounts/{account_number}/positions"
    response = requests.get(url, headers=get_auth_headers(), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch positions failed: {response.status_code} {response.text}")

    return response.json()

def get_nested_option_chain(symbol):
    cfg = tasty_config()
    url = f"{cfg['base_url']}/option-chains/{symbol.upper()}/nested"
    response = requests.get(url, headers=get_auth_headers(), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch option chain failed: {response.status_code} {response.text}")

    return response.json()

def dry_run_order(order_payload, account_number=None):
    cfg = tasty_config()

    if cfg["order_execution_enabled"]:
        raise RuntimeError("Order execution flag is ON. Refusing dry-run until manually reviewed.")

    account_number = account_number or cfg["account_number"]

    if not account_number:
        raise ValueError("Missing TASTY_ACCOUNT_NUMBER in .env")

    url = f"{cfg['base_url']}/accounts/{account_number}/orders/dry-run"
    response = requests.post(url, headers=get_auth_headers(), json=order_payload, timeout=30)

    return {
        "status_code": response.status_code,
        "body": response.json() if response.text else {}
    }

def get_market_data(instrument_type, symbols):
    """
    Fetch market data for multiple symbols.
    instrument_type examples may include: Equity, Equity Option.
    """
    cfg = tasty_config()

    if isinstance(symbols, list):
        symbols_param = ",".join(symbols)
    else:
        symbols_param = symbols

    url = f"{cfg['base_url']}/market-data"
    params = {
        "instrument-type": instrument_type,
        "symbols": symbols_param
    }

    response = requests.get(
        url,
        headers=get_auth_headers(),
        params=params,
        timeout=30
    )

    return {
        "status_code": response.status_code,
        "body": response.json() if response.text else {},
        "url": response.url
    }

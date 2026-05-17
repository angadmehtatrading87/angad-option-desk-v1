import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(BASE_DIR, "config", "ig_config.json")

# Single shared session with browser-like headers — persists cookies and looks
# like a real Chrome browser to Akamai edge nodes.
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://deal.ig.com",
    "Referer": "https://deal.ig.com/",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
})

# Module-level session token store so tokens survive across IGAdapter instances.
# IG session tokens last ~10 min of inactivity; we treat them as valid for 8 min.
_CST: Optional[str] = None
_XSEC: Optional[str] = None
_SESSION_LOGIN_TS: Optional[datetime] = None
_SESSION_MAX_AGE = timedelta(minutes=8)
_CURRENT_ACCOUNT_ID: Optional[str] = None
_CACHED_ACCOUNT_INFO: Optional[dict] = None


def _session_tokens_valid() -> bool:
    if not _CST or not _XSEC or not _SESSION_LOGIN_TS:
        return False
    return datetime.utcnow() < _SESSION_LOGIN_TS + _SESSION_MAX_AGE


def _store_tokens(cst: str, xsec: str) -> None:
    global _CST, _XSEC, _SESSION_LOGIN_TS
    _CST = cst
    _XSEC = xsec
    _SESSION_LOGIN_TS = datetime.utcnow()


def _set_account_id(account_id: str) -> None:
    global _CURRENT_ACCOUNT_ID
    _CURRENT_ACCOUNT_ID = account_id


def _store_account_info(info: dict) -> None:
    global _CACHED_ACCOUNT_INFO
    if info and isinstance(info, dict):
        _CACHED_ACCOUNT_INFO = info


def _clear_tokens() -> None:
    global _CST, _XSEC, _SESSION_LOGIN_TS, _CURRENT_ACCOUNT_ID, _CACHED_ACCOUNT_INFO
    _CST = None
    _XSEC = None
    _SESSION_LOGIN_TS = None
    _CURRENT_ACCOUNT_ID = None
    _CACHED_ACCOUNT_INFO = None


def _think(lo: float = 0.4, hi: float = 1.8) -> None:
    """Random human-like pause between API calls."""
    time.sleep(random.uniform(lo, hi))


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Wrapper that retries once with a longer timeout on ReadTimeout."""
    try:
        return getattr(_SESSION, method)(url, **kwargs)
    except requests.exceptions.Timeout:
        kwargs["timeout"] = 40
        return getattr(_SESSION, method)(url, **kwargs)


def _meter_record(category: str, amount: float = 1.0) -> None:
    """Best-effort cost-cap counter increment. Never blocks the request."""
    try:
        from app.cost_cap_meter import record
        record(category, amount)
    except Exception:
        pass

class IGAdapter:
    def __init__(self):
        with open(CFG_PATH, "r") as f:
            self.cfg = json.load(f)

        self.base_url = self.cfg.get("base_url", "https://api.ig.com/gateway/deal").rstrip("/")
        self.api_key = self.cfg.get("api_key", "")
        self.identifier = self.cfg.get("identifier", "")
        self.password = self.cfg.get("password", "")
        self.account_id = self.cfg.get("account_id", "")
        self.enabled = bool(self.cfg.get("enabled", False))

        # Restore persisted tokens so we don't re-login on every instantiation.
        self.cst: Optional[str] = _CST
        self.x_security_token: Optional[str] = _XSEC

    def _headers(self, auth: bool = False, version: str = "2") -> Dict[str, str]:
        headers = {
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
            "X-IG-API-KEY": self.api_key,
            "Version": version
        }
        if auth:
            if self.cst:
                headers["CST"] = self.cst
            if self.x_security_token:
                headers["X-SECURITY-TOKEN"] = self.x_security_token
        return headers

    def is_ready(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
            "has_identifier": bool(self.identifier),
            "has_password": bool(self.password),
            "has_account_id": bool(self.account_id),
            "watchlist_count": len(self.cfg.get("watchlist", []))
        }

    def login(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "error": "IG disabled in config"}

        # Reuse existing session if tokens are still fresh — avoids hammering
        # the login endpoint (a key bot-detection signal).
        if _session_tokens_valid():
            self.cst = _CST
            self.x_security_token = _XSEC
            cached_body: dict = {"currentAccountId": _CURRENT_ACCOUNT_ID or self.account_id}
            if _CACHED_ACCOUNT_INFO:
                cached_body["accountInfo"] = _CACHED_ACCOUNT_INFO
            return {
                "ok": True,
                "cache_status": "session_reused",
                "has_cst": True,
                "has_x_security_token": True,
                "cst": self.cst,
                "x_security_token": self.x_security_token,
                "body": cached_body,
            }

        payload = {
            "identifier": self.identifier,
            "password": self.password
        }
        r = _request(
            "post",
            f"{self.base_url}/session",
            headers=self._headers(auth=False, version="2"),
            json=payload,
            timeout=20,
        )

        try:
            body = r.json()
        except Exception:
            body = r.text

        out = {
            "ok": r.ok,
            "status_code": r.status_code,
            "body": body
        }

        if r.ok:
            self.cst = r.headers.get("CST")
            self.x_security_token = r.headers.get("X-SECURITY-TOKEN")
            _store_tokens(self.cst or "", self.x_security_token or "")
            _store_account_info((body or {}).get("accountInfo") if isinstance(body, dict) else None)
            out["has_cst"] = bool(self.cst)
            out["has_x_security_token"] = bool(self.x_security_token)
            out["cst"] = self.cst
            out["x_security_token"] = self.x_security_token

            # force-switch to configured account if needed
            if self.account_id:
                current = (body or {}).get("currentAccountId")
                if current != self.account_id:
                    _think(1.0, 2.5)
                    switch = self.switch_account(self.account_id)
                    out["switch_account"] = switch
                    if switch.get("ok"):
                        _think(0.8, 1.8)
                        sess = self.session()
                        out["post_switch_session"] = sess
                        _set_account_id(self.account_id)
                else:
                    _set_account_id(current or "")
        else:
            # Clear stale tokens so next cycle forces a fresh login attempt.
            _clear_tokens()
        return out

    def session(self) -> Dict[str, Any]:
        r = _request(
            "get",
            f"{self.base_url}/session",
            headers=self._headers(auth=True, version="1"),
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def switch_account(self, account_id: str, default_account: bool = True) -> Dict[str, Any]:
        payload = {
            "accountId": account_id,
            "defaultAccount": bool(default_account)
        }
        r = _request(
            "put",
            f"{self.base_url}/session",
            headers=self._headers(auth=True, version="1"),
            json=payload,
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def positions(self) -> Dict[str, Any]:
        _meter_record("ig_api_calls")
        _think(0.5, 1.5)
        r = _request(
            "get",
            f"{self.base_url}/positions",
            headers=self._headers(auth=True, version="2"),
            timeout=20,
        )
        if r.status_code in (401, 403):
            _clear_tokens()
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def market(self, epic: str) -> Dict[str, Any]:
        _meter_record("ig_api_calls")
        r = _request(
            "get",
            f"{self.base_url}/markets/{epic}",
            headers=self._headers(auth=True, version="3"),
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    # IG resolution strings for the /prices endpoint.
    # Documented at https://labs.ig.com/rest-trading-api-reference/service-detail?id=521
    PRICE_RESOLUTIONS = {
        "1m": "MINUTE",
        "5m": "MINUTE_5",
        "15m": "MINUTE_15",
        "30m": "MINUTE_30",
        "1h": "HOUR",
        "4h": "HOUR_4",
        "1d": "DAY",
    }

    def prices(self, epic: str, resolution: str = "5m", max_points: int = 30) -> Dict[str, Any]:
        _meter_record("ig_api_calls")
        """
        Fetch historical OHLC candles for an epic at a given resolution.

        Args:
            epic: IG epic, e.g. "CS.D.EURUSD.DBM.IP"
            resolution: One of the keys of `PRICE_RESOLUTIONS` ("5m", "15m", "1h", "4h", ...)
                        or a raw IG resolution string like "MINUTE_5".
            max_points: Number of bars to request. IG enforces a 10k-points/week
                        budget per app key, so callers should cache aggressively.

        Returns:
            {ok, status_code, body, points_consumed} — `points_consumed` is the
            number of price points IG charged this request (read from the
            `metadata.allowance.remainingAllowance` delta if present, else
            `len(prices)`).
        """
        ig_resolution = self.PRICE_RESOLUTIONS.get(resolution, resolution)
        r = _request(
            "get",
            f"{self.base_url}/prices/{epic}",
            headers=self._headers(auth=True, version="3"),
            params={"resolution": ig_resolution, "max": int(max_points), "pageSize": 0},
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text

        points_consumed = 0
        if isinstance(body, dict):
            prices = body.get("prices") or []
            points_consumed = len(prices)

        return {
            "ok": r.ok,
            "status_code": r.status_code,
            "body": body,
            "points_consumed": points_consumed,
        }

    def watchlist_snapshot(self) -> Dict[str, Any]:
        markets = []
        for epic in self.cfg.get("watchlist", []):
            markets.append({
                "epic": epic,
                "snapshot": self.market(epic)
            })
        return {"ok": True, "markets": markets}

    def open_position(
        self,
        epic: str,
        direction: str,
        size: float,
        stop_distance: Optional[float] = None,
        limit_distance: Optional[float] = None,
        currency_code: str = "USD",
        expiry: str = "-"
    ) -> Dict[str, Any]:
        # Cost cap: trading-killed flips when ig_orders_submitted_per_day cap
        # is breached. Refuse to submit further orders until next-day rollover.
        try:
            from app.cost_cap_meter import is_killed
            if is_killed("trading_killed"):
                return {
                    "ok": False,
                    "status_code": 0,
                    "body": {"error": "blocked_by_cost_cap", "reason": "trading_killed"},
                }
        except Exception:
            pass
        _meter_record("ig_api_calls")
        _meter_record("ig_orders_submitted")
        payload = {
            "epic": epic,
            "expiry": expiry,
            "direction": direction.upper(),
            "size": size,
            "orderType": "MARKET",
            "currencyCode": currency_code,
            "forceOpen": True,
            "guaranteedStop": False
        }
        if stop_distance is not None:
            payload["stopDistance"] = stop_distance
        if limit_distance is not None:
            payload["limitDistance"] = limit_distance

        r = _request(
            "post",
            f"{self.base_url}/positions/otc",
            headers=self._headers(auth=True, version="2"),
            json=payload,
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def confirm(self, deal_reference: str) -> Dict[str, Any]:
        r = _request(
            "get",
            f"{self.base_url}/confirms/{deal_reference}",
            headers=self._headers(auth=True, version="1"),
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def close_position(self, deal_id: str, direction: str, size: float, expiry: str = "-") -> Dict[str, Any]:
        payload = {
            "dealId": deal_id,
            "direction": direction.upper(),
            "size": size,
            "orderType": "MARKET",
            "expiry": expiry
        }
        headers = {**self._headers(auth=True, version="1"), "_method": "DELETE"}
        r = _request(
            "post",
            f"{self.base_url}/positions/otc",
            headers=headers,
            json=payload,
            timeout=20,
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

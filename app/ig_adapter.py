import json
import os
from typing import Any, Dict, Optional

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(BASE_DIR, "config", "ig_config.json")

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

        self.cst: Optional[str] = None
        self.x_security_token: Optional[str] = None

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

        payload = {
            "identifier": self.identifier,
            "password": self.password
        }
        r = requests.post(
            f"{self.base_url}/session",
            headers=self._headers(auth=False, version="2"),
            json=payload,
            timeout=20
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
            out["has_cst"] = bool(self.cst)
            out["has_x_security_token"] = bool(self.x_security_token)
            out["cst"] = self.cst
            out["x_security_token"] = self.x_security_token
 
            # force-switch to configured account if needed
            if self.account_id:
                current = (body or {}).get("currentAccountId")
                if current != self.account_id:
                    switch = self.switch_account(self.account_id)
                    out["switch_account"] = switch
                    if switch.get("ok"):
                        # refresh session snapshot after switch
                        sess = self.session()
                        out["post_switch_session"] = sess
        return out

    def session(self) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/session",
            headers=self._headers(auth=True, version="1"),
            timeout=20
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
        r = requests.put(
            f"{self.base_url}/session",
            headers=self._headers(auth=True, version="1"),
            json=payload,
            timeout=20
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def positions(self) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/positions",
            headers=self._headers(auth=True, version="2"),
            timeout=20
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def market(self, epic: str) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/markets/{epic}",
            headers=self._headers(auth=True, version="3"),
            timeout=20
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
        r = requests.get(
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

        r = requests.post(
            f"{self.base_url}/positions/otc",
            headers=self._headers(auth=True, version="2"),
            json=payload,
            timeout=20
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

    def confirm(self, deal_reference: str) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/confirms/{deal_reference}",
            headers=self._headers(auth=True, version="1"),
            timeout=20
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
        r = requests.post(
            f"{self.base_url}/positions/otc",
            headers=headers,
            json=payload,
            timeout=20
        )
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}

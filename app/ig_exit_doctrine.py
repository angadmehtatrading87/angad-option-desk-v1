def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def get_exit_thresholds():
    return {
        "small_profit_r": 0.35,
        "meaningful_profit_r": 0.75,
        "strong_profit_r": 1.25,
        "trim_fraction_meaningful": 0.50,
        "trim_fraction_strong": 0.50,
        "giveback_pct_after_0_75r": 0.35,
        "giveback_pct_after_1_25r": 0.25,
        "giveback_pct_after_2r": 0.15,
        "minimum_hold_minutes_for_trim": 3,
        "reentry_cooldown_minutes": 20,
    }


def classify_profit_state(current_pnl_points, risk_points):
    current = _safe_float(current_pnl_points)
    risk = max(_safe_float(risk_points), 1e-9)
    r_mult = current / risk

    if current <= 0:
        return {"profit_state": "not_in_profit", "r_multiple": round(r_mult, 3)}
    if r_mult < 0.35:
        return {"profit_state": "small_profit", "r_multiple": round(r_mult, 3)}
    if r_mult < 0.75:
        return {"profit_state": "building_profit", "r_multiple": round(r_mult, 3)}
    if r_mult < 1.25:
        return {"profit_state": "meaningful_profit", "r_multiple": round(r_mult, 3)}
    return {"profit_state": "strong_profit", "r_multiple": round(r_mult, 3)}


def get_giveback_limit_pct(r_multiple):
    r_multiple = _safe_float(r_multiple)
    t = get_exit_thresholds()
    if r_multiple >= 2.0:
        return t["giveback_pct_after_2r"]
    if r_multiple >= 1.25:
        return t["giveback_pct_after_1_25r"]
    if r_multiple >= 0.75:
        return t["giveback_pct_after_0_75r"]
    return None


def evaluate_giveback_protection(current_pnl_points, peak_pnl_points, r_multiple):
    current = _safe_float(current_pnl_points)
    peak = _safe_float(peak_pnl_points)
    if current <= 0 or peak <= 0 or peak < current:
        return {
            "giveback_pct": 0.0,
            "giveback_limit_pct": get_giveback_limit_pct(r_multiple),
            "triggered": False,
        }

    giveback = peak - current
    giveback_pct = giveback / peak if peak > 0 else 0.0
    limit_pct = get_giveback_limit_pct(r_multiple)
    triggered = bool(limit_pct is not None and giveback_pct >= limit_pct)

    return {
        "giveback_pct": round(giveback_pct, 4),
        "giveback_limit_pct": limit_pct,
        "triggered": triggered,
    }


def evaluate_exit_bias(
    profit_state,
    current_pnl_points,
    r_multiple,
    regime="range",
    regime_conviction=0.0,
    session=None,
    spread_quality="acceptable",
    momentum_quality="mixed",
    book_fragility=0.0,
    duplicate_symbol=False,
    heavy_book=False,
):
    current = _safe_float(current_pnl_points)
    conviction = _safe_float(regime_conviction)
    fragility = _safe_float(book_fragility)

    reasons = []

    if current <= 0:
        return {
            "action": "HOLD",
            "partial_fraction": 0.0,
            "trail_tight": False,
            "reasons": ["not_in_profit"],
        }

    if regime == "range":
        reasons.append("range_regime_profit_should_be_monetized")

    if momentum_quality in ("weak", "fading"):
        reasons.append("momentum_weakening")

    if spread_quality in ("wide", "poor", "bad"):
        reasons.append("spread_not_supportive")

    if duplicate_symbol:
        reasons.append("duplicate_symbol_exposure")

    if heavy_book:
        reasons.append("crowded_book")

    if fragility >= 60:
        reasons.append("book_fragility_elevated")

    if session in ("late_us", "friday_reduction", "friday_close_window", "weekend_closed"):
        reasons.append("session_deteriorating")

    if profit_state == "strong_profit" and regime == "trend" and conviction >= 55 and momentum_quality in ("good", "strong"):
        return {
            "action": "TRAIL_TIGHT",
            "partial_fraction": 0.0,
            "trail_tight": True,
            "reasons": ["strong_profit_with_trend_continuation"],
        }

    if profit_state in ("meaningful_profit", "strong_profit"):
        if regime == "range" or fragility >= 60 or duplicate_symbol or heavy_book or momentum_quality in ("weak", "fading"):
            return {
                "action": "TRIM_PARTIAL",
                "partial_fraction": 0.50,
                "trail_tight": True,
                "reasons": reasons or ["meaningful_profit_take_some_off"],
            }

    if profit_state == "strong_profit" and (regime == "range" or momentum_quality in ("weak", "fading") or spread_quality in ("wide", "poor", "bad")):
        return {
            "action": "CLOSE_FULL",
            "partial_fraction": 1.0,
            "trail_tight": False,
            "reasons": reasons or ["strong_profit_no_reason_to_hold"],
        }

    return {
        "action": "HOLD",
        "partial_fraction": 0.0,
        "trail_tight": False,
        "reasons": reasons or ["profit_present_but_hold_allowed"],
    }

def analyze(context: dict):
    return [{"issue": "no real candle data", "evidence": "data source unavailable", "severity": "high", "recommended_fix": "integrate validated candle provider", "suggested_module": "app/market_data adapters", "codex_should_create_pr": True, "priority": "P1"}]

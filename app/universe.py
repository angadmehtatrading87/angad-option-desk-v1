import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_trading_universe():
    path = os.path.join(BASE_DIR, "config", "trading_universe.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_universe_symbols():
    cfg = load_trading_universe() or {}
    return [str(x).upper() for x in cfg.get("symbols", [])]

def get_universe_rules():
    cfg = load_trading_universe() or {}
    return cfg.get("rules", {})

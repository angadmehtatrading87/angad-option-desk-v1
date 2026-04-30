import time
from app.trading_window import can_open_new_option_trade
from app.virtual_portfolio import list_open_virtual_positions, virtual_account_snapshot
from app.spread_builder import propose_spread_candidates
from app.universe import get_universe_symbols, get_universe_rules

def main():
    while True:
        try:
            allowed, _ = can_open_new_option_trade()
            open_positions = list_open_virtual_positions()
            snapshot = virtual_account_snapshot()

            max_open = int(snapshot.get("max_open_virtual_trades", 2))
            cash = float(snapshot.get("cash_balance", 0))
            min_reserve = float(snapshot.get("min_reserve_cash", 300))

            if len(open_positions) >= max_open:
                time.sleep(60)
                continue

            if cash <= min_reserve:
                time.sleep(60)
                continue

            if not allowed:
                time.sleep(300)
                continue

            symbols = get_universe_symbols()
            rules = get_universe_rules()
            max_candidates_per_cycle = int(rules.get("max_candidates_per_cycle", 2))

            created_total = 0
            for symbol in symbols:
                created = propose_spread_candidates(symbol)
                actionable = [x for x in created if x.get("status") == "PENDING_APPROVAL"]
                if actionable:
                    created_total += len(actionable)
                if created_total >= max_candidates_per_cycle:
                    break

            time.sleep(60)

        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()

from app.exit_brain import evaluate_exit_decisions
from app.virtual_portfolio import close_virtual_position

def evaluate_open_positions():
    return evaluate_exit_decisions()

def close_position_now(position_id, exit_price, note=""):
    return close_virtual_position(position_id=position_id, exit_price=exit_price, note=note)

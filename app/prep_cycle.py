from app.market_prep_brain import build_market_prep_state
from app.universe_selector import build_dynamic_universe
from app.opportunity_ranker import rank_opportunities
from app.session_plan import build_session_plan

def run_full_prep_cycle():
    build_market_prep_state()
    build_dynamic_universe()
    rank_opportunities()
    build_session_plan()
    return {"status": "ok"}

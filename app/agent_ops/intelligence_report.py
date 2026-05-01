LEVELS={1:"basic signal bot",2:"safety-gated execution",3:"two-phase protected execution",4:"Market Brain shadow intelligence",5:"ranked opportunity recommendations",6:"capital allocation intelligence",7:"controlled demo execution from Market Brain",8:"adaptive learning from outcomes",9:"multi-asset autonomous trading",10:"production-grade institutional trading agent"}

def generate(runtime:dict)->dict:
    level=4
    return {"market_brain_status":runtime.get("execution_mode","shadow"),"last_scan_time":runtime.get("market_brain_last_scan_time"),"market_regime":"unavailable","top_opportunities":[],"rejected_opportunities":[],"capital_allocation_recommendations":["Prefer fewer higher-conviction trades"],"candle_data":"unavailable","news_data":"unavailable","sentiment_data":"unavailable","intelligence_maturity_level":level,"intelligence_maturity_label":LEVELS[level]}

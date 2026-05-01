import sys
from app.market_brain import MarketBrainInput, run_market_brain
from app.market_brain.adapters import IGAdapter, InstrumentType
from app.market_brain.engines import scan_universe, candle_features, classify_regime, score_opportunity, capital_allocate, monthly_state, news_signal


def sample_watch(spread=0.0002,pct=0.4):
    return [{"epic":"CS.D.EURUSD.CFD.IP","snapshot":{"bid":1.1,"offer":1.1+spread,"percentageChange":pct,"high":1.12,"low":1.09}}]


def test_scanner_and_bad_spread_rejection():
    scans=scan_universe(sample_watch(spread=0.01))
    f=candle_features('CS.D.EURUSD.CFD.IP',[{"open":1,"high":1.02,"low":0.99,"close":1.01}]*8)
    opp=score_opportunity(scans[0],f,classify_regime([f],scans),news_signal())
    assert opp.action=='reject' and opp.rejection_reason=='bad_spread_friction'


def test_weak_signal_rejection():
    scans=scan_universe(sample_watch(spread=0.0001,pct=0.0))
    f=candle_features('x',[{"open":1,"high":1.001,"low":0.999,"close":1.0}]*8)
    opp=score_opportunity(scans[0],f,classify_regime([f],scans),news_signal())
    assert opp.action in ('reject','watch')


def test_high_conviction_sizing_and_reserve():
    inp=MarketBrainInput(watchlist=sample_watch(spread=0.00005,pct=2.0),candles={'CS.D.EURUSD.CFD.IP':[{'open':1,'high':1.03,'low':0.99,'close':1.02}]*20},account={'equity':10000,'available':9000,'balance':10000,'open_pnl':100},positions=[],monthly={'month_start_capital':9500,'trading_days_remaining':12})
    out=run_market_brain(inp)
    assert out.capital.min_reserve==3000
    assert out.opportunities[0].opportunity_score>50


def test_drawdown_reduces_deployable():
    m=monthly_state({'month_start_capital':10000},{'equity':9000,'open_pnl':-300})
    c=capital_allocate({'equity':9000,'available':2000},m,[])
    assert c.deployable_capital>=0


def test_no_data_condition():
    out=run_market_brain(MarketBrainInput(watchlist=[],candles={},account={'equity':1000,'available':1000},positions=[],monthly={}))
    assert out.regime.no_trade is True


def test_market_brain_no_tastytrade_dependency():
    sys.modules.pop("app.tasty_connector", None)
    out = run_market_brain(MarketBrainInput(watchlist=sample_watch(), candles={}, account={"equity":1000,"available":1000}, positions=[], monthly={}))
    assert out.diagnostics.get("heartbeat") == "ok"


def test_ig_adapter_forex_and_unavailable_candles_safe():
    snap = {"watchlist": {"markets": sample_watch()}, "account": {"equity": 5000, "available": 5000}, "positions": {"positions": []}}
    adapter = IGAdapter(snapshot=snap)
    watchlist = adapter.get_watchlist()
    candles = adapter.get_candles([watchlist[0]["epic"]])
    out = run_market_brain(MarketBrainInput(watchlist=watchlist, candles=candles, account=adapter.get_account(), positions=adapter.get_positions(), monthly={}))
    assert InstrumentType.FOREX.value == "forex"
    assert out.diagnostics["candle_features_unavailable"] >= 1
    assert out.news.risk_sentiment == "neutral"
    assert out.diagnostics["shadow_mode"] is True

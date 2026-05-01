from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from .models import *


def _f(v, d=0.0):
    try:return float(v)
    except Exception:return d


def scan_universe(watchlist: list[dict]) -> list[MarketScanResult]:
    out=[]
    for m in watchlist:
        snap=(m.get('snapshot') or {}).get('body',{}).get('snapshot',{}) if (m.get('snapshot') or {}).get('body') else (m.get('snapshot') or {})
        epic=m.get('epic','UNKNOWN')
        bid=_f(snap.get('bid')); offer=_f(snap.get('offer')); pct=abs(_f(snap.get('percentageChange')))
        spread=max(offer-bid,0.0); mid=(offer+bid)/2 if offer and bid else max(offer,bid,1)
        spread_bps=(spread/mid)*10000 if mid>0 else 1e6
        liquidity=max(0.0, min(100.0, 100 - spread_bps*2.5))
        mover=min(100.0, pct*220)
        quiet=pct < 0.08
        trend_clean=min(100.0, max(0.0, mover - (spread_bps*0.9)))
        out.append(MarketScanResult(epic, spread_bps, 100-liquidity, liquidity, mover, quiet, trend_clean))
    return out


def candle_features(epic:str, candles:list[dict]) -> CandleFeatures:
    if len(candles)<3:
        return CandleFeatures(epic,*([0.0]*15))
    closes=[_f(c.get('close')) for c in candles if _f(c.get('close'))>0]
    highs=[_f(c.get('high')) for c in candles]; lows=[_f(c.get('low')) for c in candles]; opens=[_f(c.get('open')) for c in candles]
    n=len(closes)
    t5=((closes[-1]-closes[-3])/closes[-3])*100 if n>=3 and closes[-3] else 0
    t1h=((closes[-1]-closes[max(0,n-12)])/closes[max(0,n-12)])*100 if n>=12 and closes[max(0,n-12)] else t5
    t4h=((closes[-1]-closes[0])/closes[0])*100 if closes and closes[0] else 0
    mom=t5*0.6+t1h*0.4
    body=abs(closes[-1]-opens[-1]); rng=max(highs[-1]-lows[-1],1e-9)
    body_q=min(100, (body/rng)*100)
    wick=abs((highs[-1]-max(closes[-1],opens[-1]))-(min(closes[-1],opens[-1])-lows[-1]))/rng*100
    breakout=max(0.0, min(100.0, ((closes[-1]-max(closes[-6:-1]))/max(closes[-6:-1],default=1))*500 if n>6 else 0))
    breakdown=max(0.0, min(100.0, ((min(closes[-6:-1],default=0)-closes[-1])/max(closes[-1],1))*500 if n>6 else 0))
    gap=((opens[-1]-closes[-2])/max(closes[-2],1))*100 if n>2 else 0
    comp=max(0.0, 100-min(100, ((highs[-1]-lows[-1])/max(closes[-1],1))*10000))
    exp=100-comp
    mean_rev=max(0.0, min(100.0, abs(mom)*1.8 if mom<0 else abs(mom)*0.7))
    cont=max(0.0, min(100.0, mom*2 if mom>0 else 0))
    fail=max(0.0, min(100.0, wick*0.8 + (100-body_q)*0.4))
    return CandleFeatures(epic,t5,t1h,t4h,mom,body_q,wick,breakout,breakdown,gap,20.0,comp,exp,mean_rev,cont,fail)


def classify_regime(features:list[CandleFeatures], scans:list[MarketScanResult])->RegimeSignal:
    if not features:return RegimeSignal('no-trade / poor edge',85,True,'No market data')
    avg_mom=sum(f.momentum for f in features)/len(features)
    avg_exp=sum(f.vol_expansion for f in features)/len(features)
    avg_liq=sum(s.liquidity_score for s in scans)/max(len(scans),1)
    label='range-bound'
    if avg_liq<35: label='liquidity-thin'
    elif avg_exp>60 and abs(avg_mom)>0.5: label='high-volatility'
    elif abs(avg_mom)>1.2: label='strong trend'
    elif abs(avg_mom)>0.4: label='weak trend'
    no_trade= label in ('liquidity-thin',) or (label=='range-bound' and avg_exp<35)
    return RegimeSignal(label, round(min(95,max(40,50+abs(avg_mom)*10)),2), no_trade, f'avg_momentum={avg_mom:.2f}, avg_exp={avg_exp:.1f}')


def news_signal()->NewsSignal:
    return NewsSignal(False,'neutral',None,0,'News adapter not connected; neutral confidence.')


def monthly_state(monthly:dict, account:dict)->MonthlyObjectiveState:
    start=_f(monthly.get('month_start_capital', account.get('balance',10000)),10000)
    current=_f(account.get('equity', start), start)
    realized=_f(monthly.get('realized_pnl',0)); unrl=_f(account.get('open_pnl',0))
    ret=((current-start)/start)*100 if start else 0
    req=max(0.0,4.0-ret)
    days=int(monthly.get('trading_days_remaining',10))
    status='ahead' if ret>5 else 'on_track' if ret>=4 else 'behind'
    return MonthlyObjectiveState(start,current,realized,unrl,round(ret,3),4.0,5.0,round(req,3),days,status)


def score_opportunity(scan:MarketScanResult, feat:CandleFeatures, regime:RegimeSignal, news:NewsSignal)->OpportunityScore:
    direction='long' if feat.momentum>=0 else 'short'
    trend=min(100,max(0,50+feat.trend_1h*6))
    momentum=min(100,max(0,50+feat.momentum*8))
    vol=feat.vol_expansion
    candle=(feat.body_quality*0.5 + (100-feat.failed_breakout_risk)*0.5)
    regime_align=75 if 'trend' in regime.label else 45
    news_c=50 if news.confidence is None else news.confidence
    friction=max(0,100-scan.friction_score)
    liq=scan.liquidity_score
    rr=max(0.5, min(4.0, 1.0 + abs(feat.momentum)/2.0))
    raw=(trend*0.13+momentum*0.14+vol*0.08+candle*0.1+friction*0.12+liq*0.12+regime_align*0.11+news_c*0.04+rr*20*0.16)
    confidence=min(95,max(20, raw*0.92))
    action='trade'
    reject=None
    if scan.spread_bps>35: action='reject'; reject='bad_spread_friction'
    elif regime.no_trade: action='watch'; reject='regime_no_trade'
    elif raw<52: action='reject'; reject='weak_signal'
    return OpportunityScore(scan.epic,direction,round(raw,2),round(confidence,2),round(raw/100,3),0.01,round(rr*0.01,3),round(rr,2),round(scan.spread_bps/10000,5),action,reject,{"trend":trend,"momentum":momentum})


def capital_allocate(account:dict, monthly:MonthlyObjectiveState, opps:list[OpportunityScore])->CapitalAllocationRecommendation:
    total=_f(account.get('equity', account.get('balance',0)))
    used=max(0.0,total-_f(account.get('available',total)))
    reserve=total*0.30
    deployable=max(0.0,total-reserve-used)
    best=max([o.opportunity_score for o in opps if o.action=='trade']+[0])
    on_track=monthly.status in ('on_track','ahead')
    note='Preserve capital in weak opportunity environment.'
    if best>=75: note='High conviction setup allows higher utilization in shadow recommendation mode.'
    elif best>=60: note='Moderate conviction; selective capital deployment recommended.'
    return CapitalAllocationRecommendation(total,reserve,used,deployable,used,total-used,on_track,4.0,5.0,note)


def thesis_for(opp:OpportunityScore, regime:RegimeSignal, alloc:CapitalAllocationRecommendation)->TradeThesis:
    size=0.0 if opp.action!='trade' else round(max(0.0, alloc.deployable_capital)*min(0.25, opp.confidence_score/400),2)
    stance='not at all' if opp.action!='trade' else 'aggressively' if opp.opportunity_score>=75 else 'moderately'
    return TradeThesis(opp.epic,opp.direction,'Relative strength + liquidity quality','Momentum/regime alignment','Score improved versus peers','Breakout/continuation context',regime.label,'Loss of structure or spread deterioration','1-2 ATR equivalent move','Structure-based invalidation under recent swing','Scale at RR tiers and volatility behavior',f'RR {opp.rr_ratio}:1',size,opp.confidence_score,stance)


def run_market_brain(inp:MarketBrainInput)->MarketBrainOutput:
    scans=scan_universe(inp.watchlist)
    feats=[candle_features(e, inp.candles.get(e,[])) for e in [s.epic for s in scans]]
    regime=classify_regime(feats, scans)
    news=news_signal()
    monthly=monthly_state(inp.monthly, inp.account)
    opps=[score_opportunity(s, next((f for f in feats if f.epic==s.epic), candle_features(s.epic,[])), regime, news) for s in scans]
    opps=sorted(opps,key=lambda x:x.opportunity_score, reverse=True)
    alloc=capital_allocate(inp.account, monthly, opps)
    thesis=[thesis_for(o, regime, alloc) for o in opps[:5]]
    rej=[o for o in opps if o.action=='reject']
    return MarketBrainOutput(datetime.now(timezone.utc).isoformat(), regime, news, monthly, alloc, opps[:10], thesis, rej[:10], {'scanned':len(scans),'heartbeat':'ok','shadow_mode':True})

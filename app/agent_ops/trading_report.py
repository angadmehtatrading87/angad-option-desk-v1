from datetime import datetime, timezone

def _f(x):
    try:return float(x or 0)
    except: return 0.0

def generate(db):
    trades=db.query("ig_trade_log","SELECT epic,status,size,created_at FROM ig_trade_log ORDER BY created_at DESC")
    if trades['status']!='ok': return {"status":"unavailable"}
    eq=db.query("virtual_equity_log","SELECT * FROM virtual_equity_log ORDER BY timestamp DESC LIMIT 2")
    acct=db.query("virtual_account","SELECT * FROM virtual_account ORDER BY updated_at DESC LIMIT 1")
    pos=db.query("virtual_positions","SELECT * FROM virtual_positions")
    rows=trades['rows']; total=len(rows); submitted=sum(1 for r in rows if str(r.get('status','')).lower() in {'submitted','filled','accepted'}); rejected=total-submitted
    open_positions=sum(1 for r in pos.get('rows',[]) if str(r.get('status','')).lower()=='open') if pos['status']=='ok' else 'unavailable'
    closed=sum(1 for r in pos.get('rows',[]) if str(r.get('status','')).lower()=='closed') if pos['status']=='ok' else 'unavailable'
    realized=unreal=equity='unavailable'
    if eq['status']=='ok' and eq['rows']:
      top=eq['rows'][0]; realized=_f(top.get('realized_pnl')); unreal=_f(top.get('unrealized_pnl')); equity=_f(top.get('total_equity'))
    cash='unavailable'; start='unavailable'
    if acct['status']=='ok' and acct['rows']:
      cash=_f(acct['rows'][0].get('cash_balance')); start=_f(acct['rows'][0].get('starting_capital'))
    monthly_return=((equity-start)/start*100) if isinstance(equity,float) and isinstance(start,float) and start else 'unavailable'
    return {"status":"ok","total_trades":total,"submitted_trades":submitted,"rejected_or_skipped":rejected,"closed_trades":closed,"open_positions":open_positions,"win_loss":"unavailable","realized_pnl":realized,"unrealized_pnl":unreal,"total_equity":equity,"drawdown":"unavailable","capital_used":(start-cash if isinstance(start,float) and isinstance(cash,float) else 'unavailable'),"capital_unused":cash,"average_trade_size":sum(_f(r.get('size')) for r in rows)/total if total else 0,"best_symbol":"unavailable","worst_symbol":"unavailable","monthly_return_pct":monthly_return,"target_progress":"unavailable" if monthly_return=='unavailable' else ("on_track" if monthly_return>=4 else "behind"),"low_capital_utilization":'unavailable',"overtrading_small_trades":total>40}

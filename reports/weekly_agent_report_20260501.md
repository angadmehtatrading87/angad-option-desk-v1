# Weekly Agent Report (20260501)

## Executive Summary
Agent Ops Controller snapshot generated for operator visibility.

## Development Progress
- Current phase: agent_ops_control_layer
- Latest commit: 11f269f 2026-05-01 Add Agent Ops Controller with reporting and dashboard integration

## Trading Performance
- Weekly P&L: unavailable
- Monthly P&L: unavailable

## Capital Utilization
- Capital utilization: unavailable
- Deployable capital: unavailable

## Market Brain Status
- Shadow status: {'mode': 'shadow', 'last_scan_time': None}

## Runtime Health
- Runtime: {'ig_worker_alive': False, 'last_loop_time': None, 'last_signal_time': None, 'last_intent_time': None, 'last_trade_time': None, 'last_rejection_reason': None, 'execution_mode': 'shadow', 'safety_gate_status': 'enabled', 'two_phase_commit_status': 'enabled', 'market_brain_last_scan_time': None, 'api_data_freshness': 'unknown', 'updated_at': '2026-05-01T09:44:12.985663+00:00'}

## Intelligence Level
- Scorecard: {'safety_controls_level': 5, 'execution_protection_level': 5, 'market_scanning_level': 4, 'candle_intelligence_level': 4, 'news_sentiment_level': 3, 'capital_allocation_level': 4, 'learning_feedback_level': 3, 'dashboard_visibility_level': 4, 'overall_intelligence_maturity_level': 4.0}

## Problems Found
- ['Trading performance depends on executed_trades schema availability']

## Next Recommended PRs/Tasks
- ['Wire live runtime heartbeat producer', 'Add richer PR metadata ingestion']

# Agent Ops Controller

## Run controller snapshot
`python -m app.agent_ops_controller`

## Generate weekly report
`python -m app.agent_ops_controller --weekly-report`

This saves `reports/weekly_agent_report_YYYYMMDD.md` and prints it.

## Intelligence level
The scorecard returns subsystem levels plus an overall maturity level average.

## Capital utilization
Capital utilization = total traded size / deployable capital from available trade data. If data is missing, the report marks fields as unavailable.

## Why this reduces manual coordination
A single module and report surface development state, runtime health, market-brain status, safety posture, and trading outcomes so operators no longer need to manually correlate terminal output, git logs, dashboard, and runtime files.

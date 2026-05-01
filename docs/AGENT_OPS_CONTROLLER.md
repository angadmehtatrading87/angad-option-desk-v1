# Agent Ops Controller
Run weekly report: `python -m app.agent_ops.cli weekly-report`
Run approval: `python -m app.agent_ops.cli request-weekend-approval`
Run weekend deploy: `python -m app.agent_ops.cli weekend-deploy --approved`
Rollback occurs automatically on failed compile/tests.
Requires Angad approval for deployment.

## Telegram Control Room policy
- Telegram Control Room is not a trade approval terminal.
- Trading agent remains autonomous within configured risk/safety rules.
- Angad approves code deployments/system upgrades only.
- Emergency kill switch is available for shutdown and controlled resume.


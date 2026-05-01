# Agent Ops Controller
Run weekly report: `python -m app.agent_ops.cli weekly-report`
Run approval: `python -m app.agent_ops.cli request-weekend-approval`
Run weekend deploy: `python -m app.agent_ops.cli weekend-deploy --approved`
Rollback occurs automatically on failed compile/tests.
Requires Angad approval for deployment.

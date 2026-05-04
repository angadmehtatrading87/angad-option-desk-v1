# Autonomous Engineering Factory

## Setup
- Configure `.env` with Telegram auth and optional SMTP.
- Run `python3 -m app.agent_ops.cli weekly-report` and `python3 -m app.telegram_control_room.cli status`.

## Components
- Repo/GitHub manager via `app.agent_ops.factory.github_repo_manager`.
- Codex improvement brief via `app.agent_ops.factory.generate_codex_improvement_brief`.
- CI/Test hooks: compile + pytest + systemd checks.
- Weekend deployment + rollback through `app.agent_ops.weekend_deployer`.

## Approval workflow
1. Generate approval request file in `reports/latest_deployment_approval.md`.
2. Approve using Telegram `/approve_deploy APPROVE WEEKEND DEPLOYMENT`.
3. Deployment still blocked on weekdays unless `force=True` from trusted operator context.

## Rollback
- Automatic rollback on deploy gate failure restores DB/runtime backups.
- Manual rollback uses `app.agent_ops.rollback_manager`.

## Known limitations
- PR tracking is local-git derived unless GitHub token integration is added.
- Service-health commands depend on `systemctl` availability.

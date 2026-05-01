# Weekend Deployment Runbook
Install timers/services with `sudo cp deploy/systemd/*.service /etc/systemd/system/` and `.timer` similarly.
Enable: `sudo systemctl enable --now agent-ops-weekly-report.timer agent-ops-weekend-approval.timer`.
Check worker: `systemctl status ig-execution-worker`.

# Server Operations

## Health checks
- CPU/memory/disk: via host telemetry (platform dependent).
- Process/systemd state: `systemctl is-active` for key units.
- Journal parsing: inspect `journalctl -u <unit> -n 200`.

## Required units
- ig-execution-worker.service
- telegram-control-room.service
- agent-ops-weekly-report.service/timer
- agent-ops-weekend-approval.service/timer
- research-daily.service/timer
- research-weekly.service/timer

## DB scope
Operational checks use:
- ig_trade_log
- virtual_equity_log
- virtual_account
- virtual_positions
- trade_proposals
- learning_log

# Telegram Control Room

Telegram is for monitoring, deployment approval, and emergency controls only. It is not a trade approval terminal.

## Setup
1. Use BotFather to create bot and set `TELEGRAM_BOT_TOKEN`.
2. Get your chat id and set `TELEGRAM_ALLOWED_CHAT_ID`.
3. Keep env vars in server environment, never commit secrets.

## Commands
/status, /trades_today, /performance, /intelligence, /research, /github, /report, /approval, /approve_deploy, /reject_deploy, /kill_switch, /system_resume, /help

## Deployment approval workflow
- `/approval` shows pending weekend deployment request only.
- `/approve_deploy APPROVE WEEKEND DEPLOYMENT` records approval.
- `/reject_deploy` records rejection.

## Emergency workflow
- `/kill_switch CONFIRM EMERGENCY SHUTDOWN` sets runtime kill switch and writes report.
- `/system_resume CONFIRM SYSTEM RESUME` clears runtime kill switch override.

## systemd
```bash
sudo cp deploy/systemd/telegram-control-room.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-control-room.service
sudo systemctl status telegram-control-room.service
```

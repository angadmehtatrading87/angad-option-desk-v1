from .auth import is_authorized_chat
from .commands import render_status, render_performance, render_github, render_approval, render_help, render_positions, render_capital, render_risk, render_why_no_trade
from .approval_handler import approve_deployment, reject_deployment
from .kill_switch import activate_kill_switch, resume_system


class TelegramControlRoomBot:
    def handle_command(self, chat_id: str, text: str) -> str:
        if not is_authorized_chat(chat_id):
            return "Unauthorized chat id."
        cmd, _, arg = (text or "").partition(" ")
        if cmd == "/status":
            return render_status()
        if cmd == "/performance":
            return render_performance()
        if cmd == "/github":
            return render_github()
        if cmd == "/approval":
            return render_approval()
        if cmd == "/approve_deploy":
            ok, msg = approve_deployment(str(chat_id), arg)
            return msg
        if cmd == "/reject_deploy":
            return reject_deployment(str(chat_id))
        if cmd == "/kill_switch":
            ok, msg = activate_kill_switch(str(chat_id), arg)
            return msg
        if cmd == "/system_resume":
            ok, msg = resume_system(str(chat_id), arg)
            return msg
        if cmd == "/positions":
            return render_positions()
        if cmd == "/capital":
            return render_capital()
        if cmd == "/risk":
            return render_risk()
        if cmd == "/why_no_trade":
            return render_why_no_trade()
        if cmd == "/help":
            return render_help()
        if cmd in {"/trades_today", "/intelligence", "/research", "/report"}:
            return "Command supported; data unavailable in this environment."
        return "Unknown command. Use /help."

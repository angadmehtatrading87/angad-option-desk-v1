import os, smtplib
from email.message import EmailMessage

def maybe_send(subject:str,body:str)->str:
    req=["AGENT_OPS_EMAIL_TO","AGENT_OPS_EMAIL_FROM","AGENT_OPS_SMTP_HOST","AGENT_OPS_SMTP_PORT"]
    if not all(os.getenv(k) for k in req): return "email_not_sent_missing_config"
    msg=EmailMessage();msg["To"]=os.environ["AGENT_OPS_EMAIL_TO"];msg["From"]=os.environ["AGENT_OPS_EMAIL_FROM"];msg["Subject"]=subject;msg.set_content(body)
    with smtplib.SMTP(os.environ["AGENT_OPS_SMTP_HOST"],int(os.environ["AGENT_OPS_SMTP_PORT"])) as s:
        if os.getenv("AGENT_OPS_SMTP_USER") and os.getenv("AGENT_OPS_SMTP_PASSWORD"): s.login(os.environ["AGENT_OPS_SMTP_USER"],os.environ["AGENT_OPS_SMTP_PASSWORD"])
        s.send_message(msg)
    return "email_sent"

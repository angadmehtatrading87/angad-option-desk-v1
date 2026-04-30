
import subprocess

SERVICES = [

    "angad-option-desk",

    "angad-ig-transition",

    "angad-ig-decision-audit",

    "angad-ig-execution",

]

def _is_active(service):

    try:

        out = subprocess.check_output(["systemctl", "is-active", service], text=True).strip()

        return out == "active", out

    except Exception as e:

        return False, str(e)

def service_health_snapshot():

    services = {}

    for s in SERVICES:

        active, raw = _is_active(s)

        services[s] = {"active": active, "raw": raw}

    return {"services": services}


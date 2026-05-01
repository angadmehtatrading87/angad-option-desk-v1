from datetime import datetime

def weekend_guard(force:bool=False)->tuple[bool,str]:
    wd=datetime.utcnow().weekday()
    if wd<5 and not force:return False,"Weekend deployment blocked: Monday-Friday requires --force"
    return True,"allowed"

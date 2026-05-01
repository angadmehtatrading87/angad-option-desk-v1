from pathlib import Path
import shutil, subprocess
from .deployment_planner import weekend_guard
from .rollback_manager import restore

def run(repo:Path, approved:bool=False, force:bool=False)->dict:
    ok,msg=weekend_guard(force)
    if not ok:return {"status":"blocked","reason":msg}
    if not approved:return {"status":"blocked","reason":"approval required"}
    bdir=repo/"backups"/"agent_ops_latest"; bdir.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    for p in ["data/trades.db","data/agent_runtime_state.json"]:
        src=repo/p
        if src.exists(): shutil.copy2(src,bdir/src.name)
    steps=[]
    for cmd in [["git","pull","origin","main"],["python3","-m","py_compile","app/*.py"],["pytest","-q","--ignore=backups","--ignore=venv","--ignore=.git"]]:
        rc=subprocess.call(" ".join(cmd),cwd=repo,shell=True);steps.append((cmd,rc))
        if rc!=0:
            rb=restore(bdir,repo,commit)
            return {"status":"rolled_back","steps":steps,"rollback":rb}
    return {"status":"deployed","steps":steps,"previous_commit":commit}

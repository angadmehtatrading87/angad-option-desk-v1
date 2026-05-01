from pathlib import Path
import shutil, subprocess

def restore(backup_dir:Path, repo:Path, commit:str)->dict:
    out={"status":"started"}
    subprocess.call(["git","checkout",commit],cwd=repo)
    for p in ["data/trades.db","data/agent_runtime_state.json"]:
        src=backup_dir/Path(p).name
        if src.exists(): shutil.copy2(src,repo/p)
    out['status']="completed";return out

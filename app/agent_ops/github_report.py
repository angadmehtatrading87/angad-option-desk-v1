import subprocess
from pathlib import Path

def _git(repo:Path,args:list[str]):
    try:return subprocess.check_output(["git",*args],cwd=repo,text=True).strip()
    except Exception:return "unavailable"

def generate(repo:Path)->dict:
    return {"current_branch":_git(repo,["rev-parse","--abbrev-ref","HEAD"]),"latest_local_commit":_git(repo,["log","-1","--pretty=%h %ad %s","--date=iso"]),"recent_merged_prs":[l for l in _git(repo,["log","--max-count=20","--pretty=%s"]).splitlines() if "#" in l or "Merge pull request" in l],"pending_branches":_git(repo,["branch","--format=%(refname:short)"]).splitlines(),"modified_files":_git(repo,["status","--short"]).splitlines(),"tests_available":"pytest", "last_test_result":"unavailable","current_roadmap_phase":"agent-ops-and-research-intelligence","pending_issues":["No GitHub API token configured"]}

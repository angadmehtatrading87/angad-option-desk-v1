import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_agent_policy():
    path = os.path.join(BASE_DIR, "config", "agent_policy.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def get_policy_section(name, default=None):
    policy = load_agent_policy()
    return policy.get(name, default if default is not None else {})

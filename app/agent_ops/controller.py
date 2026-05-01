from datetime import datetime, timezone
from pathlib import Path
from .db_reader import DBReader
from .runtime_health import RuntimeHealthStore
from .trading_report import generate as trading_generate
from .intelligence_report import generate as intel_generate
from .github_report import generate as git_generate

class AgentOpsController:
    def __init__(self, base_dir:Path):
        self.base=Path(base_dir)
        self.db=DBReader(self.base/"data/trades.db")
        self.runtime=RuntimeHealthStore(self.base/"data/agent_runtime_state.json")
    def collect(self):
        runtime=self.runtime.load()
        trading=trading_generate(self.db)
        intel=intel_generate(runtime)
        return {"generated_at":datetime.now(timezone.utc).isoformat(),"runtime_health":runtime,"trading_performance":trading,"market_brain":intel,"development":git_generate(self.base)}

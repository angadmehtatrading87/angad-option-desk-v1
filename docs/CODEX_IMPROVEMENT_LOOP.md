# Codex Improvement Loop

- Run `write_factory_report()` to produce `reports/latest_factory_report.json`.
- Run `generate_codex_improvement_brief()` for dated brief output.
- Feed brief into Codex tasking for bug diagnosis, acceptance criteria, test plans, deploy fixes, and backlog priorities.
- Stabilization trigger: if required DB tables are missing or CI is failing, prioritize stabilization before new features.

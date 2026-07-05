# Security Policy

SkillBench can execute agent commands in `full-agent` mode. Treat eval cases and agent runners as code-adjacent inputs.

## Supported Versions

Security fixes target the latest released version on the `main` branch.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the repository owner before opening a public issue. Include:

- Affected SkillBench version or commit.
- The command or eval case needed to reproduce the behavior.
- Any generated `report.json`, `case_results.jsonl`, or `agent_runs/` evidence with secrets removed.

## Safety Expectations

- Do not publish API keys, private transcripts, or proprietary skill documents in issues.
- Use `--agent-timeout` for `full-agent` runs.
- Review `SKILLBENCH_AGENT_COMMAND` before running third-party eval sets.
- Prefer isolated worktrees or disposable directories for behavior audits.

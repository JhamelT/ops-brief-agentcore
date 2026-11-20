"""Print every tool the agent registers, exactly as main.py builds it."""
import datetime, subprocess, sys
sys.path.insert(0, "app/OpsBriefAgent")
from main import get_or_create_agent

agent = get_or_create_agent("tool-audit")
specs = agent.tool_registry.get_all_tools_config()
sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()

print(f"Tools registered by main.py at commit {sha}")
print(f"Run: {datetime.date.today()}  Command: uv run python scripts/list_tools.py")
print(f"Count: {len(specs)}\n")
for name in sorted(specs):
    desc = (specs[name].get("description") or "").strip().splitlines()[0]
    print(f"- {name}: {desc[:100]}")

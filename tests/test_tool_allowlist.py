"""Guard: the agent registers exactly three read-only tools.

The CLI template shipped an example MCP client that added two web tools
(evidence 08). This test fails if any tool is added, renamed or removed
without someone changing this list on purpose.
"""
from main import get_or_create_agent

EXPECTED_TOOLS = {"alarm_state", "ec2_inventory", "yesterday_spend"}


def test_agent_registers_exactly_the_three_read_only_tools():
    agent = get_or_create_agent("allowlist-test")
    registered = set(agent.tool_registry.get_all_tools_config())
    assert registered == EXPECTED_TOOLS

import os
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient


def get_streamable_http_mcp_client() -> MCPClient:
    """MCP client for the AgentCore Gateway. Wired in during Unit 3."""
    # No default on purpose: a missing URL should fail, not fall back
    # to an endpoint nobody chose.
    url = os.environ["GATEWAY_MCP_URL"]
    return MCPClient(lambda: streamablehttp_client(url))
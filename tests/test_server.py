import pytest
from mcp import Client

from infrastructure_insight.server import mcp


@pytest.mark.anyio
async def test_mcp_exposes_only_bounded_validation_tools() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    schemas = {tool.name: tool.input_schema for tool in result.tools}
    assert set(schemas) == {
        "insight_list_targets",
        "insight_list_actions",
        "insight_preflight",
        "insight_run",
    }
    assert set(schemas["insight_run"]["properties"]) == {"target_ids", "action_ids"}
    assert all("command" not in str(schema).lower() for schema in schemas.values())

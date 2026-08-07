"""Optional local stdio MCP adapter for the bounded insight service."""

try:
    from mcp.server import MCPServer
except ImportError as exc:
    raise RuntimeError(
        'the MCP adapter requires the optional dependency: pip install "infrastructure-insight-harness[mcp]"'
    ) from exc

from .models import RunRequest
from .service import RuntimePaths, InsightService


mcp = MCPServer(
    "Infrastructure Insight Harness",
    instructions=(
        "Read-only infrastructure insight. Select contributed target and action IDs only; "
        "raw commands and credentials are not accepted."
    ),
)


def _service() -> InsightService:
    return InsightService(RuntimePaths.from_environment())


@mcp.tool()
def insight_list_targets() -> list[dict[str, object]]:
    """List contributed infrastructure targets without credentials."""
    return _service().list_targets()


@mcp.tool()
def insight_list_actions() -> list[dict[str, object]]:
    """List contributed read-only actions without exposing command text."""
    return _service().list_actions()


@mcp.tool()
def insight_preflight(target_ids: list[str] | None = None) -> list[dict[str, object]]:
    """Check local credentials and pinned SSH host keys without connecting."""
    checks = _service().preflight(tuple(target_ids) if target_ids else None)
    return [check.model_dump(mode="json") for check in checks]


@mcp.tool()
def insight_run(target_ids: list[str], action_ids: list[str]) -> dict[str, object]:
    """Run contributed actions sequentially against contributed targets."""
    result = _service().run(
        RunRequest(target_ids=tuple(target_ids), action_ids=tuple(action_ids))
    )
    return result.model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

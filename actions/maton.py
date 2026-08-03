"""
Placeholder Maton integration – now delegated to MCPController.
The previous hard‑coded GATEWAY_ROUTING_MAP and URL construction have
been removed. This module now only provides a thin wrapper that forwards
calls to an MCPController instance.
"""

from services.mcp_controller import MCPController

# Singleton controller – lazy‑initialised on first use
_controller: MCPController | None = None


def _get_controller() -> MCPController:
    """Return the shared MCPController, creating it if necessary."""
    global _controller
    if _controller is None:
        _controller = MCPController(
            transport="http",
            app_id="google-mail",
        )
    return _controller


def execute_maton_action(app_id: str, action_name: str, params: dict | None = None) -> dict:
    """Forward the old Maton‑style call to the MCPController.

    The *app_id* argument is retained for backward compatibility but is
    currently ignored – the controller can be extended later to select a
    specific MCP endpoint based on it.
    """
    controller = _get_controller()
    import asyncio

    async def _call():
        return await controller.execute_tool(action_name, params or {})

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())
    else:
        return loop.create_task(_call()).result()

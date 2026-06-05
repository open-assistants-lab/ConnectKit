"""ConnectorRuntime — load specs, check connections, discover tools."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from connectkit.backends.cli import CLIAdapter
from connectkit.backends.mcp import MCPAdapter
from connectkit.spec import ConnectorSpec, ToolSourceType
from connectkit.vault import CredentialVault

logger = logging.getLogger("connectkit")


class ConnectorRuntime:
    """Orchestrates: YAML specs → auth check → backend → tool dicts.

    Usage:
        runtime = ConnectorRuntime(
            spec_dir="./connectors",
            vault=CredentialVault("./data/users/alice"),
            user_id="alice",
        )
        tools = await runtime.get_tools()  # async for MCP discovery
        available = runtime.list_available()
        health = runtime.health()
    """

    def __init__(
        self,
        spec_dir: str | Path,
        vault: CredentialVault,
        user_id: str,
    ):
        self.spec_dir = Path(spec_dir)
        self.vault = vault
        self.user_id = user_id
        self._specs: list[ConnectorSpec] = []
        self._load_specs()

    def _load_specs(self) -> None:
        if self.spec_dir.exists():
            self._specs = ConnectorSpec.from_yaml_dir(self.spec_dir)

    def get_specs(self) -> list[ConnectorSpec]:
        return list(self._specs)

    def reload(self) -> None:
        self._load_specs()

    def list_available(self) -> list[dict[str, Any]]:
        connected = set(self.vault.list_connected())
        return [
            {
                "name": s.name,
                "display": s.display,
                "icon": s.icon,
                "category": s.category,
                "description": s.description,
                "setup_guide_url": s.setup_guide_url,
                "connected": s.name in connected,
                "auth_type": s.auth.type.value,
                "required_fields": [
                    f.model_dump() for f in s.auth.required_fields
                ],
            }
            for s in self._specs
        ]

    async def get_tools(self) -> list[dict[str, Any]]:
        """Discover tools for all connected connectors. Async — MCP servers are spawned per-spec."""
        tools: list[dict[str, Any]] = []

        for spec in self._specs:
            if not self.vault.is_connected(spec.name):
                continue

            mcp_sources = spec.get_mcp_sources()
            if mcp_sources:
                try:
                    adapter_tools = await _discover_mcp_tools(spec, self.vault, self.user_id)
                    tools.extend(adapter_tools)
                except Exception:
                    logger.warning(f"Failed to load MCP connector '{spec.name}'", exc_info=True)
                continue

            try:
                adapter_tools = self._load_cli_connector(spec)
                tools.extend(adapter_tools)
            except Exception:
                logger.warning(f"Failed to load connector '{spec.name}'", exc_info=True)
                continue

        return tools

    def get_tools_sync(self) -> list[dict[str, Any]]:
        """Sync fallback — only discovers CLI tools. MCP sources are skipped."""
        tools: list[dict[str, Any]] = []
        for spec in self._specs:
            if not self.vault.is_connected(spec.name):
                continue
            if spec.get_mcp_sources():
                continue
            try:
                adapter_tools = self._load_cli_connector(spec)
                tools.extend(adapter_tools)
            except Exception:
                continue
        return tools

    def _load_cli_connector(self, spec: ConnectorSpec) -> list[dict[str, Any]]:
        namespace = spec.name.replace("-", "_")
        all_tools: list[dict[str, Any]] = []

        for source in spec.get_tool_sources():
            try:
                if source.type == ToolSourceType.CLI:
                    adapter = CLIAdapter(spec, self.vault, self.user_id)
                    if not adapter.is_available():
                        logger.warning(
                            f"CLI not available for {spec.name}. "
                            f"Install: {source.install}"
                        )
                        continue
                    all_tools.extend(adapter.discover_tools(namespace))
            except Exception:
                logger.warning(
                    f"Failed to load tool source '{source.type}' for '{spec.name}'",
                    exc_info=True,
                )
                continue

        return all_tools

    async def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "ok", "connectors": {}}
        connected_count = 0
        error_count = 0

        for spec in self._specs:
            if not self.vault.is_connected(spec.name):
                result["connectors"][spec.name] = {"status": "not_connected"}
                continue

            connected_count += 1
            try:
                if spec.get_mcp_sources():
                    mcp_tools = await _discover_mcp_tools(spec, self.vault, self.user_id)
                    tools = mcp_tools
                else:
                    tools = self._load_cli_connector(spec)
                result["connectors"][spec.name] = {
                    "status": "ok",
                    "tools": len(tools),
                }
            except Exception as e:
                error_count += 1
                result["connectors"][spec.name] = {
                    "status": "error",
                    "error": str(e),
                }

        if error_count > 0:
            result["status"] = "broken" if error_count == connected_count else "partial"

        return result


def _make_mcp_invoker(command: str, env: dict[str, str], tool_name: str):
    """Factory: returns async function that spawns MCP server, calls tool, returns result."""
    async def ainvoke(**kwargs: Any) -> str:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        parts = command.split()
        sp = StdioServerParameters(command=parts[0], args=parts[1:], env=env)
        async with stdio_client(sp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=kwargs)
                return json.dumps(
                    {c.type: c.text for c in result.content}
                )
    return ainvoke


async def _discover_mcp_tools(
    spec: ConnectorSpec, vault: CredentialVault, user_id: str
) -> list[dict[str, Any]]:
    """Spawn MCP server, list_tools(), convert to ConnectKit tool dicts."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    adapter = MCPAdapter(spec, vault, user_id)
    env = adapter.build_server_env()
    namespace = spec.name.replace("-", "_")
    parts = adapter.command.split()
    server_params = StdioServerParameters(
        command=parts[0], args=parts[1:], env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

            tools: list[dict[str, Any]] = []
            for mcp_tool in result.tools:
                input_schema = mcp_tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                }
                tool_name = f"{namespace}__{mcp_tool.name}"
                tools.append(
                    {
                        "name": tool_name,
                        "description": mcp_tool.description or "",
                        "parameters": input_schema,
                        "function": None,
                        "ainvoke": _make_mcp_invoker(
                            adapter.command, env, mcp_tool.name
                        ),
                        "annotations": {
                            "read_only": False,
                            "destructive": False,
                            "idempotent": False,
                            "title": tool_name,
                            "mcp_server": adapter.server_name,
                            "_mcp_connector": spec.name,
                        },
                    }
                )
            return tools


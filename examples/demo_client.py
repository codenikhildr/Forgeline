"""Standalone MCP client demo for Forgeline.

Connects to the running Forgeline MCP server over streamable-HTTP using the
official MCP Python SDK, lists the tools, and calls all four against the bundled
simulator. Useful for verifying functionality and capturing demo output without
needing an MCP client UI.

Usage (with the server running, e.g. via `docker compose up`):

    python examples/demo_client.py
    python examples/demo_client.py http://localhost:8000/mcp   # custom URL
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_URL = "http://localhost:8000/mcp"

CALLS = [
    ("get_device_info", {}),
    ("read_holding_registers", {"address": 0, "count": 5}),
    ("read_input_registers", {"address": 0, "count": 5}),
    ("read_coils", {"address": 0, "count": 6}),
]


async def main(url: str) -> None:
    print(f"Connecting to Forgeline MCP server at {url}\n")
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected. Server: {init.serverInfo.name} "
                  f"(protocol {init.protocolVersion})\n")

            tools = (await session.list_tools()).tools
            print(f"Tools exposed ({len(tools)}):")
            for tool in tools:
                print(f"  - {tool.name}")
            print()

            for name, args in CALLS:
                result = await session.call_tool(name, args)
                text = result.content[0].text if result.content else "(no content)"
                print(f"=== {name}({args}) ===")
                print(text)
                print()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    asyncio.run(main(target))

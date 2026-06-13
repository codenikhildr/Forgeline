"""Quick MCP client to exercise Forgeline over streamable-HTTP.

Run with the server up (e.g. docker compose up):
    python examples/demo_client.py [http://localhost:8000/mcp]
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


async def main(url):
    print(f"Connecting to {url}\n")
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected to {init.serverInfo.name} (protocol {init.protocolVersion})\n")

            tools = (await session.list_tools()).tools
            print(f"Tools ({len(tools)}):")
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
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    asyncio.run(main(url))

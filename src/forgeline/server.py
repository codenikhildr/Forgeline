"""Forgeline MCP server.

Exposes read-only Modbus TCP operations as MCP tools using the official MCP
Python SDK (FastMCP). The MVP registers a single tool, ``get_device_info``;
the read_* register/coil tools are added on top of the same pattern.

Transport is selected via ``FORGELINE_TRANSPORT`` (``stdio`` by default, which
is how MCP clients normally launch a server). For the bundled docker-compose
stack the server runs ``streamable-http`` so it stays up as a long-lived
service alongside the simulator.
"""

from __future__ import annotations

import os
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from forgeline.tools import (
    MAX_ADDRESS,
    MAX_COIL_COUNT,
    MAX_REGISTER_COUNT,
    ModbusSettings,
)
from forgeline.tools import get_device_info as _get_device_info
from forgeline.tools import read_coils as _read_coils
from forgeline.tools import read_holding_registers as _read_holding_registers
from forgeline.tools import read_input_registers as _read_input_registers

# Reusable annotated parameter types so JSON-schema validation rejects bad input
# before it ever reaches the device (the tools layer also validates at runtime).
_Address = Annotated[
    int,
    Field(ge=0, le=MAX_ADDRESS, description="Zero-based start address (0..65535)."),
]
_RegisterCount = Annotated[
    int,
    Field(
        ge=1,
        le=MAX_REGISTER_COUNT,
        description=f"Number of registers to read (1..{MAX_REGISTER_COUNT}).",
    ),
]
_CoilCount = Annotated[
    int,
    Field(
        ge=1,
        le=MAX_COIL_COUNT,
        description=f"Number of coils to read (1..{MAX_COIL_COUNT}).",
    ),
]

_settings = ModbusSettings.from_env()

mcp = FastMCP(
    "forgeline",
    host=os.getenv("FORGELINE_HOST", "127.0.0.1"),
    port=int(os.getenv("FORGELINE_PORT", "8000")),
)


@mcp.tool()
async def get_device_info() -> dict:
    """Get identity and connection details for the monitored Modbus device.

    Returns the device's vendor, product code, revision and related fields
    (when the device supports Modbus device identification), plus the host,
    port and unit id Forgeline is connected to. Read-only.
    """
    return await _get_device_info(_settings)


@mcp.tool()
async def read_holding_registers(address: _Address, count: _RegisterCount = 1) -> dict:
    """Read holding registers (FC 0x03) from the monitored Modbus device.

    Holding registers are 16-bit read/write values (Forgeline reads them only).
    Returns the start address, count, unit id, and a list of address -> value
    pairs. Read-only.
    """
    return await _read_holding_registers(_settings, address, count)


@mcp.tool()
async def read_input_registers(address: _Address, count: _RegisterCount = 1) -> dict:
    """Read input registers (FC 0x04) from the monitored Modbus device.

    Input registers are 16-bit read-only measurements. Returns the start
    address, count, unit id, and a list of address -> value pairs.
    """
    return await _read_input_registers(_settings, address, count)


@mcp.tool()
async def read_coils(address: _Address, count: _CoilCount = 1) -> dict:
    """Read coils (FC 0x01) from the monitored Modbus device.

    Coils are single-bit on/off values. Returns the start address, count, unit
    id, and a list of address -> boolean value pairs. Read-only.
    """
    return await _read_coils(_settings, address, count)


def main() -> None:
    """Console-script entry point. Runs the MCP server on the chosen transport."""
    transport = os.getenv("FORGELINE_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

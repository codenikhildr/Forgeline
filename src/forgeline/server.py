"""Forgeline MCP server — exposes the read-only Modbus tools over MCP (FastMCP).

Transport comes from FORGELINE_TRANSPORT (default stdio). docker-compose runs it
as streamable-http so it stays up alongside the simulator.
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

# Bounds enforced at the schema level too, so bad input is rejected up front.
_Address = Annotated[int, Field(ge=0, le=MAX_ADDRESS, description="Start address (0..65535).")]
_RegisterCount = Annotated[int, Field(ge=1, le=MAX_REGISTER_COUNT, description=f"Registers to read (1..{MAX_REGISTER_COUNT}).")]
_CoilCount = Annotated[int, Field(ge=1, le=MAX_COIL_COUNT, description=f"Coils to read (1..{MAX_COIL_COUNT}).")]

_settings = ModbusSettings.from_env()

mcp = FastMCP(
    "forgeline",
    host=os.getenv("FORGELINE_HOST", "127.0.0.1"),
    port=int(os.getenv("FORGELINE_PORT", "8000")),
)


@mcp.tool()
async def get_device_info() -> dict:
    """Vendor, product code, revision and connection details for the device."""
    return await _get_device_info(_settings)


@mcp.tool()
async def read_holding_registers(address: _Address, count: _RegisterCount = 1) -> dict:
    """Read holding registers (FC 0x03). Returns address -> value pairs."""
    return await _read_holding_registers(_settings, address, count)


@mcp.tool()
async def read_input_registers(address: _Address, count: _RegisterCount = 1) -> dict:
    """Read input registers (FC 0x04). Returns address -> value pairs."""
    return await _read_input_registers(_settings, address, count)


@mcp.tool()
async def read_coils(address: _Address, count: _CoilCount = 1) -> dict:
    """Read coils (FC 0x01). Returns address -> bool pairs."""
    return await _read_coils(_settings, address, count)


def main() -> None:
    mcp.run(transport=os.getenv("FORGELINE_TRANSPORT", "stdio"))


if __name__ == "__main__":
    main()

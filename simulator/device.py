"""A self-contained Modbus TCP simulator built on pymodbus.

Starts an async TCP server pre-populated with sample values in every data table
and a device-identification block, so an AI agent can exercise Forgeline's
read-only tools against a realistic-looking "industrial device" without any
physical hardware.

Data map (addresses are zero-based; ``zero_mode=True`` so address N maps to
index N in each block):

    Holding registers (FC 03)  addr 0..99  -> 100 + addr   (e.g. setpoints)
    Input registers   (FC 04)  addr 0..99  -> 200 + addr   (e.g. live readings)
    Coils             (FC 01)  addr 0..99  -> addr % 2      (alternating on/off)
    Discrete inputs   (FC 02)  addr 0..99  -> (addr + 1) % 2

Configure the bind address with ``SIMULATOR_HOST`` / ``SIMULATOR_PORT``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartAsyncTcpServer

_LOG = logging.getLogger("forgeline.simulator")

_BLOCK_SIZE = 100


def build_context() -> ModbusServerContext:
    """Build a single-slave datastore pre-populated with sample values."""
    holding = ModbusSequentialDataBlock(0, [100 + i for i in range(_BLOCK_SIZE)])
    inputs = ModbusSequentialDataBlock(0, [200 + i for i in range(_BLOCK_SIZE)])
    coils = ModbusSequentialDataBlock(0, [i % 2 for i in range(_BLOCK_SIZE)])
    discrete = ModbusSequentialDataBlock(0, [(i + 1) % 2 for i in range(_BLOCK_SIZE)])

    slave = ModbusSlaveContext(
        di=discrete, co=coils, hr=holding, ir=inputs, zero_mode=True
    )
    # single=True: respond to any unit/slave id with this one device.
    return ModbusServerContext(slaves=slave, single=True)


def build_identity() -> ModbusDeviceIdentification:
    """Build the device-identification block returned by FC 0x2B / MEI 0x0E."""
    identity = ModbusDeviceIdentification()
    identity.VendorName = "Forgeline"
    identity.ProductCode = "FL-SIM-1"
    identity.MajorMinorRevision = "1.0.0"
    identity.VendorUrl = "https://github.com/codenikhildr/Forgeline"
    identity.ProductName = "Forgeline Modbus Simulator"
    identity.ModelName = "Virtual PLC"
    identity.UserApplicationName = "Forgeline MVP Simulator"
    return identity


async def serve() -> None:
    """Start the simulator and block forever serving requests."""
    host = os.getenv("SIMULATOR_HOST", "0.0.0.0")
    port = int(os.getenv("SIMULATOR_PORT", "5020"))

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    _LOG.info("Forgeline Modbus simulator listening on %s:%s", host, port)

    await StartAsyncTcpServer(
        context=build_context(),
        identity=build_identity(),
        address=(host, port),
    )


def run() -> None:
    """Console-script entry point (``forgeline-simulator``)."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        _LOG.info("Forgeline Modbus simulator stopped")


if __name__ == "__main__":
    run()

"""Bundled Modbus TCP simulator so Forgeline runs without any hardware.

Sample data (zero_mode, so address N maps to index N):
    holding regs (FC03)  0..99 -> 100 + addr
    input regs   (FC04)  0..99 -> 200 + addr
    coils        (FC01)  0..99 -> addr % 2
    discrete in  (FC02)  0..99 -> (addr + 1) % 2

Bind address via SIMULATOR_HOST / SIMULATOR_PORT.
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

log = logging.getLogger("forgeline.simulator")

_BLOCK_SIZE = 100


def build_context() -> ModbusServerContext:
    holding = ModbusSequentialDataBlock(0, [100 + i for i in range(_BLOCK_SIZE)])
    inputs = ModbusSequentialDataBlock(0, [200 + i for i in range(_BLOCK_SIZE)])
    coils = ModbusSequentialDataBlock(0, [i % 2 for i in range(_BLOCK_SIZE)])
    discrete = ModbusSequentialDataBlock(0, [(i + 1) % 2 for i in range(_BLOCK_SIZE)])
    slave = ModbusSlaveContext(di=discrete, co=coils, hr=holding, ir=inputs, zero_mode=True)
    return ModbusServerContext(slaves=slave, single=True)


def build_identity() -> ModbusDeviceIdentification:
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
    host = os.getenv("SIMULATOR_HOST", "0.0.0.0")
    port = int(os.getenv("SIMULATOR_PORT", "5020"))
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    log.info("Modbus simulator listening on %s:%s", host, port)
    await StartAsyncTcpServer(
        context=build_context(),
        identity=build_identity(),
        address=(host, port),
    )


def run() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log.info("simulator stopped")


if __name__ == "__main__":
    run()

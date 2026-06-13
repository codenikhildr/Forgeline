"""Read-only Modbus operations.

Each function opens a short-lived connection, does one read, and returns a plain
dict. server.py wraps these as MCP tools. There are deliberately no write helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import DeviceInformation

# Device-identification objects (MEI 0x0E) -> JSON keys.
_DEVICE_ID_OBJECTS = {
    0x00: "vendor_name",
    0x01: "product_code",
    0x02: "revision",
    0x03: "vendor_url",
    0x04: "product_name",
    0x05: "model_name",
    0x06: "user_application_name",
}

# Per-request Modbus limits.
MAX_ADDRESS = 0xFFFF
MAX_REGISTER_COUNT = 125   # FC 0x03 / 0x04
MAX_COIL_COUNT = 2000      # FC 0x01 / 0x02


class ModbusError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModbusSettings:
    host: str = "127.0.0.1"
    port: int = 5020
    unit_id: int = 1
    timeout: float = 3.0

    @classmethod
    def from_env(cls) -> "ModbusSettings":
        return cls(
            host=os.getenv("MODBUS_HOST", cls.host),
            port=int(os.getenv("MODBUS_PORT", str(cls.port))),
            unit_id=int(os.getenv("MODBUS_UNIT_ID", str(cls.unit_id))),
            timeout=float(os.getenv("MODBUS_TIMEOUT", str(cls.timeout))),
        )


async def _connect(settings: ModbusSettings) -> AsyncModbusTcpClient:
    client = AsyncModbusTcpClient(settings.host, port=settings.port, timeout=settings.timeout)
    await client.connect()
    if not client.connected:
        raise ModbusError(f"Could not connect to {settings.host}:{settings.port}")
    return client


async def get_device_info(settings: ModbusSettings) -> dict:
    """Device identity (FC 0x2B / MEI 0x0E) plus connection details."""
    client = await _connect(settings)
    try:
        info: dict = {
            "host": settings.host,
            "port": settings.port,
            "unit_id": settings.unit_id,
            "connected": True,
        }
        identity: dict = {}

        try:
            response = await client.read_device_information(
                read_code=DeviceInformation.REGULAR, slave=settings.unit_id
            )
        except Exception as exc:  # noqa: BLE001
            info["device_identification_supported"] = False
            info["device_identification_error"] = str(exc)
            info["identity"] = identity
            return info

        if response.isError():
            info["device_identification_supported"] = False
            info["device_identification_error"] = str(response)
        else:
            for object_id, raw in response.information.items():
                key = _DEVICE_ID_OBJECTS.get(object_id, f"object_0x{object_id:02x}")
                if isinstance(raw, (bytes, bytearray)):
                    identity[key] = raw.decode("ascii", errors="replace")
                else:
                    identity[key] = str(raw)
            info["device_identification_supported"] = bool(identity)

        info["identity"] = identity
        return info
    finally:
        client.close()


def _validate_range(address: int, count: int, max_count: int, kind: str) -> None:
    if isinstance(address, bool) or isinstance(count, bool):
        raise ValueError("address and count must be integers, not booleans")
    if not isinstance(address, int) or not isinstance(count, int):
        raise ValueError("address and count must be integers")
    if not 0 <= address <= MAX_ADDRESS:
        raise ValueError(f"address {address} out of range (0..{MAX_ADDRESS})")
    if not 1 <= count <= max_count:
        raise ValueError(f"count {count} out of range (1..{max_count}) for {kind}")
    if address + count - 1 > MAX_ADDRESS:
        raise ValueError(f"range {address}..{address + count - 1} exceeds {MAX_ADDRESS}")


def _format(settings: ModbusSettings, address: int, values: list) -> dict:
    return {
        "start_address": address,
        "count": len(values),
        "unit_id": settings.unit_id,
        "values": [{"address": address + i, "value": v} for i, v in enumerate(values)],
    }


async def _read(settings: ModbusSettings, method_name: str, address: int, count: int):
    client = await _connect(settings)
    try:
        response = await getattr(client, method_name)(
            address, count=count, slave=settings.unit_id
        )
        if response.isError():
            raise ModbusError(f"{method_name}({address}, count={count}) failed: {response}")
        return response
    finally:
        client.close()


async def read_holding_registers(settings: ModbusSettings, address: int, count: int = 1) -> dict:
    _validate_range(address, count, MAX_REGISTER_COUNT, "holding registers")
    response = await _read(settings, "read_holding_registers", address, count)
    return _format(settings, address, list(response.registers))


async def read_input_registers(settings: ModbusSettings, address: int, count: int = 1) -> dict:
    _validate_range(address, count, MAX_REGISTER_COUNT, "input registers")
    response = await _read(settings, "read_input_registers", address, count)
    return _format(settings, address, list(response.registers))


async def read_coils(settings: ModbusSettings, address: int, count: int = 1) -> dict:
    _validate_range(address, count, MAX_COIL_COUNT, "coils")
    response = await _read(settings, "read_coils", address, count)
    # pymodbus pads bits out to a byte boundary, so trim back to count.
    return _format(settings, address, [bool(b) for b in response.bits[:count]])

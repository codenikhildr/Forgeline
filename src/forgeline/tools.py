"""Read-only Modbus tool implementations for Forgeline.

This module is intentionally transport-agnostic: each function opens a short-lived
connection to a Modbus TCP device, performs a single read, and returns plain
JSON-serializable data. The MCP layer in :mod:`forgeline.server` is a thin wrapper
that registers these as tools.

Design note (safety): only *read* function codes are implemented here. There is no
helper to write coils or registers, by design — Forgeline's MVP cannot mutate a
device even if asked to.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import DeviceInformation

# Standard Modbus device-identification objects (MEI type 0x0E). Maps the numeric
# object id returned by the device to a friendly key for the JSON response.
_DEVICE_ID_OBJECTS: dict[int, str] = {
    0x00: "vendor_name",
    0x01: "product_code",
    0x02: "revision",
    0x03: "vendor_url",
    0x04: "product_name",
    0x05: "model_name",
    0x06: "user_application_name",
}


# Modbus protocol limits. These cap what a caller (e.g. an AI agent) can request
# so a single tool call can't ask for a huge or invalid range.
MAX_ADDRESS = 0xFFFF  # 16-bit addressing: valid addresses are 0..65535
MAX_REGISTER_COUNT = 125  # FC 0x03 / 0x04 max registers per request (Modbus spec)
MAX_COIL_COUNT = 2000  # FC 0x01 / 0x02 max coils/bits per request (Modbus spec)


class ModbusError(RuntimeError):
    """Raised when a Modbus device is unreachable or returns an error response."""


@dataclass(frozen=True)
class ModbusSettings:
    """Connection settings for the target Modbus TCP device.

    Defaults point at the bundled simulator on localhost so Forgeline runs with
    zero hardware and zero configuration.
    """

    host: str = "127.0.0.1"
    port: int = 5020
    unit_id: int = 1
    timeout: float = 3.0

    @classmethod
    def from_env(cls) -> "ModbusSettings":
        """Build settings from ``MODBUS_*`` environment variables."""
        return cls(
            host=os.getenv("MODBUS_HOST", cls.host),
            port=int(os.getenv("MODBUS_PORT", str(cls.port))),
            unit_id=int(os.getenv("MODBUS_UNIT_ID", str(cls.unit_id))),
            timeout=float(os.getenv("MODBUS_TIMEOUT", str(cls.timeout))),
        )


async def _connect(settings: ModbusSettings) -> AsyncModbusTcpClient:
    """Open a verified TCP connection, raising :class:`ModbusError` on failure."""
    client = AsyncModbusTcpClient(
        settings.host, port=settings.port, timeout=settings.timeout
    )
    await client.connect()
    if not client.connected:
        raise ModbusError(
            f"Could not connect to Modbus device at {settings.host}:{settings.port}"
        )
    return client


async def get_device_info(settings: ModbusSettings) -> dict:
    """Return identity and connection details for the target Modbus device.

    Issues a Read Device Identification request (function code 0x2B / MEI 0x0E)
    and decodes the standard objects (vendor, product, revision, ...). Devices
    that do not implement MEI 0x0E still return connection details, with
    ``device_identification_supported`` set to ``False``.
    """
    client = await _connect(settings)
    try:
        info: dict[str, object] = {
            "host": settings.host,
            "port": settings.port,
            "unit_id": settings.unit_id,
            "connected": True,
        }
        identity: dict[str, str] = {}
        try:
            response = await client.read_device_information(
                read_code=DeviceInformation.REGULAR, slave=settings.unit_id
            )
        except Exception as exc:  # noqa: BLE001 - report, don't crash the tool
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
                identity[key] = (
                    raw.decode("ascii", errors="replace")
                    if isinstance(raw, (bytes, bytearray))
                    else str(raw)
                )
            info["device_identification_supported"] = bool(identity)

        info["identity"] = identity
        return info
    finally:
        client.close()


def _validate_range(address: int, count: int, max_count: int, kind: str) -> None:
    """Reject invalid or oversized read ranges before touching the device."""
    if isinstance(address, bool) or isinstance(count, bool):
        raise ValueError("address and count must be integers, not booleans")
    if not isinstance(address, int) or not isinstance(count, int):
        raise ValueError("address and count must be integers")
    if address < 0 or address > MAX_ADDRESS:
        raise ValueError(f"address {address} out of range (0..{MAX_ADDRESS})")
    if count < 1 or count > max_count:
        raise ValueError(
            f"count {count} out of range (1..{max_count}) for {kind}"
        )
    last = address + count - 1
    if last > MAX_ADDRESS:
        raise ValueError(
            f"range {address}..{last} exceeds max address {MAX_ADDRESS}"
        )


def _format(settings: ModbusSettings, address: int, values: list) -> dict:
    """Shape a read result as clean, ordered address -> value pairs."""
    return {
        "start_address": address,
        "count": len(values),
        "unit_id": settings.unit_id,
        "values": [
            {"address": address + offset, "value": value}
            for offset, value in enumerate(values)
        ],
    }


async def _read(settings: ModbusSettings, method_name: str, address: int, count: int):
    """Run a single read function code against the device, checking for errors."""
    client = await _connect(settings)
    try:
        method = getattr(client, method_name)
        response = await method(address, count=count, slave=settings.unit_id)
        if response.isError():
            raise ModbusError(
                f"{method_name}(address={address}, count={count}) failed: {response}"
            )
        return response
    finally:
        client.close()


async def read_holding_registers(
    settings: ModbusSettings, address: int, count: int = 1
) -> dict:
    """Read ``count`` 16-bit holding registers starting at ``address`` (FC 0x03)."""
    _validate_range(address, count, MAX_REGISTER_COUNT, "holding registers")
    response = await _read(settings, "read_holding_registers", address, count)
    return _format(settings, address, list(response.registers))


async def read_input_registers(
    settings: ModbusSettings, address: int, count: int = 1
) -> dict:
    """Read ``count`` 16-bit input registers starting at ``address`` (FC 0x04)."""
    _validate_range(address, count, MAX_REGISTER_COUNT, "input registers")
    response = await _read(settings, "read_input_registers", address, count)
    return _format(settings, address, list(response.registers))


async def read_coils(
    settings: ModbusSettings, address: int, count: int = 1
) -> dict:
    """Read ``count`` coils (on/off) starting at ``address`` (FC 0x01).

    pymodbus pads ``bits`` up to a byte boundary, so the result is trimmed to
    exactly ``count`` values.
    """
    _validate_range(address, count, MAX_COIL_COUNT, "coils")
    response = await _read(settings, "read_coils", address, count)
    return _format(settings, address, [bool(bit) for bit in response.bits[:count]])

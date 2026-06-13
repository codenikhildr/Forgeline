"""End-to-end tests for the read-only Modbus tools against the bundled simulator.

These exercise the real Modbus path (the tools connect over TCP to the simulator
started in conftest) plus the input-validation guards.
"""

import pytest

from forgeline.tools import (
    get_device_info,
    read_coils,
    read_holding_registers,
    read_input_registers,
)


async def test_get_device_info(settings):
    info = await get_device_info(settings)
    assert info["connected"] is True
    assert info["device_identification_supported"] is True
    assert info["identity"]["vendor_name"] == "Forgeline"
    assert info["identity"]["product_code"] == "FL-SIM-1"
    assert info["identity"]["revision"] == "1.0.0"


async def test_read_holding_registers(settings):
    result = await read_holding_registers(settings, 0, 5)
    assert result["start_address"] == 0
    assert result["count"] == 5
    assert result["unit_id"] == 1
    assert [v["value"] for v in result["values"]] == [100, 101, 102, 103, 104]
    assert [v["address"] for v in result["values"]] == [0, 1, 2, 3, 4]


async def test_read_input_registers(settings):
    result = await read_input_registers(settings, 10, 3)
    assert [v["value"] for v in result["values"]] == [210, 211, 212]
    assert [v["address"] for v in result["values"]] == [10, 11, 12]


async def test_read_coils(settings):
    result = await read_coils(settings, 0, 6)
    # Simulator coil value at address i is i % 2.
    assert [v["value"] for v in result["values"]] == [
        False, True, False, True, False, True
    ]
    assert all(isinstance(v["value"], bool) for v in result["values"])


@pytest.mark.parametrize(
    "address, count",
    [
        (0, 200),     # count over the 125-register limit
        (0, 0),       # count below 1
        (70000, 1),   # address beyond the 16-bit range
        (-1, 1),      # negative address
        (65535, 2),   # range overflows past the max address
    ],
)
async def test_register_validation_rejects_bad_ranges(settings, address, count):
    with pytest.raises(ValueError):
        await read_holding_registers(settings, address, count)


async def test_coil_count_limit(settings):
    with pytest.raises(ValueError):
        await read_coils(settings, 0, 5000)  # over the 2000-coil limit

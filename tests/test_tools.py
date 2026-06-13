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
    assert [v["value"] for v in result["values"]] == [100, 101, 102, 103, 104]
    assert [v["address"] for v in result["values"]] == [0, 1, 2, 3, 4]


async def test_read_input_registers(settings):
    result = await read_input_registers(settings, 10, 3)
    assert [v["value"] for v in result["values"]] == [210, 211, 212]
    assert [v["address"] for v in result["values"]] == [10, 11, 12]


async def test_read_coils(settings):
    result = await read_coils(settings, 0, 6)
    assert [v["value"] for v in result["values"]] == [False, True, False, True, False, True]
    assert all(isinstance(v["value"], bool) for v in result["values"])


@pytest.mark.parametrize(
    "address, count",
    [
        (0, 200),
        (0, 0),
        (70000, 1),
        (-1, 1),
        (65535, 2),
    ],
)
async def test_register_validation(settings, address, count):
    with pytest.raises(ValueError):
        await read_holding_registers(settings, address, count)


async def test_coil_count_limit(settings):
    with pytest.raises(ValueError):
        await read_coils(settings, 0, 5000)

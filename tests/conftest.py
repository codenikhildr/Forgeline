"""Test fixtures: run the bundled simulator on a separate port for the suite."""

import asyncio
import socket
import threading
import time

import pytest
from pymodbus.server import StartAsyncTcpServer

from forgeline.tools import ModbusSettings
from simulator.device import build_context, build_identity

TEST_HOST = "127.0.0.1"
TEST_PORT = 5021  # avoid clashing with a local/docker simulator on 5020


def _serve_forever():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            StartAsyncTcpServer(
                context=build_context(),
                identity=build_identity(),
                address=(TEST_HOST, TEST_PORT),
            )
        )
    except Exception:  # noqa: BLE001
        pass


def _wait_for_port(host, port, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"simulator did not start on {host}:{port}")


@pytest.fixture(scope="session", autouse=True)
def simulator():
    threading.Thread(target=_serve_forever, daemon=True).start()
    _wait_for_port(TEST_HOST, TEST_PORT)
    yield


@pytest.fixture
def settings():
    return ModbusSettings(host=TEST_HOST, port=TEST_PORT, unit_id=1)

"""Shared test fixtures.

Runs the bundled Modbus simulator on a dedicated test port (in a background
thread with its own event loop, so it's independent of pytest-asyncio's loop)
and tears down automatically when the test process exits.
"""

import asyncio
import socket
import threading
import time

import pytest
from pymodbus.server import StartAsyncTcpServer

from forgeline.tools import ModbusSettings
from simulator.device import build_context, build_identity

# A port distinct from the default (5020) so tests don't clash with a locally
# running simulator / docker stack.
TEST_HOST = "127.0.0.1"
TEST_PORT = 5021


def _serve_forever() -> None:
    """Run the simulator forever in this thread's own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    coro = StartAsyncTcpServer(
        context=build_context(),
        identity=build_identity(),
        address=(TEST_HOST, TEST_PORT),
    )
    try:
        loop.run_until_complete(coro)
    except Exception:  # noqa: BLE001 - thread is daemonized; swallow on shutdown
        pass


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    """Block until the simulator is accepting connections, or raise."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Simulator did not start on {host}:{port} within {timeout}s")


@pytest.fixture(scope="session", autouse=True)
def simulator():
    """Start the simulator once for the whole test session."""
    thread = threading.Thread(target=_serve_forever, daemon=True)
    thread.start()
    _wait_for_port(TEST_HOST, TEST_PORT)
    yield
    # Daemon thread is torn down with the process; no explicit shutdown needed.


@pytest.fixture
def settings() -> ModbusSettings:
    """Connection settings pointing at the test simulator."""
    return ModbusSettings(host=TEST_HOST, port=TEST_PORT, unit_id=1)

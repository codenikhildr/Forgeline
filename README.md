# Forgeline

**Read-only Modbus TCP monitoring, exposed as safe MCP tools.**

[![CI](https://github.com/codenikhildr/Forgeline/actions/workflows/ci.yml/badge.svg)](https://github.com/codenikhildr/Forgeline/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Forgeline is an [MCP](https://modelcontextprotocol.io) server that lets an AI
agent **monitor** an industrial Modbus TCP device — read holding/input
registers, coils, and device identity — without any ability to change it.

> **Safety by design.** This MVP exposes **read-only** tools only. There are no
> write/command tools, and no helper code exists to write coils or registers.
> An agent connected to Forgeline cannot alter device state.

A simulated Modbus device is bundled, so you can run the whole thing with **zero
hardware**.

## Status

MVP complete. All four read-only tools — `get_device_info`,
`read_holding_registers`, `read_input_registers`, and `read_coils` — are
implemented and verified end-to-end against the bundled simulator.

## Project layout

```
forgeline/
├── src/forgeline/
│   ├── server.py        # FastMCP server: registers MCP tools
│   └── tools.py         # Read-only Modbus implementations (transport-agnostic)
├── simulator/
│   └── device.py        # Bundled pymodbus TCP simulator (zero hardware)
├── docker-compose.yml   # Starts simulator + server together
├── Dockerfile
├── pyproject.toml
├── README.md
└── LICENSE              # Apache 2.0
```

## Quick start

### Option A — Docker (simulator + server, one command)

```bash
docker compose up --build
```

This starts:

- **simulator** — a virtual Modbus device on `localhost:5020`.
- **forgeline** — the MCP server over `streamable-http` at
  `http://localhost:8000/mcp`, already pointed at the simulator.

### Option B — Local Python

Requires Python 3.10+.

```bash
pip install -e .

# Terminal 1: start the bundled simulator
forgeline-simulator

# Terminal 2: run the MCP server (stdio transport, for an MCP client)
forgeline
```

By default the server talks to the simulator on `127.0.0.1:5020`.

## Configuration

All configuration is via environment variables.

| Variable              | Default       | Description                                            |
| --------------------- | ------------- | ------------------------------------------------------ |
| `MODBUS_HOST`         | `127.0.0.1`   | Host of the Modbus TCP device to monitor.              |
| `MODBUS_PORT`         | `5020`        | Port of the Modbus TCP device.                         |
| `MODBUS_UNIT_ID`      | `1`           | Modbus unit / slave id.                                |
| `MODBUS_TIMEOUT`      | `3.0`         | Per-request timeout in seconds.                        |
| `FORGELINE_TRANSPORT` | `stdio`       | MCP transport: `stdio`, `sse`, or `streamable-http`.   |
| `FORGELINE_HOST`      | `127.0.0.1`   | Bind host for HTTP transports.                         |
| `FORGELINE_PORT`      | `8000`        | Bind port for HTTP transports.                         |
| `SIMULATOR_HOST`      | `0.0.0.0`     | Bind host for the bundled simulator.                   |
| `SIMULATOR_PORT`      | `5020`        | Bind port for the bundled simulator.                   |

## Connecting an MCP client

To launch Forgeline over stdio (e.g. from Claude Desktop or another MCP client),
register a server that runs the `forgeline` command. Example client config:

```json
{
  "mcpServers": {
    "forgeline": {
      "command": "forgeline",
      "env": { "MODBUS_HOST": "127.0.0.1", "MODBUS_PORT": "5020" }
    }
  }
}
```

(Start `forgeline-simulator` first, or point `MODBUS_HOST`/`MODBUS_PORT` at a
real device.)

## Tools

### `get_device_info`

Returns identity and connection details for the monitored device.

```jsonc
{
  "host": "127.0.0.1",
  "port": 5020,
  "unit_id": 1,
  "connected": true,
  "device_identification_supported": true,
  "identity": {
    "vendor_name": "Forgeline",
    "product_code": "FL-SIM-1",
    "revision": "1.0.0",
    "vendor_url": "https://github.com/codenikhildr/Forgeline",
    "product_name": "Forgeline Modbus Simulator",
    "model_name": "Virtual PLC",
    "user_application_name": "Forgeline MVP Simulator"
  }
}
```

Devices that do not implement Modbus device identification still return
connection details, with `device_identification_supported: false`.

### `read_holding_registers` / `read_input_registers`

Read 16-bit registers — holding (FC 0x03, read/write on the device) or input
(FC 0x04, read-only measurements). Parameters:

| Param     | Type | Default | Bounds                          |
| --------- | ---- | ------- | ------------------------------- |
| `address` | int  | —       | `0`–`65535`                     |
| `count`   | int  | `1`     | `1`–`125` (Modbus FC03/04 limit)|

```jsonc
// read_holding_registers(address=0, count=5)
{
  "start_address": 0,
  "count": 5,
  "unit_id": 1,
  "values": [
    { "address": 0, "value": 100 },
    { "address": 1, "value": 101 },
    { "address": 2, "value": 102 },
    { "address": 3, "value": 103 },
    { "address": 4, "value": 104 }
  ]
}
```

### `read_coils`

Read single-bit on/off coils (FC 0x01). Parameters:

| Param     | Type | Default | Bounds                       |
| --------- | ---- | ------- | ---------------------------- |
| `address` | int  | —       | `0`–`65535`                  |
| `count`   | int  | `1`     | `1`–`2000` (Modbus FC01 limit)|

```jsonc
// read_coils(address=0, count=4)
{
  "start_address": 0,
  "count": 4,
  "unit_id": 1,
  "values": [
    { "address": 0, "value": false },
    { "address": 1, "value": true },
    { "address": 2, "value": false },
    { "address": 3, "value": true }
  ]
}
```

Requests outside these bounds (count over the limit, or a range that exceeds
the 16-bit address space) are rejected before any request reaches the device.

## Simulator data map

The bundled simulator pre-populates each table (addresses are zero-based):

| Table                      | FC   | Addresses | Values        |
| -------------------------- | ---- | --------- | ------------- |
| Holding registers          | 0x03 | 0–99      | `100 + addr`  |
| Input registers            | 0x04 | 0–99      | `200 + addr`  |
| Coils                      | 0x01 | 0–99      | `addr % 2`    |
| Discrete inputs            | 0x02 | 0–99      | `(addr+1) % 2`|

## Development

Run the test suite — it starts the bundled simulator on a test port and
exercises all four tools plus the input-validation guards:

```bash
pip install -e ".[dev]"
pytest
```

CI runs the same suite on every push and pull request across Python 3.10–3.12.

## License

Apache License 2.0. See [LICENSE](LICENSE).

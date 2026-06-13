# Single image used by both docker-compose services (simulator + MCP server).
# The service's `command` selects which console script to run.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
COPY simulator ./simulator

RUN pip install --no-cache-dir .

# Default to the MCP server; docker-compose overrides this for the simulator.
CMD ["forgeline"]

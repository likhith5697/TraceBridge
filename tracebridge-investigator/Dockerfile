# Build context is the repo root (see docker-compose.yml) because this image
# bundles a copy of tracebridge-mcp too: the investigator launches it as a
# real stdio subprocess (exactly like the CLI does locally), so both packages
# need to live in the same container filesystem.
FROM python:3.12-slim

WORKDIR /app

COPY tracebridge-mcp /app/tracebridge-mcp
RUN pip install --no-cache-dir -e /app/tracebridge-mcp

COPY tracebridge-investigator /app/tracebridge-investigator
RUN pip install --no-cache-dir -e /app/tracebridge-investigator

WORKDIR /app/tracebridge-investigator

# No .venv exists in this image, so config.py's auto-detection correctly
# falls back to plain "python" - the same interpreter tracebridge-mcp was
# just installed into. See config.py::_default_mcp_server_command.
ENV MCP_SERVER_ARGS=-m,tracebridge_mcp.server
ENV MCP_SERVER_CWD=/app/tracebridge-mcp
ENV MCP_SERVER_PYTHONPATH=src

EXPOSE 8000
CMD ["uvicorn", "tracebridge_investigator.api:app", "--host", "0.0.0.0", "--port", "8000"]

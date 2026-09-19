"""Structural guarantee: this package has no way to reach infrastructure
except through the MCP connection and the LLM API. Evidence must only ever
arrive via mcp_client.py."""

import pathlib

import tracebridge_investigator

_PACKAGE_DIR = pathlib.Path(tracebridge_investigator.__file__).parent

_FORBIDDEN_IMPORT_LINES = (
    "import opensearchpy",
    "from opensearchpy",
    "import psycopg",
    "from psycopg",
    "import kafka",
    "from kafka",
    "import confluent_kafka",
    "import requests",
    "import httpx",
    "import urllib3",
    "import subprocess",
    "from subprocess",
    "os.system(",
    # Phase 8: runtime/dependency evidence must arrive through MCP exactly
    "import docker",
    "from docker",
    "import socket",
    "from socket",
)


def test_no_module_imports_infrastructure_clients_directly():
    for path in _PACKAGE_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_IMPORT_LINES:
            assert forbidden not in source, f"{path.name} references forbidden dependency {forbidden!r}"


def test_only_mcp_client_module_imports_the_mcp_sdk():
    for path in _PACKAGE_DIR.glob("*.py"):
        if path.stem in ("mcp_client",):
            continue
        source = path.read_text(encoding="utf-8")
        assert "import mcp" not in source and "from mcp" not in source, (
            f"{path.name} imports the mcp SDK directly - only mcp_client.py should"
        )

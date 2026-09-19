"""Environment-based configuration.

Model/provider concerns live only here and in llm.py - nothing in
investigator.py, evidence.py, or report.py knows which LLM provider is in
use, so switching providers later never touches investigation logic.

This process needs exactly two kinds of secret: an LLM API key, and
whatever tracebridge-mcp itself needs (which it reads from its own .env -
we never see PostgreSQL/OpenSearch/ServiceNow credentials here at all).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    llm_provider: str
    llm_model: str
    anthropic_api_key: str | None
    openai_api_key: str | None

    mcp_server_command: str
    mcp_server_args: list[str]
    mcp_server_cwd: Path
    mcp_server_pythonpath: str | None

    max_iterations: int


def _default_mcp_server_command(mcp_server_cwd: Path) -> str:
    """tracebridge-mcp has its own venv with the correct `mcp` SDK version - a
    bare "python" resolves through PATH ambiguously and may find an unrelated
    interpreter with an incompatible (or missing) mcp package. Point at that
    venv's interpreter explicitly whenever it exists."""
    windows_python = mcp_server_cwd / ".venv" / "Scripts" / "python.exe"
    posix_python = mcp_server_cwd / ".venv" / "bin" / "python"
    if windows_python.exists():
        return str(windows_python)
    if posix_python.exists():
        return str(posix_python)
    return "python"


def load_config() -> Config:
    args = os.environ.get("MCP_SERVER_ARGS", "-m,tracebridge_mcp.server")
    cwd = os.environ.get("MCP_SERVER_CWD", "../tracebridge-mcp")
    mcp_server_cwd = (_PROJECT_ROOT / cwd).resolve()

    return Config(
        llm_provider=os.environ.get("LLM_PROVIDER", "openai"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        mcp_server_command=os.environ.get("MCP_SERVER_COMMAND") or _default_mcp_server_command(mcp_server_cwd),
        mcp_server_args=[a for a in args.split(",") if a],
        mcp_server_cwd=mcp_server_cwd,
        mcp_server_pythonpath=os.environ.get("MCP_SERVER_PYTHONPATH", "src"),
        max_iterations=int(os.environ.get("MAX_ITERATIONS", "8")),
    )

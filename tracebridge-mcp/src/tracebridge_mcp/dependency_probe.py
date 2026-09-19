"""A bounded, read-only TCP reachability check.

This is the entire implementation behind get_dependency_health: open a bare
TCP connection to a known (host, port), see if it succeeds, close it. No
protocol handshake, no authentication, no query, no data sent or received -
which also means this never needs a credential for whatever it is checking,
so none can ever leak through it.
"""

import socket
import time
from typing import NamedTuple


class ProbeResult(NamedTuple):
    reachable: bool
    failure: str | None
    duration_ms: float


def check_tcp_reachable(host: str, port: int, timeout_seconds: float) -> ProbeResult:
    start = time.monotonic()

    def elapsed_ms() -> float:
        return (time.monotonic() - start) * 1000

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            pass
        return ProbeResult(reachable=True, failure=None, duration_ms=elapsed_ms())
    except ConnectionRefusedError:
        return ProbeResult(reachable=False, failure="CONNECTION_REFUSED", duration_ms=elapsed_ms())
    except socket.timeout:
        return ProbeResult(reachable=False, failure="TIMEOUT", duration_ms=elapsed_ms())
    except socket.gaierror:
        return ProbeResult(reachable=False, failure="DNS_RESOLUTION_FAILED", duration_ms=elapsed_ms())
    except OSError:
        return ProbeResult(reachable=False, failure="CONNECTION_ERROR", duration_ms=elapsed_ms())

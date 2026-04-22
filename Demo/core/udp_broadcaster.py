from __future__ import annotations

import socket
import json


class UDPBroadcaster:
    """Sends hybrid stabilized tracking state over UDP as JSON."""

    def __init__(self, ip: str = "127.0.0.1", port: int = 5005) -> None:
        self.ip = ip
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        self._sock.close()

    def send_hybrid_state(self, hybrid_state: dict) -> None:
        """Send hybrid stabilized state as JSON for downstream consumers."""
        payload = {
            "type": "hybrid_state_v2",
            "data": hybrid_state,
        }
        blob = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._sock.sendto(blob, (self.ip, self.port))

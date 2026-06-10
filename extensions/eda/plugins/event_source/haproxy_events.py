# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
haproxy_events.py

An event source plugin for ansible-rulebook that monitors HAProxy statistics
via the stats socket and emits events when server states change, connection
thresholds are breached, or backend topology changes.

"""

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

import asyncio
import csv
import socket
from datetime import datetime, timezone
from typing import Any

DOCUMENTATION = r"""
name: haproxy_events
short_description: Monitor HAProxy stats socket for state changes
version_added: 0.1.0
description:
  - Polls the HAProxy stats socket at regular intervals.
  - Detects server state changes (UP/DOWN).
  - Detects connection threshold breaches.
  - Detects backend topology changes (servers added/removed).
  - Emits events for consumption by ansible-rulebook rules.
author:
  - Steve Fulmer (@stevefulme1)
options:
  socket:
    description:
      - Path to the HAProxy stats socket.
      - Can be a Unix socket path (e.g., /var/run/haproxy/admin.sock).
      - Can be a TCP socket (e.g., localhost:9999).
    type: str
    default: /var/run/haproxy/admin.sock
  poll_interval:
    description:
      - How often to poll HAProxy stats, in seconds.
    type: int
    default: 10
  connection_threshold:
    description:
      - Fraction (0.0-1.0) of max connections before emitting connection_threshold event.
      - For example, 0.8 means emit when current connections >= 80% of limit.
    type: float
    default: 0.8
  event_types:
    description:
      - List of event types to emit.
      - Valid values are server_state_change, connection_threshold, server_added, server_removed.
    type: list
    elements: str
    default:
      - server_state_change
      - connection_threshold
      - server_added
      - server_removed
  timeout:
    description:
      - Socket connection timeout in seconds.
    type: int
    default: 5
examples:
  - |
    - name: Monitor HAProxy health
      hosts: all
      sources:
        - stevefulme1.haproxy.haproxy_events:
            socket: /var/run/haproxy/admin.sock
            poll_interval: 10
            connection_threshold: 0.8
      rules:
        - name: Server went DOWN
          condition: event.type == "server_state_change" and event.data.current_status == "DOWN"
          action:
            run_playbook:
              name: respond_to_server_down.yml
"""


def _connect_socket(socket_path: str, timeout: int = 5) -> socket.socket:
    """
    Create a socket connection to HAProxy stats socket.

    Args:
        socket_path: Unix socket path or host:port for TCP
        timeout: Connection timeout in seconds

    Returns:
        Connected socket object

    Raises:
        OSError: If connection fails
    """
    if ":" in socket_path:
        # TCP socket
        host, port = socket_path.rsplit(":", 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
    else:
        # Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_path)

    return sock


def _poll_stats(socket_path: str, timeout: int = 5) -> list[dict[str, Any]]:
    """
    Poll HAProxy stats socket and return parsed statistics.

    Args:
        socket_path: Unix socket path or host:port for TCP
        timeout: Connection timeout in seconds

    Returns:
        List of dictionaries, one per server/frontend/backend

    Raises:
        OSError: If connection or read fails
    """
    sock = _connect_socket(socket_path, timeout)
    try:
        sock.sendall(b"show stat\n")
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()

    # Parse CSV output
    lines = data.decode("utf-8").strip().split("\n")
    reader = csv.DictReader(lines)
    return list(reader)


def _detect_changes(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    connection_threshold: float = 0.8,
) -> list[dict[str, Any]]:
    """
    Compare two stat snapshots and return detected events.

    Args:
        previous: Previous stats snapshot
        current: Current stats snapshot
        connection_threshold: Fraction for connection threshold events

    Returns:
        List of event dictionaries
    """
    events = []

    # Build lookup maps: (pxname, svname) -> stat dict
    prev_map = {(s["pxname"], s["svname"]): s for s in previous}
    curr_map = {(s["pxname"], s["svname"]): s for s in current}

    # Detect state changes and topology changes
    for key, curr_stat in curr_map.items():
        pxname, svname = key

        if key in prev_map:
            prev_stat = prev_map[key]

            # Server state change (not for FRONTEND/BACKEND aggregate entries)
            if svname not in ("FRONTEND", "BACKEND"):
                if prev_stat.get("status") != curr_stat.get("status"):
                    events.append({
                        "type": "server_state_change",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {
                            "backend": pxname,
                            "server": svname,
                            "previous_status": prev_stat.get("status"),
                            "current_status": curr_stat.get("status"),
                        },
                    })

        else:
            # Server added (not for FRONTEND/BACKEND)
            if svname not in ("FRONTEND", "BACKEND"):
                events.append({
                    "type": "server_added",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "backend": pxname,
                        "server": svname,
                        "status": curr_stat.get("status"),
                    },
                })

    # Detect removed servers
    for key, prev_stat in prev_map.items():
        pxname, svname = key
        if key not in curr_map and svname not in ("FRONTEND", "BACKEND"):
            events.append({
                "type": "server_removed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "backend": pxname,
                    "server": svname,
                },
            })

    # Detect connection threshold breaches (for FRONTEND entries)
    for key, curr_stat in curr_map.items():
        pxname, svname = key
        if svname == "FRONTEND":
            scur = curr_stat.get("scur", "0")
            slim = curr_stat.get("slim", "0")

            try:
                scur_int = int(scur)
                slim_int = int(slim)
                if slim_int > 0:
                    utilization = scur_int / slim_int
                    if utilization >= connection_threshold:
                        events.append({
                            "type": "connection_threshold",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "data": {
                                "frontend": pxname,
                                "current_connections": scur_int,
                                "limit": slim_int,
                                "utilization_pct": round(utilization * 100, 2),
                            },
                        })
            except (ValueError, ZeroDivisionError):
                pass

    return events


async def main(queue: asyncio.Queue, args: dict[str, Any]):
    """
    Main entry point for the EDA event source plugin.

    Args:
        queue: Asyncio queue to put events into
        args: Plugin arguments from rulebook
    """
    socket_path = args.get("socket", "/var/run/haproxy/admin.sock")
    poll_interval = args.get("poll_interval", 10)
    connection_threshold = args.get("connection_threshold", 0.8)
    timeout = args.get("timeout", 5)
    event_types = args.get("event_types", [
        "server_state_change",
        "connection_threshold",
        "server_added",
        "server_removed",
    ])

    previous_stats = []

    while True:
        try:
            # Poll current stats
            current_stats = _poll_stats(socket_path, timeout)

            # Detect changes
            if previous_stats:
                events = _detect_changes(previous_stats, current_stats, connection_threshold)

                # Filter by event_types and emit
                for event in events:
                    if event["type"] in event_types:
                        await queue.put(event)

            # Update previous state
            previous_stats = current_stats

        except Exception as e:
            # Emit error event
            await queue.put({
                "type": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "message": str(e),
                    "socket": socket_path,
                },
            })

        # Wait before next poll
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    # Simple CLI test for the detection logic
    import sys

    print("Testing _detect_changes...")

    previous = [
        {"pxname": "web", "svname": "srv1", "status": "UP", "scur": "5"},
        {"pxname": "web", "svname": "FRONTEND", "status": "OPEN", "scur": "50", "slim": "200"},
    ]
    current = [
        {"pxname": "web", "svname": "srv1", "status": "DOWN", "scur": "0"},
        {"pxname": "web", "svname": "srv2", "status": "UP", "scur": "0"},
        {"pxname": "web", "svname": "FRONTEND", "status": "OPEN", "scur": "180", "slim": "200"},
    ]

    events = _detect_changes(previous, current, 0.8)
    for event in events:
        print(f"{event['type']}: {event['data']}")

#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_stats
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Query detailed HAProxy statistics
description:
  - Query detailed per-entity stats (sessions, bytes, rates, health checks) from HAProxy
  - Uses the HAProxy Runtime API stats socket to retrieve statistics
  - Supports filtering by entity type (frontend, backend, server) and name
options:
  socket:
    description:
      - Path to HAProxy stats socket or TCP endpoint
      - Unix socket path or tcp://host:port format
    type: str
    default: /var/run/haproxy/admin.sock
  timeout:
    description:
      - Socket connection timeout in seconds
    type: int
    default: 10
  filter_type:
    description:
      - Filter statistics by entity type
    type: str
    choices:
      - frontend
      - backend
      - server
      - all
    default: all
  filter_name:
    description:
      - Filter to specific frontend/backend name (pxname field)
    type: str
  filter_server:
    description:
      - Filter to specific server name within a backend
      - Only applicable when filter_type is server
    type: str
"""

EXAMPLES = """
- name: Get all HAProxy statistics
  sfulmer.haproxy.haproxy_stats:
    socket: /var/run/haproxy/admin.sock
  register: result

- name: Get only frontend statistics
  sfulmer.haproxy.haproxy_stats:
    socket: /var/run/haproxy/admin.sock
    filter_type: frontend
  register: frontends

- name: Get statistics for specific backend
  sfulmer.haproxy.haproxy_stats:
    socket: /var/run/haproxy/admin.sock
    filter_type: backend
    filter_name: web_backend
  register: backend_stats

- name: Get statistics for specific server
  sfulmer.haproxy.haproxy_stats:
    socket: /var/run/haproxy/admin.sock
    filter_type: server
    filter_server: web_server1
  register: server_stats

- name: Get all servers in a backend
  sfulmer.haproxy.haproxy_stats:
    socket: /var/run/haproxy/admin.sock
    filter_type: server
    filter_name: web_backend
  register: backend_servers
"""

RETURN = """
stats:
  description:
    - List of filtered statistics entries
    - Each entry contains all CSV fields from HAProxy show stat command
  type: list
  elements: dict
  returned: always
  sample:
    - pxname: web_frontend
      svname: FRONTEND
      status: OPEN
      scur: "10"
      smax: "50"
      stot: "1000"
      bin: "10240"
      bout: "20480"
      rate: "5"
      check_status: ""
      weight: ""
summary:
  description:
    - Summary counts of entities
  type: dict
  returned: always
  contains:
    total_frontends:
      description: Total number of frontends
      type: int
    total_backends:
      description: Total number of backends
      type: int
    total_servers:
      description: Total number of servers
      type: int
    total_sessions:
      description: Total cumulative sessions across all entities
      type: int
  sample:
    total_frontends: 2
    total_backends: 2
    total_servers: 4
    total_sessions: 3500
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


def get_stats(module):
    """Retrieve and filter HAProxy statistics.

    Args:
        module: AnsibleModule instance with params

    Returns:
        dict: Result dictionary with stats and summary
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]
    filter_type = module.params["filter_type"]
    filter_name = module.params.get("filter_name")
    filter_server = module.params.get("filter_server")

    try:
        client = HAProxySocket(socket_path, timeout)
        all_stats = client.get_stats()
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to retrieve stats: {e}")

    # Filter stats based on parameters
    filtered_stats = []
    for entry in all_stats:
        # Apply type filter
        if filter_type == "frontend" and entry["svname"] != "FRONTEND":
            continue
        if filter_type == "backend" and entry["svname"] != "BACKEND":
            continue
        if filter_type == "server" and entry["svname"] in ("FRONTEND", "BACKEND"):
            continue

        # Apply name filter
        if filter_name and entry["pxname"] != filter_name:
            continue

        # Apply server filter
        if filter_server and entry["svname"] != filter_server:
            continue

        filtered_stats.append(entry)

    # Calculate summary
    total_frontends = sum(1 for s in all_stats if s["svname"] == "FRONTEND")
    total_backends = sum(1 for s in all_stats if s["svname"] == "BACKEND")
    total_servers = sum(1 for s in all_stats if s["svname"] not in ("FRONTEND", "BACKEND"))
    total_sessions = sum(int(s.get("stot", 0) or 0) for s in all_stats)

    summary = {
        "total_frontends": total_frontends,
        "total_backends": total_backends,
        "total_servers": total_servers,
        "total_sessions": total_sessions,
    }

    return {
        "changed": False,
        "stats": filtered_stats,
        "summary": summary,
    }


def main():
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", default="/var/run/haproxy/admin.sock"),
        timeout=dict(type="int", default=10),
        filter_type=dict(
            type="str",
            choices=["frontend", "backend", "server", "all"],
            default="all",
        ),
        filter_name=dict(type="str"),
        filter_server=dict(type="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = get_stats(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

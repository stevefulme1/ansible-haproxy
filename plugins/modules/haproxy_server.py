#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_server
author: Steve Fulmer (@stevefulme1)
version_added: "1.0.0"
short_description: Manage HAProxy backend server state
description:
  - Enable, disable, or drain backend servers in HAProxy via the Runtime API.
  - Set server weight and wait for status changes.
  - Supports check mode and idempotent operations.
options:
  socket:
    description:
      - Path to the HAProxy Runtime API socket.
    type: str
    default: /var/run/haproxy/admin.sock
  timeout:
    description:
      - Timeout in seconds for socket operations.
    type: int
    default: 10
  backend:
    description:
      - Name of the backend containing the server.
    type: str
    required: true
  server:
    description:
      - Name of the server to manage.
    type: str
    required: true
  state:
    description:
      - Desired state of the server.
      - C(enabled) sets the server to UP status.
      - C(disabled) sets the server to MAINT status.
      - C(drain) sets the server to DRAIN status (accepts existing connections, refuses new ones).
    type: str
    choices: [enabled, disabled, drain]
    default: enabled
  weight:
    description:
      - Server weight (0-256).
      - If specified, the server's weight will be set to this value.
    type: int
  drain:
    description:
      - Deprecated. Use C(state=drain) instead.
    type: bool
    default: false
  wait:
    description:
      - Whether to wait for the server to reach the desired state.
    type: bool
    default: true
  wait_retries:
    description:
      - Number of retries when waiting for status change.
    type: int
    default: 25
  wait_interval:
    description:
      - Interval in seconds between retries when waiting.
    type: int
    default: 2
"""

EXAMPLES = """
- name: Enable server in backend
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    state: enabled

- name: Disable server for maintenance
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    state: disabled

- name: Drain server (no new connections)
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    state: drain

- name: Set server weight
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    weight: 50

- name: Enable server and set weight
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    state: enabled
    weight: 100

- name: Disable server without waiting
  stevefulme1.haproxy.haproxy_server:
    backend: web_backend
    server: server1
    state: disabled
    wait: false
"""

RETURN = """
changed:
  description: Whether the server state was changed.
  type: bool
  returned: always
  sample: true
server_status:
  description: Final status of the server.
  type: str
  returned: always
  sample: "UP"
"""

import time
from typing import TYPE_CHECKING

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


if TYPE_CHECKING:
    from typing import Any, Dict


# Map desired states to acceptable HAProxy status values
STATE_STATUS_MAP = {
    "enabled": ("UP", "UP 1/3", "UP 2/3", "OPEN"),
    "disabled": ("MAINT", "MAINT (via)", "DRAIN (agent)"),
    "drain": ("DRAIN", "DRAIN (agent)"),
}


def manage_server(module: AnsibleModule) -> Dict[str, Any]:
    """Manage HAProxy backend server state.

    Args:
        module: The Ansible module instance.

    Returns:
        Dictionary with 'changed' status and 'server_status'.
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]
    backend = module.params["backend"]
    server = module.params["server"]
    state = module.params["state"]
    weight = module.params["weight"]
    wait = module.params["wait"]
    wait_retries = module.params["wait_retries"]
    wait_interval = module.params["wait_interval"]

    try:
        client = HAProxySocket(socket_path=socket_path, timeout=timeout)
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to connect to HAProxy socket: {e}")

    # Get current server status
    try:
        stats = client.get_stats()
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to get HAProxy stats: {e}")

    # Find the server in stats
    server_info = None
    for stat in stats:
        if stat.get("pxname") == backend and stat.get("svname") == server:
            server_info = stat
            break

    if not server_info:
        module.fail_json(
            msg=f"Server '{server}' not found in backend '{backend}'"
        )

    current_status = server_info.get("status", "UNKNOWN")
    current_weight = server_info.get("weight")

    # Determine if changes are needed
    desired_statuses = STATE_STATUS_MAP[state]
    state_needs_change = current_status not in desired_statuses

    weight_needs_change = False
    if weight is not None and current_weight is not None:
        weight_needs_change = str(current_weight) != str(weight)

    changed = state_needs_change or weight_needs_change

    if not changed:
        return {
            "changed": False,
            "server_status": current_status,
        }

    if module.check_mode:
        return {
            "changed": True,
            "server_status": current_status,
        }

    # Apply state change
    if state_needs_change:
        try:
            if state == "enabled":
                client.execute(f"enable server {backend}/{server}")
            elif state == "disabled":
                client.execute(f"disable server {backend}/{server}")
            elif state == "drain":
                client.execute(f"set server {backend}/{server} state drain")
        except HAProxySocketError as e:
            module.fail_json(msg=f"Failed to change server state: {e}")

    # Apply weight change
    if weight_needs_change:
        try:
            client.execute(f"set server {backend}/{server} weight {weight}")
        except HAProxySocketError as e:
            module.fail_json(msg=f"Failed to set server weight: {e}")

    # Wait for status change if requested
    if wait and state_needs_change:
        for i in range(wait_retries):
            time.sleep(wait_interval)
            try:
                stats = client.get_stats()
            except HAProxySocketError as e:
                module.fail_json(msg=f"Failed to get HAProxy stats: {e}")

            for stat in stats:
                if stat.get("pxname") == backend and stat.get("svname") == server:
                    current_status = stat.get("status", "UNKNOWN")
                    if current_status in desired_statuses:
                        break
            else:
                continue
            break

    # Get final status
    try:
        stats = client.get_stats()
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to get HAProxy stats: {e}")

    for stat in stats:
        if stat.get("pxname") == backend and stat.get("svname") == server:
            final_status = stat.get("status", "UNKNOWN")
            break
    else:
        final_status = "UNKNOWN"

    return {
        "changed": True,
        "server_status": final_status,
    }


def main() -> None:
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", default="/var/run/haproxy/admin.sock"),
        timeout=dict(type="int", default=10),
        backend=dict(type="str", required=True),
        server=dict(type="str", required=True),
        state=dict(
            type="str",
            choices=["enabled", "disabled", "drain"],
            default="enabled",
        ),
        weight=dict(type="int"),
        drain=dict(type="bool", default=False),
        wait=dict(type="bool", default=True),
        wait_retries=dict(type="int", default=25),
        wait_interval=dict(type="int", default=2),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = manage_server(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

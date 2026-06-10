#!/usr/bin/python
# pylint: disable=E0401
# haproxy_stick_table.py - Query and manage HAProxy stick table entries.
# Author: Steve Fulmer (@stevefulme1)
# License: GPL-3.0-or-later
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function


DOCUMENTATION = """
module: haproxy_stick_table
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Query and manage HAProxy stick table entries
description:
  - Query, inspect, and clear stick table entries via the HAProxy Runtime API.
  - Supports filtering by data type and key lookup.
options:
  socket:
    description: Path to the HAProxy stats socket.
    type: str
    default: /var/run/haproxy/admin.sock
  timeout:
    description: Socket timeout in seconds.
    type: int
    default: 10
  table:
    description: Stick table name (typically matches a backend/frontend name).
    type: str
    required: true
  action:
    description: Action to perform on the stick table.
    type: str
    choices: [show, clear, lookup]
    default: show
  key:
    description: Key to look up (required when action=lookup).
    type: str
  data_type:
    description: Filter by data type (e.g., gpc0, conn_rate, http_req_rate).
    type: str
"""

EXAMPLES = """
- name: Show all entries in a stick table
  stevefulme1.haproxy.haproxy_stick_table:
    table: web_back
    action: show

- name: Look up a specific key
  stevefulme1.haproxy.haproxy_stick_table:
    table: web_back
    action: lookup
    key: 10.0.0.1

- name: Clear all entries in a stick table
  stevefulme1.haproxy.haproxy_stick_table:
    table: web_back
    action: clear

- name: Show stick table entries filtered by gpc0
  stevefulme1.haproxy.haproxy_stick_table:
    table: web_back
    action: show
    data_type: gpc0
"""

RETURN = """
entries:
  description: List of stick table entries.
  type: list
  elements: dict
  returned: when action is show or lookup
  sample:
    - key: 10.0.0.1
      use: "0"
      exp: "30000"
      gpc0: "5"
      conn_rate(30000): "2"
table:
  description: Name of the stick table queried.
  type: str
  returned: always
entry_count:
  description: Number of entries returned.
  type: int
  returned: always
"""


__metaclass__ = type  # pylint: disable=C0103

from typing import TYPE_CHECKING

from ansible.module_utils.basic import AnsibleModule  # type: ignore
from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


if TYPE_CHECKING:
    from typing import Any, Dict, List


def parse_stick_table_entries(output: str) -> list:
    """Parse stick table output into structured entries.

    Args:
        output: Raw output from HAProxy show table command.

    Returns:
        List of dicts containing parsed entries.
    """
    entries = []
    lines = output.strip().split("\n")

    for line in lines:
        if line.startswith("#") or not line.strip():
            continue

        # Parse entry line format: 0x1234: key=10.0.0.1 use=0 exp=30000 gpc0=5
        if ": " not in line:
            continue

        parts = line.split(": ", 1)
        if len(parts) != 2:
            continue

        entry_data = parts[1]
        entry = {}

        # Parse key=value pairs
        for pair in entry_data.split():
            if "=" in pair:
                key, value = pair.split("=", 1)
                # Remove parentheses content from keys like "conn_rate(30000)"
                entry[key] = value

        if entry:
            entries.append(entry)

    return entries


def manage_stick_table(module: AnsibleModule) -> dict:
    """Manage HAProxy stick table.

    Args:
        module: AnsibleModule instance.

    Returns:
        Dict containing result data.
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]
    table = module.params["table"]
    action = module.params["action"]
    key = module.params["key"]
    data_type = module.params["data_type"]

    result = {
        "changed": False,
        "table": table,
    }

    try:
        client = HAProxySocket(socket_path, timeout)

        if action == "clear":
            if not module.check_mode:
                client.execute(f"clear table {table}")
            result["changed"] = True
            result["entries"] = []
            result["entry_count"] = 0

        elif action == "lookup":
            if not key:
                module.fail_json(msg="key parameter is required when action=lookup")

            command = f"show table {table} key {key}"
            output = client.execute(command)
            entries = parse_stick_table_entries(output)
            result["entries"] = entries
            result["entry_count"] = len(entries)

        else:  # action == "show"
            if data_type:
                command = f"show table {table} data.{data_type}"
            else:
                command = f"show table {table}"

            output = client.execute(command)
            entries = parse_stick_table_entries(output)
            result["entries"] = entries
            result["entry_count"] = len(entries)

    except HAProxySocketError as e:
        module.fail_json(msg=f"HAProxy socket error: {e}")

    return result


def main() -> None:
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", default="/var/run/haproxy/admin.sock"),
        timeout=dict(type="int", default=10),
        table=dict(type="str", required=True),
        action=dict(type="str", choices=["show", "clear", "lookup"], default="show"),
        key=dict(type="str", no_log=False),
        data_type=dict(type="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = manage_stick_table(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

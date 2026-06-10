#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function


DOCUMENTATION = """
module: haproxy_acl
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Manage HAProxy runtime ACL entries
description:
  - Add, remove, or list entries in HAProxy runtime ACLs via the stats socket.
  - This module communicates with HAProxy using the Runtime API.
options:
  socket:
    description:
      - Path to the HAProxy stats socket.
      - Can be a Unix socket path or TCP socket in format tcp://host:port.
    type: str
    default: /var/run/haproxy/admin.sock
  timeout:
    description:
      - Socket communication timeout in seconds.
    type: int
    default: 10
  acl_name:
    description:
      - ACL identifier (name or #id from C(show acl)).
    type: str
    required: true
  state:
    description:
      - Desired state of the ACL entry.
      - C(present) adds the value if not already in the ACL.
      - C(absent) removes the value if present in the ACL.
      - C(list) returns all current ACL entries.
    type: str
    choices: [present, absent, list]
    default: present
  value:
    description:
      - ACL entry value to add or remove.
      - Required when I(state=present) or I(state=absent).
    type: str
"""

EXAMPLES = """
- name: Add IP to blocked_ips ACL
  sfulmer.haproxy.haproxy_acl:
    socket: /var/run/haproxy/admin.sock
    acl_name: blocked_ips
    state: present
    value: 10.0.0.1

- name: Remove IP from blocked_ips ACL
  sfulmer.haproxy.haproxy_acl:
    socket: /var/run/haproxy/admin.sock
    acl_name: blocked_ips
    state: absent
    value: 10.0.0.1

- name: List all entries in blocked_ips ACL
  sfulmer.haproxy.haproxy_acl:
    socket: /var/run/haproxy/admin.sock
    acl_name: blocked_ips
    state: list
  register: acl_entries

- name: Add domain to allowed_domains ACL
  sfulmer.haproxy.haproxy_acl:
    acl_name: allowed_domains
    state: present
    value: example.com
"""

RETURN = """
entries:
  description: List of current ACL entries
  returned: always
  type: list
  elements: str
  sample: ['10.0.0.1', '10.0.0.2', '192.168.1.1']
acl_name:
  description: The ACL that was managed
  returned: always
  type: str
  sample: blocked_ips
"""


__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


def parse_acl_entries(output):
    """Parse ACL entries from 'show acl' output.

    Args:
        output: Raw output from 'show acl' command.

    Returns:
        list: List of ACL entry values (without the 0xHEX prefix).
    """
    entries = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        # Format: 0x1234 value
        parts = line.split(None, 1)
        if len(parts) == 2:
            entries.append(parts[1])
    return entries


def get_acl_entries(client, acl_name):
    """Get current ACL entries.

    Args:
        client: HAProxySocket instance.
        acl_name: ACL identifier.

    Returns:
        list: List of current ACL entry values.
    """
    output = client.execute(f"show acl {acl_name}")
    return parse_acl_entries(output)


def manage_acl(module):
    """Manage HAProxy ACL entries.

    Args:
        module: AnsibleModule instance.

    Returns:
        dict: Result dictionary with changed status and entries.
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]
    acl_name = module.params["acl_name"]
    state = module.params["state"]
    value = module.params["value"]

    try:
        client = HAProxySocket(socket_path, timeout)

        # Get current entries
        current_entries = get_acl_entries(client, acl_name)

        if state == "list":
            return {
                "changed": False,
                "entries": current_entries,
                "acl_name": acl_name,
            }

        # Check if value already exists
        value_exists = value in current_entries

        if state == "present":
            if value_exists:
                # Already present, no change needed
                return {
                    "changed": False,
                    "entries": current_entries,
                    "acl_name": acl_name,
                }
            else:
                # Add the entry
                if not module.check_mode:
                    client.execute(f"add acl {acl_name} {value}")
                    # Get updated entries
                    current_entries = get_acl_entries(client, acl_name)
                return {
                    "changed": True,
                    "entries": current_entries,
                    "acl_name": acl_name,
                }

        elif state == "absent":
            if not value_exists:
                # Already absent, no change needed
                return {
                    "changed": False,
                    "entries": current_entries,
                    "acl_name": acl_name,
                }
            else:
                # Remove the entry
                if not module.check_mode:
                    client.execute(f"del acl {acl_name} {value}")
                    # Get updated entries
                    current_entries = get_acl_entries(client, acl_name)
                return {
                    "changed": True,
                    "entries": current_entries,
                    "acl_name": acl_name,
                }

    except HAProxySocketError as e:
        module.fail_json(msg=f"HAProxy socket error: {e}")


def main():
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", default="/var/run/haproxy/admin.sock"),
        timeout=dict(type="int", default=10),
        acl_name=dict(type="str", required=True),
        state=dict(type="str", default="present", choices=["present", "absent", "list"]),
        value=dict(type="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ("state", "present", ["value"]),
            ("state", "absent", ["value"]),
        ],
    )

    result = manage_acl(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

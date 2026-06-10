#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_info
author: Steve Fulmer (@stevefulme1)
version_added: "1.0.0"
short_description: Gather facts from HAProxy stats socket
description:
  - Connects to HAProxy stats socket (Unix or TCP) to gather version, uptime, frontends, backends, and server information.
  - Returns structured data suitable for monitoring and inventory purposes.
options:
  socket:
    description:
      - Path to HAProxy stats socket (Unix socket path or tcp://host:port).
    type: str
    required: true
  timeout:
    description:
      - Socket connection timeout in seconds.
    type: int
    default: 10
"""

EXAMPLES = """
- name: Gather HAProxy info from Unix socket
  sfulmer.haproxy.haproxy_info:
    socket: /var/run/haproxy/admin.sock
  register: haproxy_facts

- name: Gather HAProxy info from TCP socket
  sfulmer.haproxy.haproxy_info:
    socket: tcp://127.0.0.1:9999
    timeout: 5
  register: haproxy_facts

- name: Display version
  ansible.builtin.debug:
    msg: "HAProxy version: {{ haproxy_facts.haproxy.version }}"
"""

RETURN = """
haproxy:
  description: Dictionary containing HAProxy facts
  returned: always
  type: dict
  contains:
    version:
      description: HAProxy version string
      type: str
      sample: "2.8.3"
    uptime_seconds:
      description: HAProxy uptime in seconds
      type: int
      sample: 12345
    node:
      description: Node name (if set in HAProxy config)
      type: str
      sample: "haproxy-node-1"
    frontends:
      description: Dictionary of frontends keyed by frontend name
      type: dict
      sample:
        web_frontend:
          current_sessions: 5
          max_sessions: 100
          total_sessions: 1234
          status: OPEN
    backends:
      description: Dictionary of backends keyed by backend name
      type: dict
      sample:
        web_backend:
          current_sessions: 2
          status: UP
          servers:
            server1:
              status: UP
              current_sessions: 1
              weight: 100
              check_status: L4OK
    info:
      description: Raw info dictionary from HAProxy
      type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


def gather_info(module):
    """Gather HAProxy information via stats socket.

    Args:
        module: AnsibleModule instance with params

    Returns:
        Dictionary containing HAProxy facts

    Raises:
        Exception: On connection or parsing errors
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]

    client = HAProxySocket(socket_path, timeout)

    info = client.get_info()
    stats = client.get_stats()

    frontends = {}
    backends = {}

    for entry in stats:
        pxname = entry.get("pxname", "")
        svname = entry.get("svname", "")

        if svname == "FRONTEND":
            frontends[pxname] = {
                "current_sessions": int(entry.get("scur", 0) or 0),
                "max_sessions": int(entry.get("smax", 0) or 0),
                "total_sessions": int(entry.get("stot", 0) or 0),
                "status": entry.get("status", "UNKNOWN"),
            }
        elif svname == "BACKEND":
            if pxname not in backends:
                backends[pxname] = {"servers": {}}
            backends[pxname]["current_sessions"] = int(entry.get("scur", 0) or 0)
            backends[pxname]["status"] = entry.get("status", "UNKNOWN")
        else:
            if pxname not in backends:
                backends[pxname] = {"servers": {}}
            if "current_sessions" not in backends[pxname]:
                backends[pxname]["current_sessions"] = 0
            if "status" not in backends[pxname]:
                backends[pxname]["status"] = "UNKNOWN"

            backends[pxname]["servers"][svname] = {
                "status": entry.get("status", "UNKNOWN"),
                "current_sessions": int(entry.get("scur", 0) or 0),
                "weight": int(entry.get("weight", 0) or 0),
                "check_status": entry.get("check_status", "UNKNOWN"),
            }

    return {
        "version": info.get("Version", "unknown"),
        "uptime_seconds": int(info.get("Uptime_sec", 0)),
        "node": info.get("node", ""),
        "frontends": frontends,
        "backends": backends,
        "info": info,
    }


def main():
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", required=True),
        timeout=dict(type="int", default=10),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    try:
        result = gather_info(module)
        module.exit_json(changed=False, haproxy=result)
    except HAProxySocketError as e:
        module.fail_json(msg=f"HAProxy socket error: {str(e)}")


if __name__ == "__main__":
    main()

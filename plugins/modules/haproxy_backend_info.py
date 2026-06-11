#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_backend_info
author: Steve Fulmer (@stevefulme1)
version_added: "1.0.0"
short_description: Gather information about HAProxy backend configurations
description:
  - Retrieves backend configuration information from HAProxy configuration file.
  - Returns backend definitions including mode, balance algorithm, options, and servers.
  - Supports querying specific backends or all backends.
options:
  config_path:
    description:
      - Path to HAProxy configuration file.
    type: str
    default: /etc/haproxy/haproxy.cfg
  name:
    description:
      - Name of a specific backend to retrieve.
      - If not specified, all backends are returned.
    type: str
"""

EXAMPLES = """
- name: Get all backend configurations
  stevefulme1.haproxy.haproxy_backend_info:
    config_path: /etc/haproxy/haproxy.cfg
  register: result

- name: Get specific backend configuration
  stevefulme1.haproxy.haproxy_backend_info:
    config_path: /etc/haproxy/haproxy.cfg
    name: web_backend
  register: result

- name: Display backend information
  ansible.builtin.debug:
    msg: "Backend {{ item.name }} uses {{ item.balance }} balancing"
  loop: "{{ result.backends }}"
"""

RETURN = """
backends:
  description: List of backend configurations.
  returned: always
  type: list
  elements: dict
  contains:
    name:
      description: Backend name
      type: str
      sample: "web_backend"
    mode:
      description: Protocol mode
      type: str
      sample: "http"
    balance:
      description: Load balancing algorithm
      type: str
      sample: "roundrobin"
    options:
      description: List of backend options
      type: list
      elements: str
      sample: ["httpchk GET /health", "forwardfor"]
    servers:
      description: List of server definitions
      type: list
      elements: dict
      sample:
        - name: "web1"
          address: "10.0.1.10:8080"
          params: "check inter 3s"
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_config_parser import (
    HAProxyConfigParser,
    HAProxyConfigError,
)


def parse_backend_section(section):
    """Parse backend section into structured data.

    Args:
        section: Section dictionary with type, name, and lines

    Returns:
        Dictionary containing parsed backend configuration
    """
    backend = {
        "name": section["name"],
        "mode": None,
        "balance": None,
        "options": [],
        "servers": [],
    }

    for line in section["lines"]:
        stripped = line.strip()

        if stripped.startswith("backend "):
            continue
        elif stripped.startswith("mode "):
            backend["mode"] = stripped.split(None, 1)[1]
        elif stripped.startswith("balance "):
            backend["balance"] = stripped.split(None, 1)[1]
        elif stripped.startswith("option "):
            option = stripped.split(None, 1)[1]
            backend["options"].append(option)
        elif stripped.startswith("server "):
            parts = stripped.split(None, 3)
            server = {
                "name": parts[1] if len(parts) > 1 else "",
                "address": parts[2] if len(parts) > 2 else "",
                "params": parts[3] if len(parts) > 3 else "",
            }
            backend["servers"].append(server)

    return backend


def gather_backend_info(module):
    """Gather backend information from HAProxy configuration.

    Args:
        module: AnsibleModule instance with params

    Returns:
        List of backend configuration dictionaries
    """
    config_path = module.params["config_path"]
    name = module.params.get("name")

    try:
        parser = HAProxyConfigParser(config_path)
        parser.read()
    except HAProxyConfigError as e:
        module.fail_json(msg=f"Failed to read config: {str(e)}")

    backends = []

    for section in parser.sections:
        if section["type"] == "backend":
            if name is None or section["name"] == name:
                backends.append(parse_backend_section(section))

    return backends


def main():
    """Entry point for module execution."""
    argument_spec = dict(
        config_path=dict(type="str", default="/etc/haproxy/haproxy.cfg"),
        name=dict(type="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    backends = gather_backend_info(module)
    module.exit_json(changed=False, backends=backends)


if __name__ == "__main__":
    main()

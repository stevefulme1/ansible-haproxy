#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_frontend_info
author: Steve Fulmer (@stevefulme1)
version_added: "1.0.0"
short_description: Gather information about HAProxy frontend configurations
description:
  - Retrieves frontend configuration information from HAProxy configuration file.
  - Returns frontend definitions including bind addresses, mode, ACLs, and backend routing.
  - Supports querying specific frontends or all frontends.
options:
  config_path:
    description:
      - Path to HAProxy configuration file.
    type: str
    default: /etc/haproxy/haproxy.cfg
  name:
    description:
      - Name of a specific frontend to retrieve.
      - If not specified, all frontends are returned.
    type: str
"""

EXAMPLES = """
- name: Get all frontend configurations
  stevefulme1.haproxy.haproxy_frontend_info:
    config_path: /etc/haproxy/haproxy.cfg
  register: result

- name: Get specific frontend configuration
  stevefulme1.haproxy.haproxy_frontend_info:
    config_path: /etc/haproxy/haproxy.cfg
    name: web_front
  register: result

- name: Display frontend bind addresses
  ansible.builtin.debug:
    msg: "Frontend {{ item.name }} binds to {{ item.bind }}"
  loop: "{{ result.frontends }}"
"""

RETURN = """
frontends:
  description: List of frontend configurations.
  returned: always
  type: list
  elements: dict
  contains:
    name:
      description: Frontend name
      type: str
      sample: "web_front"
    bind:
      description: List of bind addresses
      type: list
      elements: str
      sample: ["*:80", "*:443 ssl crt /etc/ssl/cert.pem"]
    mode:
      description: Protocol mode
      type: str
      sample: "http"
    default_backend:
      description: Default backend name
      type: str
      sample: "web_backend"
    acls:
      description: List of ACL definitions
      type: list
      elements: dict
      sample:
        - name: "is_api"
          criterion: "path_beg /api"
    use_backends:
      description: List of conditional backend routing rules
      type: list
      elements: dict
      sample:
        - backend: "api_backend"
          condition: "if is_api"
    options:
      description: List of frontend options
      type: list
      elements: str
      sample: ["httplog", "forwardfor"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_config_parser import (
    HAProxyConfigParser,
    HAProxyConfigError,
)


def parse_frontend_section(section):
    """Parse frontend section into structured data.

    Args:
        section: Section dictionary with type, name, and lines

    Returns:
        Dictionary containing parsed frontend configuration
    """
    frontend = {
        "name": section["name"],
        "bind": [],
        "mode": None,
        "default_backend": None,
        "acls": [],
        "use_backends": [],
        "options": [],
    }

    for line in section["lines"]:
        stripped = line.strip()

        if stripped.startswith("frontend "):
            continue
        elif stripped.startswith("bind "):
            bind_addr = stripped.split(None, 1)[1]
            frontend["bind"].append(bind_addr)
        elif stripped.startswith("mode "):
            frontend["mode"] = stripped.split(None, 1)[1]
        elif stripped.startswith("default_backend "):
            frontend["default_backend"] = stripped.split(None, 1)[1]
        elif stripped.startswith("acl "):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                acl = {
                    "name": parts[1],
                    "criterion": parts[2],
                }
                frontend["acls"].append(acl)
        elif stripped.startswith("use_backend "):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                use_backend = {
                    "backend": parts[1],
                    "condition": parts[2],
                }
                frontend["use_backends"].append(use_backend)
        elif stripped.startswith("option "):
            option = stripped.split(None, 1)[1]
            frontend["options"].append(option)

    return frontend


def gather_frontend_info(module):
    """Gather frontend information from HAProxy configuration.

    Args:
        module: AnsibleModule instance with params

    Returns:
        List of frontend configuration dictionaries
    """
    config_path = module.params["config_path"]
    name = module.params.get("name")

    try:
        parser = HAProxyConfigParser(config_path)
        parser.read()
    except HAProxyConfigError as e:
        module.fail_json(msg=f"Failed to read config: {str(e)}")

    frontends = []

    for section in parser.sections:
        if section["type"] == "frontend":
            if name is None or section["name"] == name:
                frontends.append(parse_frontend_section(section))

    return frontends


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

    frontends = gather_frontend_info(module)
    module.exit_json(changed=False, frontends=frontends)


if __name__ == "__main__":
    main()

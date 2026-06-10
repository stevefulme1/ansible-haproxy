#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_backend
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Manage HAProxy backend definitions
description:
  - Add, modify, or remove backend sections in HAProxy configuration file.
  - Supports server definitions, load balancing algorithms, and health checks.
  - Optionally validates configuration before writing.
options:
  config_path:
    description: Path to HAProxy configuration file.
    type: str
    default: /etc/haproxy/haproxy.cfg
  name:
    description: Name of the backend.
    type: str
    required: true
  state:
    description: Whether the backend should be present or absent.
    type: str
    choices: [present, absent]
    default: present
  mode:
    description: Protocol mode for the backend.
    type: str
    choices: [http, tcp]
  balance:
    description: Load balancing algorithm.
    type: str
  options:
    description:
      - List of HAProxy options for the backend.
      - Each item is a complete option line (e.g., "httpchk GET /health").
    type: list
    elements: str
  servers:
    description: Server definitions for the backend.
    type: list
    elements: dict
    suboptions:
      name:
        description: Server name.
        type: str
        required: true
      address:
        description: Server address and port (e.g., "192.168.1.10:8080").
        type: str
        required: true
      params:
        description: Additional server parameters (e.g., "check inter 3s fall 3 rise 2").
        type: str
  backup:
    description: Mark this backend as a backup backend.
    type: bool
    default: false
  validate:
    description: Validate configuration with haproxy -c before writing.
    type: bool
    default: true
"""

EXAMPLES = """
- name: Add basic backend
  sfulmer.haproxy.haproxy_backend:
    name: api_backend
    state: present
    mode: http
    balance: leastconn

- name: Add backend with servers
  sfulmer.haproxy.haproxy_backend:
    name: web_backend
    mode: http
    balance: roundrobin
    options:
      - httpchk GET /health
      - forwardfor
    servers:
      - name: web1
        address: 10.0.1.10:8080
        params: check inter 3s fall 3 rise 2
      - name: web2
        address: 10.0.1.11:8080
        params: check inter 3s fall 3 rise 2

- name: Remove backend
  sfulmer.haproxy.haproxy_backend:
    name: old_backend
    state: absent
"""

RETURN = """
name:
  description: Name of the backend.
  type: str
  returned: always
  sample: api_backend
config_path:
  description: Path to the configuration file.
  type: str
  returned: always
  sample: /etc/haproxy/haproxy.cfg
"""

import tempfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_config_parser import (
    HAProxyConfigParser,
    HAProxyConfigError,
)


def build_backend_section(name, mode=None, balance=None, options=None, servers=None):
    """Build backend section lines from parameters."""
    lines = [f"backend {name}"]

    if mode:
        lines.append(f"    mode {mode}")

    if balance:
        lines.append(f"    balance {balance}")

    if options:
        for option in options:
            lines.append(f"    option {option}")

    if servers:
        for server in servers:
            server_line = f"    server {server['name']} {server['address']}"
            if server.get("params"):
                server_line += f" {server['params']}"
            lines.append(server_line)

    # Add trailing blank line for proper formatting
    lines.append("")

    return lines


def sections_equal(existing_lines, new_lines):
    """Compare two backend section line lists, ignoring whitespace differences."""
    # Normalize whitespace for comparison
    def normalize(line):
        return " ".join(line.split())

    existing_normalized = [normalize(line) for line in existing_lines]
    new_normalized = [normalize(line) for line in new_lines]

    return existing_normalized == new_normalized


def validate_config(config_path, module):
    """Validate HAProxy configuration using haproxy -c."""
    rc, stdout, stderr = module.run_command(["haproxy", "-c", "-f", config_path])

    if rc != 0:
        module.fail_json(
            msg=f"HAProxy configuration validation failed: {stderr}",
            config_path=config_path,
        )


def run_module(module):
    """Execute the module logic."""
    config_path = module.params["config_path"]
    name = module.params["name"]
    state = module.params["state"]
    mode = module.params["mode"]
    balance = module.params["balance"]
    options = module.params["options"]
    servers = module.params["servers"]
    validate = module.params["validate"]

    result = {
        "changed": False,
        "name": name,
        "config_path": config_path,
    }

    try:
        parser = HAProxyConfigParser(config_path)
        parser.read()
    except HAProxyConfigError as e:
        module.fail_json(msg=str(e))

    existing_section = parser.get_section("backend", name)

    if state == "absent":
        if existing_section:
            # Remove the backend section
            parser.sections.remove(existing_section)
            result["changed"] = True

            if not module.check_mode:
                if validate:
                    # Write to temp file and validate
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as tmp:
                        tmp_path = tmp.name
                        parser.write(tmp_path)
                        validate_config(tmp_path, module)
                        Path(tmp_path).unlink()

                parser.write()
    else:  # state == present
        new_lines = build_backend_section(name, mode, balance, options, servers)

        if existing_section:
            # Check if update is needed
            if not sections_equal(existing_section["lines"], new_lines):
                # Update existing backend
                existing_section["lines"] = new_lines
                result["changed"] = True
        else:
            # Add new backend
            parser.sections.append(
                {
                    "type": "backend",
                    "name": name,
                    "lines": new_lines,
                }
            )
            result["changed"] = True

        if result["changed"] and not module.check_mode:
            if validate:
                # Write to temp file and validate
                with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as tmp:
                    tmp_path = tmp.name
                    parser.write(tmp_path)
                    validate_config(tmp_path, module)
                    Path(tmp_path).unlink()

            parser.write()

    return result


def main():
    """Entry point for module execution."""
    argument_spec = dict(
        config_path=dict(type="str", default="/etc/haproxy/haproxy.cfg"),
        name=dict(type="str", required=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
        mode=dict(type="str", choices=["http", "tcp"]),
        balance=dict(type="str"),
        options=dict(type="list", elements="str"),
        servers=dict(
            type="list",
            elements="dict",
            options=dict(
                name=dict(type="str", required=True),
                address=dict(type="str", required=True),
                params=dict(type="str"),
            ),
        ),
        backup=dict(type="bool", default=False),
        validate=dict(type="bool", default=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = run_module(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

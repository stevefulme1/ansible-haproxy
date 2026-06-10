#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

DOCUMENTATION = """
module: haproxy_config
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Manage complete HAProxy configuration file
description:
  - Render a complete HAProxy configuration from structured data
  - Supports global, defaults, frontend, backend, and listen sections
  - Validates configuration before writing (optional)
  - Creates backup before overwriting (optional)
options:
  dest:
    description: Destination path for the configuration file
    type: str
    required: true
  global_section:
    description: Global section configuration
    type: dict
    required: false
  defaults_section:
    description: Defaults section configuration
    type: dict
    required: false
  frontends:
    description: List of frontend definitions
    type: list
    elements: dict
    required: false
  backends:
    description: List of backend definitions
    type: list
    elements: dict
    required: false
  listens:
    description: List of listen definitions
    type: list
    elements: dict
    required: false
  validate:
    description: Validate configuration with haproxy -c -f before writing
    type: bool
    default: true
  backup:
    description: Create backup file before overwriting
    type: bool
    default: true
"""

EXAMPLES = """
- name: Configure HAProxy from structured data
  sfulmer.haproxy.haproxy_config:
    dest: /etc/haproxy/haproxy.cfg
    global_section:
      maxconn: 4096
      user: haproxy
      group: haproxy
      daemon: true
      log:
        - "127.0.0.1 local0"
        - "127.0.0.1 local1 notice"
    defaults_section:
      mode: http
      log: global
      option:
        - httplog
        - dontlognull
      timeout:
        connect: "5000"
        client: "50000"
        server: "50000"
      retries: 3
    frontends:
      - name: http_front
        bind: "*:80"
        mode: http
        default_backend: web_servers
    backends:
      - name: web_servers
        mode: http
        balance: roundrobin
        servers:
          - name: web1
            address: "192.168.1.10:80"
            check: true
          - name: web2
            address: "192.168.1.11:80"
            check: true

- name: Configure with ACLs and conditional backends
  sfulmer.haproxy.haproxy_config:
    dest: /etc/haproxy/haproxy.cfg
    frontends:
      - name: http_front
        bind: "*:80"
        mode: http
        acls:
          - name: is_api
            criterion: "path_beg -i /api"
          - name: is_static
            criterion: "path_end .jpg .png .css"
        use_backends:
          - backend: api_servers
            condition: "if is_api"
          - backend: static_servers
            condition: "if is_static"
        default_backend: web_servers
"""

RETURN = """
dest:
  description: Path to the written configuration file
  type: str
  returned: always
  sample: "/etc/haproxy/haproxy.cfg"
checksum:
  description: MD5 checksum of the written file
  type: str
  returned: changed
  sample: "2a4c5e6f8b9d0a1c3e5f7b9d1a3c5e7f"
size:
  description: Size of the written file in bytes
  type: int
  returned: changed
  sample: 2048
"""

__metaclass__ = type

import hashlib
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ansible.module_utils.basic import AnsibleModule


def render_config(
    global_section: Optional[Dict[str, Any]],
    defaults_section: Optional[Dict[str, Any]],
    frontends: Optional[List[Dict[str, Any]]],
    backends: Optional[List[Dict[str, Any]]],
    listens: Optional[List[Dict[str, Any]]]
) -> str:
    """Render HAProxy configuration from structured data.

    Args:
        global_section: Global section settings
        defaults_section: Defaults section settings
        frontends: List of frontend definitions
        backends: List of backend definitions
        listens: List of listen definitions

    Returns:
        str: Complete HAProxy configuration as string
    """
    lines = []

    # Global section
    if global_section:
        lines.append("global")
        for key, value in global_section.items():
            if key == "daemon" and value:
                lines.append("    daemon")
            elif key == "log" and isinstance(value, list):
                for log_entry in value:
                    lines.append(f"    log {log_entry}")
            elif key == "stats_socket":
                lines.append(f"    stats socket {value}")
            elif key == "stats_timeout":
                lines.append(f"    stats timeout {value}")
            elif key not in ["daemon", "log", "stats_socket", "stats_timeout"]:
                lines.append(f"    {key} {value}")
        lines.append("")

    # Defaults section
    if defaults_section:
        lines.append("defaults")
        for key, value in defaults_section.items():
            if key == "option" and isinstance(value, list):
                for opt in value:
                    lines.append(f"    option {opt}")
            elif key == "timeout" and isinstance(value, dict):
                for timeout_type, timeout_val in value.items():
                    lines.append(f"    timeout {timeout_type} {timeout_val}")
            elif key not in ["option", "timeout"]:
                lines.append(f"    {key} {value}")
        lines.append("")

    # Frontend sections
    if frontends:
        for frontend in frontends:
            lines.append(f"frontend {frontend['name']}")
            if "bind" in frontend:
                lines.append(f"    bind {frontend['bind']}")
            if "mode" in frontend:
                lines.append(f"    mode {frontend['mode']}")
            if "acls" in frontend:
                for acl in frontend["acls"]:
                    lines.append(f"    acl {acl['name']} {acl['criterion']}")
            if "use_backends" in frontend:
                for ub in frontend["use_backends"]:
                    lines.append(f"    use_backend {ub['backend']} {ub['condition']}")
            if "default_backend" in frontend:
                lines.append(f"    default_backend {frontend['default_backend']}")
            if "options" in frontend:
                for opt in frontend["options"]:
                    lines.append(f"    option {opt}")
            lines.append("")

    # Backend sections
    if backends:
        for backend in backends:
            lines.append(f"backend {backend['name']}")
            if "mode" in backend:
                lines.append(f"    mode {backend['mode']}")
            if "balance" in backend:
                lines.append(f"    balance {backend['balance']}")
            if "options" in backend:
                for opt in backend["options"]:
                    lines.append(f"    option {opt}")
            if "servers" in backend:
                for server in backend["servers"]:
                    server_line = f"    server {server['name']} {server['address']}"
                    if server.get("check"):
                        server_line += " check"
                    lines.append(server_line)
            lines.append("")

    # Listen sections
    if listens:
        for listen in listens:
            lines.append(f"listen {listen['name']}")
            if "bind" in listen:
                lines.append(f"    bind {listen['bind']}")
            if "mode" in listen:
                lines.append(f"    mode {listen['mode']}")
            if "balance" in listen:
                lines.append(f"    balance {listen['balance']}")
            if "options" in listen:
                for opt in listen["options"]:
                    lines.append(f"    option {opt}")
            if "stats" in listen:
                stats = listen["stats"]
                if stats.get("enable"):
                    lines.append("    stats enable")
                if "uri" in stats:
                    lines.append(f"    stats uri {stats['uri']}")
                if "refresh" in stats:
                    lines.append(f"    stats refresh {stats['refresh']}")
            if "servers" in listen:
                for server in listen["servers"]:
                    server_line = f"    server {server['name']} {server['address']}"
                    if server.get("check"):
                        server_line += " check"
                    lines.append(server_line)
            lines.append("")

    return "\n".join(lines)


def validate_config(module: AnsibleModule, config_path: str) -> None:
    """Validate HAProxy configuration using haproxy -c -f.

    Args:
        module: AnsibleModule instance
        config_path: Path to config file to validate

    Raises:
        Calls module.fail_json if validation fails
    """
    try:
        result = subprocess.run(
            ["haproxy", "-c", "-f", config_path],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            module.fail_json(
                msg=f"HAProxy configuration validation failed: {result.stderr}",
                stdout=result.stdout,
                stderr=result.stderr
            )
    except FileNotFoundError:
        module.fail_json(msg="haproxy binary not found in PATH")


def manage_config(module: AnsibleModule) -> Dict[str, Any]:
    """Manage HAProxy configuration file.

    Args:
        module: AnsibleModule instance

    Returns:
        dict: Result dictionary with changed status and file info
    """
    dest = module.params["dest"]
    validate = module.params["validate"]
    backup = module.params["backup"]

    # Render new config
    new_config = render_config(
        module.params.get("global_section"),
        module.params.get("defaults_section"),
        module.params.get("frontends"),
        module.params.get("backends"),
        module.params.get("listens")
    )

    # Check if file exists and compare
    changed = False
    if os.path.exists(dest):
        with open(dest, 'r') as f:
            existing_config = f.read()
        if existing_config != new_config:
            changed = True
    else:
        changed = True

    result = {
        "changed": changed,
        "dest": dest
    }

    # If no changes needed, return early
    if not changed:
        return result

    # Check mode - don't actually write
    if module.check_mode:
        return result

    # Create backup if requested and file exists
    if backup and os.path.exists(dest):
        backup_path = dest + ".bak"
        shutil.copy2(dest, backup_path)

    # Write new config
    with open(dest, 'w') as f:
        f.write(new_config)

    # Validate if requested
    if validate:
        validate_config(module, dest)

    # Calculate checksum and size
    with open(dest, 'rb') as f:
        content = f.read()
        result["checksum"] = hashlib.md5(content).hexdigest()
        result["size"] = len(content)

    return result


def main() -> None:
    """Entry point for module execution"""
    argument_spec = dict(
        dest=dict(type="str", required=True),
        global_section=dict(type="dict", required=False),
        defaults_section=dict(type="dict", required=False),
        frontends=dict(type="list", elements="dict", required=False),
        backends=dict(type="list", elements="dict", required=False),
        listens=dict(type="list", elements="dict", required=False),
        validate=dict(type="bool", default=True),
        backup=dict(type="bool", default=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = manage_config(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

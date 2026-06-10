#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_frontend
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Manage HAProxy frontend configuration
description:
  - Add, modify, or remove frontend sections in HAProxy configuration file.
  - Supports bind addresses, ACL definitions, and conditional backend selection.
  - Provides idempotent configuration management with optional validation.
options:
  config_path:
    description:
      - Path to the HAProxy configuration file.
    type: str
    default: /etc/haproxy/haproxy.cfg
  name:
    description:
      - Name of the frontend.
    type: str
    required: true
  state:
    description:
      - Desired state of the frontend section.
      - C(present) ensures the frontend exists with the specified configuration.
      - C(absent) removes the frontend section.
    type: str
    choices: [present, absent]
    default: present
  bind:
    description:
      - Bind address(es) for the frontend.
      - Can be a single string or a list of bind addresses.
      - Each bind address can include options like SSL certificates.
    type: raw
  mode:
    description:
      - Protocol mode for the frontend.
    type: str
    choices: [http, tcp]
  default_backend:
    description:
      - Default backend to use if no other routing rules match.
    type: str
  options:
    description:
      - List of HAProxy options to add to the frontend.
      - Each option should be a complete HAProxy directive.
    type: list
    elements: str
  acls:
    description:
      - ACL definitions for the frontend.
      - Each ACL must have a name and criterion.
    type: list
    elements: dict
    suboptions:
      name:
        description: ACL name
        type: str
        required: true
      criterion:
        description: ACL matching criterion (e.g., "path_beg /api")
        type: str
        required: true
  use_backends:
    description:
      - Conditional backend selection rules.
      - Each rule specifies a backend and condition.
    type: list
    elements: dict
    suboptions:
      backend:
        description: Backend name
        type: str
        required: true
      condition:
        description: Condition expression (e.g., "if is_api")
        type: str
        required: true
  validate:
    description:
      - Whether to validate the HAProxy configuration after changes.
      - If validation fails, the module will fail and not save changes.
    type: bool
    default: true
"""

EXAMPLES = """
- name: Create a simple HTTP frontend
  stevefulme1.haproxy.haproxy_frontend:
    name: web_front
    bind: "*:80"
    mode: http
    default_backend: web_back

- name: Create HTTPS frontend with multiple binds
  stevefulme1.haproxy.haproxy_frontend:
    name: ssl_front
    bind:
      - "*:80"
      - "*:443 ssl crt /etc/ssl/cert.pem"
    mode: http
    default_backend: web_back

- name: Frontend with ACL-based routing
  stevefulme1.haproxy.haproxy_frontend:
    name: api_front
    bind: "*:80"
    mode: http
    acls:
      - name: is_api
        criterion: path_beg /api
      - name: is_static
        criterion: path_beg /static
    use_backends:
      - backend: api_back
        condition: if is_api
      - backend: static_back
        condition: if is_static
    default_backend: web_back

- name: Remove a frontend
  stevefulme1.haproxy.haproxy_frontend:
    name: old_front
    state: absent

- name: Frontend with custom options
  stevefulme1.haproxy.haproxy_frontend:
    name: custom_front
    bind: "*:80"
    mode: http
    options:
      - "option httplog"
      - "option forwardfor"
    default_backend: web_back
"""

RETURN = """
name:
  description: Name of the frontend.
  type: str
  returned: always
  sample: "web_front"
config_path:
  description: Path to the configuration file.
  type: str
  returned: always
  sample: "/etc/haproxy/haproxy.cfg"
"""

from typing import TYPE_CHECKING

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_config_parser import (
    HAProxyConfigParser,
    HAProxyConfigError,
)


if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional


def build_frontend_lines(params: Dict[str, Any]) -> List[str]:
    """Build frontend configuration lines from module parameters.

    Args:
        params: Module parameters dictionary.

    Returns:
        List of configuration lines for the frontend section.
    """
    name = params["name"]
    lines = [f"frontend {name}"]

    # Add bind directives
    bind_addrs = params.get("bind")
    if bind_addrs:
        if isinstance(bind_addrs, str):
            bind_addrs = [bind_addrs]
        for addr in bind_addrs:
            lines.append(f"    bind {addr}")

    # Add mode
    mode = params.get("mode")
    if mode:
        lines.append(f"    mode {mode}")

    # Add options
    options = params.get("options")
    if options:
        for option in options:
            lines.append(f"    {option}")

    # Add ACLs
    acls = params.get("acls")
    if acls:
        for acl in acls:
            acl_name = acl["name"]
            criterion = acl["criterion"]
            lines.append(f"    acl {acl_name} {criterion}")

    # Add use_backend directives
    use_backends = params.get("use_backends")
    if use_backends:
        for rule in use_backends:
            backend = rule["backend"]
            condition = rule["condition"]
            lines.append(f"    use_backend {backend} {condition}")

    # Add default_backend
    default_backend = params.get("default_backend")
    if default_backend:
        lines.append(f"    default_backend {default_backend}")

    return lines


def sections_match(existing_lines: List[str], new_lines: List[str]) -> bool:
    """Check if existing section matches the desired configuration.

    Args:
        existing_lines: Lines from existing section.
        new_lines: Lines for desired configuration.

    Returns:
        True if sections match, False otherwise.
    """
    # Normalize by stripping whitespace
    existing_normalized = [line.strip() for line in existing_lines if line.strip()]
    new_normalized = [line.strip() for line in new_lines if line.strip()]

    return existing_normalized == new_normalized


def validate_config(module, config_path: str) -> tuple[bool, str]:
    """Validate HAProxy configuration using haproxy -c.

    Args:
        module: The Ansible module instance.
        config_path: Path to the configuration file.

    Returns:
        Tuple of (is_valid, error_message).
    """
    rc, dummy, stderr = module.run_command(["haproxy", "-c", "-f", config_path])
    if rc == 0:
        return True, ""
    return False, stderr


def manage_frontend(module: AnsibleModule) -> Dict[str, Any]:
    """Manage HAProxy frontend configuration.

    Args:
        module: The Ansible module instance.

    Returns:
        Dictionary with 'changed' status and result data.
    """
    config_path = module.params["config_path"]
    name = module.params["name"]
    state = module.params["state"]
    validate = module.params["validate"]

    try:
        parser = HAProxyConfigParser(config_path)
        parser.read()
    except HAProxyConfigError as e:
        module.fail_json(msg=f"Failed to read config: {e}")

    existing_section = parser.get_section("frontend", name)

    if state == "absent":
        if not existing_section:
            return {
                "changed": False,
                "name": name,
                "config_path": config_path,
            }

        if module.check_mode:
            return {
                "changed": True,
                "name": name,
                "config_path": config_path,
            }

        # Remove the frontend section
        parser.sections = [s for s in parser.sections if not (s["type"] == "frontend" and s["name"] == name)]

        parser.write()

        return {
            "changed": True,
            "name": name,
            "config_path": config_path,
        }

    # state == "present"
    new_lines = build_frontend_lines(module.params)

    if existing_section:
        # Check if update is needed
        if sections_match(existing_section["lines"], new_lines):
            return {
                "changed": False,
                "name": name,
                "config_path": config_path,
            }

        if module.check_mode:
            return {
                "changed": True,
                "name": name,
                "config_path": config_path,
            }

        # Update existing section
        existing_section["lines"] = new_lines
    else:
        if module.check_mode:
            return {
                "changed": True,
                "name": name,
                "config_path": config_path,
            }

        # Add new section
        new_section = {
            "type": "frontend",
            "name": name,
            "lines": new_lines,
        }
        parser.sections.append(new_section)

    # Validate if requested
    if validate and not module.check_mode:
        # Write to a temporary location first for validation
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as tmp:
            tmp_path = tmp.name
            parser.write(tmp_path)

        is_valid, error_msg = validate_config(module, tmp_path)

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        if not is_valid:
            module.fail_json(msg=f"Configuration validation failed: {error_msg}")

    # Write the config
    if not module.check_mode:
        parser.write()

    return {
        "changed": True,
        "name": name,
        "config_path": config_path,
    }


def main() -> None:
    """Entry point for module execution."""
    argument_spec = dict(
        config_path=dict(type="str", default="/etc/haproxy/haproxy.cfg"),
        name=dict(type="str", required=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        bind=dict(type="raw"),
        mode=dict(type="str", choices=["http", "tcp"]),
        default_backend=dict(type="str"),
        options=dict(type="list", elements="str"),
        acls=dict(type="list", elements="dict"),
        use_backends=dict(type="list", elements="dict"),
        validate=dict(type="bool", default=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    result = manage_frontend(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

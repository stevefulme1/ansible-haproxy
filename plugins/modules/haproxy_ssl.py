#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: haproxy_ssl
author: Steve Fulmer (@stevefulme1)
version_added: "0.1.0"
short_description: Manage SSL certificates at runtime via HAProxy stats socket
description:
  - Add, update, or remove SSL certificates at runtime without restarting HAProxy.
  - List all SSL certificates currently loaded in HAProxy.
  - Uses the HAProxy Runtime API via stats socket.
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
  state:
    description:
      - Desired state of the SSL certificate.
      - C(present) adds or updates the certificate.
      - C(absent) removes the certificate.
    type: str
    choices: [present, absent]
    default: present
  list_certs:
    description:
      - When C(true), return a list of all loaded certificates without making changes.
      - Overrides I(state) when set.
    type: bool
    default: false
  cert_name:
    description:
      - Certificate filename as known to HAProxy.
      - Required when C(state) is C(present) or C(absent).
      - Example C(/etc/haproxy/ssl/example.com.pem)
    type: str
  cert_content:
    description:
      - PEM certificate content.
      - Required when C(state=present).
      - Should include certificate, intermediate certificates, and private key.
    type: str
"""

EXAMPLES = """
- name: Add or update SSL certificate
  sfulmer.haproxy.haproxy_ssl:
    cert_name: /etc/haproxy/ssl/example.com.pem
    cert_content: |
      -----BEGIN CERTIFICATE-----
      MIIDXTCCAkWgAwIBAgIJAKZ...
      -----END CERTIFICATE-----
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADANBgkqhkiG9w0...
      -----END PRIVATE KEY-----
    state: present

- name: Remove SSL certificate
  sfulmer.haproxy.haproxy_ssl:
    cert_name: /etc/haproxy/ssl/example.com.pem
    state: absent

- name: List all SSL certificates
  sfulmer.haproxy.haproxy_ssl:
    list_certs: true
  register: ssl_certs

- name: Display certificate list
  ansible.builtin.debug:
    msg: "{{ ssl_certs.certs }}"
"""

RETURN = """
changed:
  description: Whether the certificate state was changed.
  type: bool
  returned: always
  sample: true
cert_name:
  description: The name of the managed certificate.
  type: str
  returned: when state is present or absent
  sample: "/etc/haproxy/ssl/example.com.pem"
certs:
  description: List of all certificate names.
  type: list
  elements: str
  returned: when list_certs is true
  sample:
    - "/etc/haproxy/ssl/example.com.pem"
    - "/etc/haproxy/ssl/api.example.com.pem"
"""

from typing import TYPE_CHECKING

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


if TYPE_CHECKING:
    from typing import Any, Dict


def manage_ssl_cert(module: AnsibleModule) -> Dict[str, Any]:
    """Manage HAProxy SSL certificates at runtime.

    Args:
        module: The Ansible module instance.

    Returns:
        Dictionary with 'changed' status and certificate information.
    """
    socket_path = module.params["socket"]
    timeout = module.params["timeout"]
    state = module.params["state"]
    cert_name = module.params["cert_name"]
    cert_content = module.params["cert_content"]

    try:
        client = HAProxySocket(socket_path=socket_path, timeout=timeout)
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to connect to HAProxy socket: {e}")

    # Handle list mode
    if module.params["list_certs"]:
        try:
            output = client.execute("show ssl cert")
            certs = [line.strip() for line in output.strip().split("\n") if line.strip()]
            return {
                "changed": False,
                "certs": certs,
            }
        except HAProxySocketError as e:
            module.fail_json(msg=f"Failed to list SSL certificates: {e}")

    # Validate cert_name is provided for present/absent states
    if not cert_name:
        module.fail_json(msg="cert_name is required when state is present or absent")

    # Handle absent state
    if state == "absent":
        if module.check_mode:
            return {
                "changed": True,
                "cert_name": cert_name,
            }

        try:
            client.execute(f"del ssl cert {cert_name}")
            return {
                "changed": True,
                "cert_name": cert_name,
            }
        except HAProxySocketError as e:
            module.fail_json(msg=f"Failed to remove SSL certificate: {e}")

    # Handle present state
    if not cert_content:
        module.fail_json(msg="cert_content is required when state is present")

    # Check if certificate exists
    cert_exists = False
    try:
        output = client.execute(f"show ssl cert {cert_name}")
        # If the cert exists, output will contain cert details
        # If it doesn't exist, output will contain an error message
        if "Can't locate" not in output and "does not exist" not in output:
            cert_exists = True
    except HAProxySocketError:
        cert_exists = False

    if module.check_mode:
        return {
            "changed": True,
            "cert_name": cert_name,
        }

    # Add or update certificate
    try:
        if not cert_exists:
            # New certificate - need to create it first
            client.execute(f"new ssl cert {cert_name}")

        # Set certificate content (works for both new and existing)
        client.execute(f"set ssl cert {cert_name} <<\n{cert_content}\n")

        # Commit the certificate
        client.execute(f"commit ssl cert {cert_name}")

        return {
            "changed": True,
            "cert_name": cert_name,
        }
    except HAProxySocketError as e:
        module.fail_json(msg=f"Failed to manage SSL certificate: {e}")


def main() -> None:
    """Entry point for module execution."""
    argument_spec = dict(
        socket=dict(type="str", default="/var/run/haproxy/admin.sock"),
        timeout=dict(type="int", default=10),
        state=dict(
            type="str",
            choices=["present", "absent"],
            default="present",
        ),
        cert_name=dict(type="str"),
        cert_content=dict(type="str", no_log=True),
        list_certs=dict(type="bool", default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ("state", "present", ["cert_name", "cert_content"]),
            ("state", "absent", ["cert_name"]),
        ],
    )

    result = manage_ssl_cert(module)
    module.exit_json(**result)


if __name__ == "__main__":
    main()

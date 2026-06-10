# stevefulme1.haproxy

Ansible collection for managing HAProxy load balancers, providing comprehensive lifecycle management including installation, configuration, runtime operations, and event-driven automation.

## Description

This collection enables you to:

- Install HAProxy from package repositories or compile from source
- Generate and validate HAProxy configuration from structured Ansible variables
- Manage runtime operations (server state changes, statistics, SSL certificates)
- Build event-driven automation workflows with HAProxy event sources
- Query detailed information about backends, frontends, servers, and statistics

## Requirements

- `ansible-core` >= 2.16
- Python >= 3.10
- HAProxy >= 2.0 (for runtime socket operations)

## Installation

Install from Ansible Galaxy:

```bash
ansible-galaxy collection install stevefulme1.haproxy
```

Or add to your `requirements.yml`:

```yaml
collections:
  - name: stevefulme1.haproxy
    version: ">=0.1.0"
```

Then install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Quick Start

Here's a simple playbook that installs HAProxy and configures a basic load balancer:

```yaml
---
- name: Deploy HAProxy load balancer
  hosts: loadbalancers
  become: true
  
  roles:
    - role: stevefulme1.haproxy.install
      vars:
        haproxy_version: "2.8"
        haproxy_install_method: package
    
    - role: stevefulme1.haproxy.configure
      vars:
        haproxy_global:
          maxconn: 4096
          log: "/dev/log local0"
        
        haproxy_defaults:
          mode: http
          timeout_connect: 5s
          timeout_client: 30s
          timeout_server: 30s
        
        haproxy_frontends:
          - name: web_frontend
            bind: "*:80"
            default_backend: web_servers
        
        haproxy_backends:
          - name: web_servers
            balance: roundrobin
            servers:
              - name: web1
                address: 192.168.1.10:8080
                check: true
              - name: web2
                address: 192.168.1.11:8080
                check: true
```

## Modules

| Module | Description |
|--------|-------------|
| `haproxy_info` | Gather HAProxy facts (version, stats, backends, frontends, servers) |
| `haproxy_server` | Manage backend server state (enable, disable, drain, set weight) |
| `haproxy_backend` | Manage backend definitions in configuration |
| `haproxy_frontend` | Manage frontend definitions in configuration |
| `haproxy_config` | Full HAProxy configuration management |
| `haproxy_acl` | Manage runtime ACL entries and map files |
| `haproxy_stick_table` | Query and manage stick table entries |
| `haproxy_stats` | Query detailed per-entity statistics |
| `haproxy_ssl` | Manage SSL certificates at runtime |

### Example: Gather HAProxy information

```yaml
- name: Get HAProxy version and backend status
  stevefulme1.haproxy.haproxy_info:
    socket: /var/run/haproxy.sock
    gather_subset:
      - version
      - backends
      - servers
  register: haproxy_facts

- name: Display version
  ansible.builtin.debug:
    msg: "HAProxy version: {{ haproxy_facts.haproxy_info.version }}"
```

### Example: Manage server state

```yaml
- name: Drain web1 for maintenance
  stevefulme1.haproxy.haproxy_server:
    socket: /var/run/haproxy.sock
    backend: web_servers
    server: web1
    state: drain
    wait: true
    wait_timeout: 300

- name: Re-enable web1 after maintenance
  stevefulme1.haproxy.haproxy_server:
    socket: /var/run/haproxy.sock
    backend: web_servers
    server: web1
    state: ready
```

## Roles

| Role | Description |
|------|-------------|
| `install` | Install HAProxy from package or source |
| `configure` | Render haproxy.cfg from structured variables, manage SSL, validate config |

### install role

Installs HAProxy using your preferred method (package manager or source compilation).

**Variables:**

- `haproxy_install_method`: `package` (default) or `source`
- `haproxy_version`: Target version (e.g., `"2.8"`)
- `haproxy_package_name`: Package name (default: `haproxy`)
- `haproxy_compile_options`: List of build flags for source installation

**Example:**

```yaml
- role: stevefulme1.haproxy.install
  vars:
    haproxy_version: "2.8"
    haproxy_install_method: package
```

### configure role

Generates `haproxy.cfg` from structured Ansible variables, manages SSL certificates, and validates configuration before reloading.

**Variables:**

- `haproxy_config_path`: Path to haproxy.cfg (default: `/etc/haproxy/haproxy.cfg`)
- `haproxy_global`: Dict of global section directives
- `haproxy_defaults`: Dict of defaults section directives
- `haproxy_frontends`: List of frontend definitions
- `haproxy_backends`: List of backend definitions
- `haproxy_ssl_certificates`: List of SSL certificate definitions
- `haproxy_validate_config`: Validate before applying (default: `true`)

**Example:**

```yaml
- role: stevefulme1.haproxy.configure
  vars:
    haproxy_global:
      maxconn: 4096
      ssl-default-bind-ciphers: "ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384"
    
    haproxy_ssl_certificates:
      - name: example.com
        cert_path: /etc/ssl/certs/example.com.pem
        key_path: /etc/ssl/private/example.com.key
```

## Event-Driven Ansible (EDA)

The collection includes an event source plugin for building reactive automation workflows based on HAProxy events.

### haproxy_events event source

Monitors HAProxy logs, statistics socket, or admin socket for events and triggers automation.

**Example rulebook:**

```yaml
---
- name: HAProxy reactive automation
  hosts: all
  sources:
    - stevefulme1.haproxy.haproxy_events:
        socket: /var/run/haproxy.sock
        poll_interval: 10
        events:
          - backend_down
          - server_down
          - server_up
  
  rules:
    - name: Alert on backend down
      condition: event.type == "backend_down"
      action:
        run_playbook:
          name: alert_ops_team.yml
          extra_vars:
            backend: "{{ event.backend }}"
    
    - name: Auto-scale on high load
      condition: event.type == "high_load" and event.connections > 1000
      action:
        run_playbook:
          name: scale_backends.yml
```

## License

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.

## Author

Steve Fulmer ([@stevefulme1](https://github.com/stevefulme1))

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## More Information

- [Ansible User Guide](https://docs.ansible.com/ansible/latest/user_guide/index.html)
- [Ansible Collection Development](https://docs.ansible.com/ansible/devel/dev_guide/developing_collections.html)
- [HAProxy Documentation](https://docs.haproxy.org/)

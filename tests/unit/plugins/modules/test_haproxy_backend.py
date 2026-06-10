# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock

import pytest

from ansible_collections.stevefulme1.haproxy.plugins.modules import haproxy_backend


@pytest.fixture
def basic_config(tmp_path):
    """Create a basic HAProxy config file."""
    config = tmp_path / "haproxy.cfg"
    config.write_text(
        "global\n"
        "    maxconn 4096\n"
        "\n"
        "defaults\n"
        "    mode http\n"
        "    timeout connect 5000\n"
    )
    return str(config)


@pytest.fixture
def config_with_backend(tmp_path):
    """Create config with an existing backend."""
    config = tmp_path / "haproxy.cfg"
    config.write_text(
        "global\n"
        "    maxconn 4096\n"
        "\n"
        "defaults\n"
        "    mode http\n"
        "\n"
        "backend web_back\n"
        "    mode http\n"
        "    balance roundrobin\n"
        "    server web1 192.168.1.10:8080 check\n"
    )
    return str(config)


class TestHAProxyBackend:
    def test_add_backend(self, basic_config):
        """Test adding a new backend to config."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "api_backend",
            "state": "present",
            "mode": "http",
            "balance": "leastconn",
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is True
        assert result["name"] == "api_backend"

        # Verify the backend was added
        with open(basic_config) as f:
            content = f.read()
            assert "backend api_backend" in content
            assert "mode http" in content
            assert "balance leastconn" in content

    def test_remove_backend(self, config_with_backend):
        """Test removing an existing backend."""
        module = MagicMock()
        module.params = {
            "config_path": config_with_backend,
            "name": "web_back",
            "state": "absent",
            "mode": None,
            "balance": None,
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is True

        # Verify backend was removed
        with open(config_with_backend) as f:
            content = f.read()
            assert "backend web_back" not in content

    def test_backend_already_absent(self, basic_config):
        """Test removing a backend that doesn't exist."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "nonexistent",
            "state": "absent",
            "mode": None,
            "balance": None,
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is False

    def test_check_mode(self, basic_config):
        """Test check mode doesn't modify config."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "test_backend",
            "state": "present",
            "mode": "tcp",
            "balance": None,
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,
        }
        module.check_mode = True

        original_content = open(basic_config).read()
        result = haproxy_backend.run_module(module)

        assert result["changed"] is True
        # Verify file wasn't modified
        assert open(basic_config).read() == original_content

    def test_add_backend_with_servers(self, basic_config):
        """Test adding backend with server definitions."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "app_backend",
            "state": "present",
            "mode": "http",
            "balance": "roundrobin",
            "options": ["httpchk GET /health", "forwardfor"],
            "servers": [
                {
                    "name": "app1",
                    "address": "10.0.1.10:8080",
                    "params": "check inter 3s fall 3 rise 2",
                },
                {
                    "name": "app2",
                    "address": "10.0.1.11:8080",
                    "params": "check inter 3s fall 3 rise 2",
                },
            ],
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is True

        # Verify servers were added correctly
        with open(basic_config) as f:
            content = f.read()
            assert "backend app_backend" in content
            assert "option httpchk GET /health" in content
            assert "option forwardfor" in content
            assert "server app1 10.0.1.10:8080 check inter 3s fall 3 rise 2" in content
            assert "server app2 10.0.1.11:8080 check inter 3s fall 3 rise 2" in content

    def test_backend_idempotent(self, config_with_backend):
        """Test that adding identical backend is idempotent."""
        module = MagicMock()
        module.params = {
            "config_path": config_with_backend,
            "name": "web_back",
            "state": "present",
            "mode": "http",
            "balance": "roundrobin",
            "options": None,
            "servers": [
                {
                    "name": "web1",
                    "address": "192.168.1.10:8080",
                    "params": "check",
                }
            ],
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        # Should be idempotent - no changes if backend already matches
        assert result["changed"] is False

    def test_backend_update(self, config_with_backend):
        """Test updating an existing backend."""
        module = MagicMock()
        module.params = {
            "config_path": config_with_backend,
            "name": "web_back",
            "state": "present",
            "mode": "tcp",  # Changed from http
            "balance": "leastconn",  # Changed from roundrobin
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is True

        with open(config_with_backend) as f:
            content = f.read()
            assert "mode tcp" in content
            assert "balance leastconn" in content

    def test_validate_disabled(self, basic_config):
        """Test adding backend with validation disabled."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "valid_backend",
            "state": "present",
            "mode": "http",
            "balance": None,
            "options": None,
            "servers": None,
            "backup": False,
            "validate": False,  # Disabled for this test
        }
        module.check_mode = False

        result = haproxy_backend.run_module(module)

        assert result["changed"] is True
        # Verify backend was added
        with open(basic_config) as f:
            content = f.read()
            assert "backend valid_backend" in content

    def test_validate_config_failure(self, basic_config):
        """Test config validation failure."""
        module = MagicMock()
        module.params = {
            "config_path": basic_config,
            "name": "invalid_backend",
            "state": "present",
            "mode": "http",
            "balance": "invalid_algo",
            "options": None,
            "servers": None,
            "backup": False,
            "validate": True,
        }
        module.check_mode = False
        module.run_command = MagicMock(
            return_value=(1, "", "[ALERT] parsing error: invalid balance algorithm")
        )
        module.fail_json = MagicMock(side_effect=Exception("Validation failed"))

        with pytest.raises(Exception, match="Validation failed"):
            haproxy_backend.run_module(module)

        # Verify original file wasn't modified
        with open(basic_config) as f:
            content = f.read()
            assert "invalid_backend" not in content

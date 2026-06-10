# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, mock_open, patch
import hashlib
import os

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_config


class TestRenderConfig:
    """Test the render_config function directly"""

    def test_render_basic_config(self):
        """Test rendering a basic config with all sections"""
        global_section = {
            "maxconn": 4096,
            "user": "haproxy",
            "group": "haproxy",
            "daemon": True,
            "log": ["127.0.0.1 local0", "127.0.0.1 local1 notice"],
            "chroot": "/var/lib/haproxy",
            "stats_socket": "/var/run/haproxy/admin.sock mode 660 level admin",
            "stats_timeout": "30s"
        }

        defaults_section = {
            "mode": "http",
            "log": "global",
            "option": ["httplog", "dontlognull"],
            "timeout": {
                "connect": "5000",
                "client": "50000",
                "server": "50000"
            },
            "retries": 3
        }

        frontends = [
            {
                "name": "http_front",
                "bind": "*:80",
                "mode": "http",
                "default_backend": "web_servers"
            }
        ]

        backends = [
            {
                "name": "web_servers",
                "mode": "http",
                "balance": "roundrobin",
                "servers": [
                    {"name": "web1", "address": "192.168.1.10:80", "check": True},
                    {"name": "web2", "address": "192.168.1.11:80", "check": True}
                ]
            }
        ]

        result = haproxy_config.render_config(
            global_section, defaults_section, frontends, backends, None
        )

        assert "global" in result
        assert "maxconn 4096" in result
        assert "user haproxy" in result
        assert "daemon" in result
        assert "defaults" in result
        assert "mode http" in result
        assert "option httplog" in result
        assert "timeout connect 5000" in result
        assert "frontend http_front" in result
        assert "bind *:80" in result
        assert "default_backend web_servers" in result
        assert "backend web_servers" in result
        assert "balance roundrobin" in result
        assert "server web1 192.168.1.10:80 check" in result
        assert "server web2 192.168.1.11:80 check" in result

    def test_render_minimal_config(self):
        """Test rendering with only required sections"""
        result = haproxy_config.render_config(None, None, None, None, None)

        # Should at least have section headers
        assert isinstance(result, str)

    def test_render_with_listens(self):
        """Test rendering listen sections"""
        listens = [
            {
                "name": "stats",
                "bind": "*:8404",
                "mode": "http",
                "options": ["http-use-htx"],
                "stats": {
                    "enable": True,
                    "uri": "/stats",
                    "refresh": "10s"
                }
            }
        ]

        result = haproxy_config.render_config(None, None, None, None, listens)

        assert "listen stats" in result
        assert "bind *:8404" in result

    def test_render_with_acls(self):
        """Test rendering frontend with ACLs"""
        frontends = [
            {
                "name": "http_front",
                "bind": "*:80",
                "mode": "http",
                "acls": [
                    {"name": "is_api", "criterion": "path_beg -i /api"},
                    {"name": "is_static", "criterion": "path_end .jpg .png .css"}
                ],
                "use_backends": [
                    {"backend": "api_servers", "condition": "if is_api"},
                    {"backend": "static_servers", "condition": "if is_static"}
                ],
                "default_backend": "web_servers"
            }
        ]

        result = haproxy_config.render_config(None, None, frontends, None, None)

        assert "acl is_api path_beg -i /api" in result
        assert "acl is_static path_end .jpg .png .css" in result
        assert "use_backend api_servers if is_api" in result
        assert "use_backend static_servers if is_static" in result


class TestHAProxyConfigModule:
    """Test the full module functionality"""

    @pytest.fixture
    def module_args_basic(self, tmp_path):
        config_file = tmp_path / "haproxy.cfg"
        return {
            "dest": str(config_file),
            "global_section": {
                "maxconn": 4096,
                "user": "haproxy"
            },
            "defaults_section": {
                "mode": "http",
                "timeout": {"connect": "5000"}
            },
            "frontends": [
                {
                    "name": "http_front",
                    "bind": "*:80",
                    "default_backend": "web"
                }
            ],
            "backends": [
                {
                    "name": "web",
                    "balance": "roundrobin",
                    "servers": [
                        {"name": "web1", "address": "192.168.1.10:80"}
                    ]
                }
            ],
            "listens": None,
            "validate": False,
            "backup": True
        }

    @pytest.fixture
    def mock_module(self, module_args_basic):
        mock = MagicMock()
        mock.params = module_args_basic
        mock.check_mode = False
        mock.run_command.return_value = (0, "", "")
        return mock

    def test_changed_when_different(self, mock_module, tmp_path):
        """Test that changed=True when config differs"""
        # Create existing file with different content
        config_file = tmp_path / "haproxy.cfg"
        config_file.write_text("# old config\n")
        mock_module.params["dest"] = str(config_file)

        result = haproxy_config.manage_config(mock_module)

        assert result["changed"] is True
        assert result["dest"] == str(config_file)
        assert "checksum" in result
        assert "size" in result

    def test_no_change_when_identical(self, mock_module, tmp_path):
        """Test that changed=False when config is identical"""
        config_file = tmp_path / "haproxy.cfg"

        # First write to create the config
        mock_module.params["dest"] = str(config_file)
        result1 = haproxy_config.manage_config(mock_module)

        # Read what was written
        existing_content = config_file.read_text()

        # Second write with same params should not change
        result2 = haproxy_config.manage_config(mock_module)

        assert result2["changed"] is False
        assert config_file.read_text() == existing_content

    def test_check_mode(self, mock_module, tmp_path):
        """Test that check_mode doesn't write file"""
        config_file = tmp_path / "haproxy.cfg"
        mock_module.params["dest"] = str(config_file)
        mock_module.check_mode = True

        result = haproxy_config.manage_config(mock_module)

        assert result["changed"] is True
        assert not config_file.exists()

    def test_backup_created(self, mock_module, tmp_path):
        """Test that backup file is created"""
        config_file = tmp_path / "haproxy.cfg"
        backup_file = tmp_path / "haproxy.cfg.bak"

        # Create existing file
        config_file.write_text("# old config\n")
        mock_module.params["dest"] = str(config_file)
        mock_module.params["backup"] = True

        result = haproxy_config.manage_config(mock_module)

        assert result["changed"] is True
        assert backup_file.exists()
        assert backup_file.read_text() == "# old config\n"

    def test_no_backup_when_disabled(self, mock_module, tmp_path):
        """Test that backup is not created when disabled"""
        config_file = tmp_path / "haproxy.cfg"
        backup_file = tmp_path / "haproxy.cfg.bak"

        # Create existing file
        config_file.write_text("# old config\n")
        mock_module.params["dest"] = str(config_file)
        mock_module.params["backup"] = False

        result = haproxy_config.manage_config(mock_module)

        assert result["changed"] is True
        assert not backup_file.exists()

    def test_validation_success(self, mock_module, tmp_path):
        """Test that validation runs when enabled"""
        config_file = tmp_path / "haproxy.cfg"
        mock_module.params["dest"] = str(config_file)
        mock_module.params["validate"] = True
        mock_module.run_command.return_value = (0, "Configuration file is valid", "")

        result = haproxy_config.manage_config(mock_module)

        assert result["changed"] is True
        mock_module.run_command.assert_called()

    def test_validation_failure(self, mock_module, tmp_path):
        """Test that validation failure raises error"""
        config_file = tmp_path / "haproxy.cfg"
        mock_module.params["dest"] = str(config_file)
        mock_module.params["validate"] = True
        mock_module.run_command.return_value = (1, "", "[ALERT] parsing error")

        haproxy_config.manage_config(mock_module)
        mock_module.fail_json.assert_called()

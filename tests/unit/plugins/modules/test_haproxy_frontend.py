# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_frontend


@pytest.fixture
def module_args_present():
    return {
        "config_path": "/tmp/haproxy.cfg",
        "name": "web_front",
        "state": "present",
        "bind": "*:80",
        "mode": "http",
        "default_backend": "web_back",
        "options": None,
        "acls": None,
        "use_backends": None,
        "validate": False,
    }


@pytest.fixture
def mock_module(module_args_present):
    mock = MagicMock()
    mock.params = module_args_present
    mock.check_mode = False
    return mock


class TestHAProxyFrontend:
    def test_add_frontend(self, tmp_path, mock_module):
        """Test adding a new frontend section."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "defaults\n"
            "    mode http\n"
        )

        mock_module.params["config_path"] = str(config)

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True
        assert result["name"] == "web_front"
        assert result["config_path"] == str(config)

        content = config.read_text()
        assert "frontend web_front" in content
        assert "bind *:80" in content
        assert "mode http" in content
        assert "default_backend web_back" in content

    def test_remove_frontend(self, tmp_path, mock_module):
        """Test removing a frontend section."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "frontend web_front\n"
            "    bind *:80\n"
            "    mode http\n"
            "    default_backend web_back\n"
            "\n"
            "backend web_back\n"
            "    server web1 127.0.0.1:8080\n"
        )

        mock_module.params["config_path"] = str(config)
        mock_module.params["state"] = "absent"

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True
        assert result["name"] == "web_front"

        content = config.read_text()
        assert "frontend web_front" not in content
        assert "backend web_back" in content

    def test_frontend_with_acls(self, tmp_path, mock_module):
        """Test adding a frontend with ACL definitions and use_backend."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
        )

        mock_module.params["config_path"] = str(config)
        mock_module.params["acls"] = [
            {"name": "is_api", "criterion": "path_beg /api"},
            {"name": "is_static", "criterion": "path_beg /static"},
        ]
        mock_module.params["use_backends"] = [
            {"backend": "api_back", "condition": "if is_api"},
            {"backend": "static_back", "condition": "if is_static"},
        ]

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True

        content = config.read_text()
        assert "acl is_api path_beg /api" in content
        assert "acl is_static path_beg /static" in content
        assert "use_backend api_back if is_api" in content
        assert "use_backend static_back if is_static" in content

    def test_check_mode(self, tmp_path, mock_module):
        """Test check mode doesn't write to the file."""
        config = tmp_path / "haproxy.cfg"
        original_content = "global\n    maxconn 4096\n"
        config.write_text(original_content)

        mock_module.params["config_path"] = str(config)
        mock_module.check_mode = True

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True

        # File should not be modified in check mode
        assert config.read_text() == original_content

    def test_multiple_binds(self, tmp_path, mock_module):
        """Test frontend with multiple bind addresses."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
        )

        mock_module.params["config_path"] = str(config)
        mock_module.params["bind"] = [
            "*:80",
            "*:443 ssl crt /etc/ssl/cert.pem",
        ]

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True

        content = config.read_text()
        assert "bind *:80" in content
        assert "bind *:443 ssl crt /etc/ssl/cert.pem" in content

    def test_frontend_already_exists_no_change(self, tmp_path, mock_module):
        """Test that no change is made if frontend already matches."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "frontend web_front\n"
            "    bind *:80\n"
            "    mode http\n"
            "    default_backend web_back\n"
        )

        mock_module.params["config_path"] = str(config)

        result = haproxy_frontend.manage_frontend(mock_module)

        # Should detect no change needed
        assert result["changed"] is False

    def test_frontend_update(self, tmp_path, mock_module):
        """Test updating an existing frontend with different config."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "frontend web_front\n"
            "    bind *:8080\n"
            "    mode tcp\n"
        )

        mock_module.params["config_path"] = str(config)

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is True

        content = config.read_text()
        assert "bind *:80" in content
        assert "bind *:8080" not in content
        assert "mode http" in content
        assert "mode tcp" not in content

    def test_remove_nonexistent_frontend_no_change(self, tmp_path, mock_module):
        """Test removing a frontend that doesn't exist."""
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
        )

        mock_module.params["config_path"] = str(config)
        mock_module.params["state"] = "absent"

        result = haproxy_frontend.manage_frontend(mock_module)

        assert result["changed"] is False

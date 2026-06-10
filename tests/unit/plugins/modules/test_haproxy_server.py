# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_server


@pytest.fixture
def module_args_enable():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "backend": "web_backend",
        "server": "server1",
        "state": "enabled",
        "weight": None,
        "drain": False,
        "wait": True,
        "wait_retries": 25,
        "wait_interval": 2,
    }


@pytest.fixture
def mock_module(module_args_enable):
    mock = MagicMock()
    mock.params = module_args_enable
    mock.check_mode = False
    return mock


class TestHAProxyServer:
    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_enable_server(self, mock_socket_class, mock_module):
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = "\n"
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "DOWN"},
        ]

        result = haproxy_server.manage_server(mock_module)

        mock_client.execute.assert_called_with("enable server web_backend/server1")
        assert result["changed"] is True

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_disable_server(self, mock_socket_class, mock_module):
        mock_module.params["state"] = "disabled"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = "\n"
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "UP"},
        ]

        result = haproxy_server.manage_server(mock_module)

        mock_client.execute.assert_called_with("disable server web_backend/server1")
        assert result["changed"] is True

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_drain_server(self, mock_socket_class, mock_module):
        mock_module.params["state"] = "drain"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = "\n"
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "UP"},
        ]

        result = haproxy_server.manage_server(mock_module)

        mock_client.execute.assert_called_with("set server web_backend/server1 state drain")
        assert result["changed"] is True

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_set_weight(self, mock_socket_class, mock_module):
        mock_module.params["weight"] = 50
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = "\n"
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "UP", "weight": "100"},
        ]

        result = haproxy_server.manage_server(mock_module)

        assert result["changed"] is True

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_already_enabled_no_change(self, mock_socket_class, mock_module):
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "UP"},
        ]

        result = haproxy_server.manage_server(mock_module)

        assert result["changed"] is False

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_server.HAProxySocket")
    def test_check_mode(self, mock_socket_class, mock_module):
        mock_module.check_mode = True
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = [
            {"pxname": "web_backend", "svname": "server1", "status": "DOWN"},
        ]

        result = haproxy_server.manage_server(mock_module)

        assert result["changed"] is True
        mock_client.execute.assert_not_called()

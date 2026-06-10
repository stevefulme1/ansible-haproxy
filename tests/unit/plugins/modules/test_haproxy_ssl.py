# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, call, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_ssl


@pytest.fixture
def module_args_present():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "state": "present",
        "cert_name": "/etc/haproxy/ssl/example.com.pem",
        "cert_content": "-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAKZ...\n-----END CERTIFICATE-----",
    }


@pytest.fixture
def module_args_absent():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "state": "absent",
        "cert_name": "/etc/haproxy/ssl/example.com.pem",
        "cert_content": None,
    }


@pytest.fixture
def module_args_list():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "state": "list",
        "cert_name": None,
        "cert_content": None,
    }


@pytest.fixture
def mock_module(module_args_present):
    mock = MagicMock()
    mock.params = module_args_present
    mock.check_mode = False
    return mock


class TestHAProxySSL:
    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_add_new_cert(self, mock_socket_class, mock_module):
        """Test adding a new SSL certificate."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show ssl cert <name> returns error for non-existing cert
        mock_client.execute.side_effect = [
            "Can't locate the SSL certificate file",  # show ssl cert check
            "",  # new ssl cert
            "",  # set ssl cert
            "",  # commit ssl cert
        ]

        result = haproxy_ssl.manage_ssl_cert(mock_module)

        expected_calls = [
            call("show ssl cert /etc/haproxy/ssl/example.com.pem"),
            call("new ssl cert /etc/haproxy/ssl/example.com.pem"),
            call("set ssl cert /etc/haproxy/ssl/example.com.pem <<\n-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAKZ...\n-----END CERTIFICATE-----\n"),
            call("commit ssl cert /etc/haproxy/ssl/example.com.pem"),
        ]
        assert mock_client.execute.call_args_list == expected_calls
        assert result["changed"] is True
        assert result["cert_name"] == "/etc/haproxy/ssl/example.com.pem"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_update_existing_cert(self, mock_socket_class, mock_module):
        """Test updating an existing SSL certificate."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show ssl cert <name> returns cert details for existing cert
        mock_client.execute.side_effect = [
            "Filename: /etc/haproxy/ssl/example.com.pem\nStatus: Used\n",  # show ssl cert check
            "",  # set ssl cert
            "",  # commit ssl cert
        ]

        result = haproxy_ssl.manage_ssl_cert(mock_module)

        expected_calls = [
            call("show ssl cert /etc/haproxy/ssl/example.com.pem"),
            call("set ssl cert /etc/haproxy/ssl/example.com.pem <<\n-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAKZ...\n-----END CERTIFICATE-----\n"),
            call("commit ssl cert /etc/haproxy/ssl/example.com.pem"),
        ]
        assert mock_client.execute.call_args_list == expected_calls
        assert result["changed"] is True
        assert result["cert_name"] == "/etc/haproxy/ssl/example.com.pem"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_remove_cert(self, mock_socket_class, module_args_absent):
        """Test removing an SSL certificate."""
        mock = MagicMock()
        mock.params = module_args_absent
        mock.check_mode = False

        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = ""

        result = haproxy_ssl.manage_ssl_cert(mock)

        mock_client.execute.assert_called_once_with("del ssl cert /etc/haproxy/ssl/example.com.pem")
        assert result["changed"] is True
        assert result["cert_name"] == "/etc/haproxy/ssl/example.com.pem"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_list_certs(self, mock_socket_class, module_args_list):
        """Test listing all SSL certificates."""
        mock = MagicMock()
        mock.params = module_args_list
        mock.check_mode = False

        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = (
            "/etc/haproxy/ssl/example.com.pem\n"
            "/etc/haproxy/ssl/api.example.com.pem\n"
        )

        result = haproxy_ssl.manage_ssl_cert(mock)

        mock_client.execute.assert_called_once_with("show ssl cert")
        assert result["changed"] is False
        assert result["certs"] == [
            "/etc/haproxy/ssl/example.com.pem",
            "/etc/haproxy/ssl/api.example.com.pem",
        ]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_check_mode(self, mock_socket_class, mock_module):
        """Test check mode - no commands should be executed."""
        mock_module.check_mode = True
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show ssl cert returns error for non-existing cert
        mock_client.execute.return_value = "Can't locate the SSL certificate file"

        result = haproxy_ssl.manage_ssl_cert(mock_module)

        # Only the check command should be called, not the modification commands
        mock_client.execute.assert_called_once_with("show ssl cert /etc/haproxy/ssl/example.com.pem")
        assert result["changed"] is True
        assert result["cert_name"] == "/etc/haproxy/ssl/example.com.pem"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_ssl.HAProxySocket")
    def test_list_empty_certs(self, mock_socket_class, module_args_list):
        """Test listing SSL certificates when none exist."""
        mock = MagicMock()
        mock.params = module_args_list
        mock.check_mode = False

        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = ""

        result = haproxy_ssl.manage_ssl_cert(mock)

        assert result["changed"] is False
        assert result["certs"] == []

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

import socket
from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.module_utils.haproxy_socket import (
    HAProxySocket,
    HAProxySocketError,
)


class TestHAProxySocket:
    def test_init_unix_socket(self):
        sock = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")
        assert sock.socket_path == "/var/run/haproxy/admin.sock"
        assert sock.timeout == 10

    def test_init_tcp_socket(self):
        sock = HAProxySocket(socket_path="tcp://127.0.0.1:9999")
        assert sock.socket_path == "tcp://127.0.0.1:9999"

    def test_init_custom_timeout(self):
        sock = HAProxySocket(socket_path="/var/run/haproxy/admin.sock", timeout=30)
        assert sock.timeout == 30

    @patch("socket.socket")
    def test_execute_unix_command(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [b"1.8.30\n", b""]

        client = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")
        result = client.execute("show info")

        mock_sock.connect.assert_called_once_with("/var/run/haproxy/admin.sock")
        mock_sock.sendall.assert_called_once_with(b"show info\n")
        assert result == "1.8.30\n"

    @patch("socket.socket")
    def test_execute_tcp_command(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [b"OK\n", b""]

        client = HAProxySocket(socket_path="tcp://127.0.0.1:9999")
        result = client.execute("show info")

        mock_sock.connect.assert_called_once_with(("127.0.0.1", 9999))
        assert result == "OK\n"

    @patch("socket.socket")
    def test_execute_connection_refused(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        client = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")

        with pytest.raises(HAProxySocketError, match="Connection refused"):
            client.execute("show info")

    @patch("socket.socket")
    def test_execute_timeout(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout("timed out")

        client = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")

        with pytest.raises(HAProxySocketError, match="timed out"):
            client.execute("show info")

    @patch("socket.socket")
    def test_get_stats_csv(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        csv_output = (
            "# pxname,svname,qcur,qmax,scur,smax,slim,stot\n"
            "frontend,FRONTEND,0,0,1,10,2000,500\n"
            "backend,server1,0,0,0,5,200,100\n"
        )
        mock_sock.recv.side_effect = [csv_output.encode(), b""]

        client = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")
        result = client.get_stats()

        assert len(result) == 2
        assert result[0]["pxname"] == "frontend"
        assert result[1]["svname"] == "server1"

    @patch("socket.socket")
    def test_get_info(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        info_output = "Name: HAProxy\nVersion: 2.8.3\nUptime_sec: 12345\nNode: lb01\n"
        mock_sock.recv.side_effect = [info_output.encode(), b""]

        client = HAProxySocket(socket_path="/var/run/haproxy/admin.sock")
        result = client.get_info()

        assert result["Name"] == "HAProxy"
        assert result["Version"] == "2.8.3"
        assert result["Uptime_sec"] == "12345"

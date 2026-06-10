# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_info


@pytest.fixture
def module_args():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
    }


@pytest.fixture
def mock_module(module_args):
    mock = MagicMock()
    mock.params = module_args
    mock.check_mode = False
    return mock


class TestHAProxyInfo:
    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_info.HAProxySocket")
    def test_gather_info(self, mock_socket_class, mock_module):
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_info.return_value = {
            "Name": "HAProxy",
            "Version": "2.8.3",
            "Uptime_sec": "12345",
        }
        mock_client.get_stats.return_value = [
            {"pxname": "web_frontend", "svname": "FRONTEND", "scur": "5"},
            {"pxname": "web_backend", "svname": "server1", "scur": "2", "status": "UP"},
            {"pxname": "web_backend", "svname": "BACKEND", "scur": "2"},
        ]

        result = haproxy_info.gather_info(mock_module)

        assert result["version"] == "2.8.3"
        assert result["uptime_seconds"] == 12345
        assert "web_frontend" in result["frontends"]
        assert "web_backend" in result["backends"]
        assert "server1" in result["backends"]["web_backend"]["servers"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_info.HAProxySocket")
    def test_gather_info_connection_error(self, mock_socket_class, mock_module):
        mock_socket_class.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            haproxy_info.gather_info(mock_module)

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.stevefulme1.haproxy.plugins.modules import haproxy_stats


@pytest.fixture
def module_args():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "filter_type": "all",
    }


@pytest.fixture
def mock_module(module_args):
    mock = MagicMock()
    mock.params = module_args
    mock.check_mode = False
    return mock


@pytest.fixture
def mock_stats_data():
    """Mock stats data with 2 frontends, 2 backends, 4 servers."""
    return [
        {
            "pxname": "web_frontend",
            "svname": "FRONTEND",
            "status": "OPEN",
            "scur": "10",
            "smax": "50",
            "stot": "1000",
            "bin": "10240",
            "bout": "20480",
            "rate": "5",
            "check_status": "",
            "weight": "",
        },
        {
            "pxname": "api_frontend",
            "svname": "FRONTEND",
            "status": "OPEN",
            "scur": "5",
            "smax": "25",
            "stot": "500",
            "bin": "5120",
            "bout": "10240",
            "rate": "2",
            "check_status": "",
            "weight": "",
        },
        {
            "pxname": "web_backend",
            "svname": "web_server1",
            "status": "UP",
            "scur": "3",
            "smax": "20",
            "stot": "400",
            "bin": "4096",
            "bout": "8192",
            "rate": "2",
            "check_status": "L7OK",
            "weight": "100",
        },
        {
            "pxname": "web_backend",
            "svname": "web_server2",
            "status": "UP",
            "scur": "2",
            "smax": "15",
            "stot": "300",
            "bin": "3072",
            "bout": "6144",
            "rate": "1",
            "check_status": "L7OK",
            "weight": "100",
        },
        {
            "pxname": "web_backend",
            "svname": "BACKEND",
            "status": "UP",
            "scur": "5",
            "smax": "35",
            "stot": "700",
            "bin": "7168",
            "bout": "14336",
            "rate": "3",
            "check_status": "",
            "weight": "",
        },
        {
            "pxname": "api_backend",
            "svname": "api_server1",
            "status": "UP",
            "scur": "1",
            "smax": "10",
            "stot": "200",
            "bin": "2048",
            "bout": "4096",
            "rate": "1",
            "check_status": "L7OK",
            "weight": "100",
        },
        {
            "pxname": "api_backend",
            "svname": "api_server2",
            "status": "DOWN",
            "scur": "0",
            "smax": "5",
            "stot": "100",
            "bin": "1024",
            "bout": "2048",
            "rate": "0",
            "check_status": "L4TOUT",
            "weight": "0",
        },
        {
            "pxname": "api_backend",
            "svname": "BACKEND",
            "status": "UP",
            "scur": "1",
            "smax": "15",
            "stot": "300",
            "bin": "3072",
            "bout": "6144",
            "rate": "1",
            "check_status": "",
            "weight": "",
        },
    ]


class TestHAProxyStats:
    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_get_all_stats(self, mock_socket_class, mock_module, mock_stats_data):
        """Test getting all stats with no filter."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 8
        assert result["summary"]["total_frontends"] == 2
        assert result["summary"]["total_backends"] == 2
        assert result["summary"]["total_servers"] == 4
        assert not result["changed"]

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_filter_frontends(self, mock_socket_class, mock_module, mock_stats_data):
        """Test filtering by frontend type."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_type"] = "frontend"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 2
        assert all(s["svname"] == "FRONTEND" for s in result["stats"])
        assert result["summary"]["total_frontends"] == 2

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_filter_backends(self, mock_socket_class, mock_module, mock_stats_data):
        """Test filtering by backend type."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_type"] = "backend"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 2
        assert all(s["svname"] == "BACKEND" for s in result["stats"])
        assert result["summary"]["total_backends"] == 2

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_filter_servers(self, mock_socket_class, mock_module, mock_stats_data):
        """Test filtering by server type (excludes FRONTEND/BACKEND)."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_type"] = "server"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 4
        assert all(s["svname"] not in ("FRONTEND", "BACKEND") for s in result["stats"])
        assert result["summary"]["total_servers"] == 4

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_filter_by_name(self, mock_socket_class, mock_module, mock_stats_data):
        """Test filtering by specific frontend/backend name."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_name"] = "web_backend"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 3
        assert all(s["pxname"] == "web_backend" for s in result["stats"])

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_filter_by_server(self, mock_socket_class, mock_module, mock_stats_data):
        """Test filtering by specific server name."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_type"] = "server"
        mock_module.params["filter_server"] = "web_server1"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 1
        assert result["stats"][0]["svname"] == "web_server1"

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_summary_counts(self, mock_socket_class, mock_module, mock_stats_data):
        """Test that summary counts are correct."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data

        result = haproxy_stats.get_stats(mock_module)

        summary = result["summary"]
        assert summary["total_frontends"] == 2
        assert summary["total_backends"] == 2
        assert summary["total_servers"] == 4
        # Total sessions is sum of all stot
        assert summary["total_sessions"] == 3500

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_combined_filters(self, mock_socket_class, mock_module, mock_stats_data):
        """Test combining filter_type and filter_name."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.params["filter_type"] = "server"
        mock_module.params["filter_name"] = "api_backend"

        result = haproxy_stats.get_stats(mock_module)

        assert len(result["stats"]) == 2
        assert all(s["pxname"] == "api_backend" for s in result["stats"])
        assert all(s["svname"] not in ("FRONTEND", "BACKEND") for s in result["stats"])

    @patch("ansible_collections.stevefulme1.haproxy.plugins.modules.haproxy_stats.HAProxySocket")
    def test_check_mode_supported(self, mock_socket_class, mock_module, mock_stats_data):
        """Test that check mode is supported (read-only module)."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.get_stats.return_value = mock_stats_data
        mock_module.check_mode = True

        result = haproxy_stats.get_stats(mock_module)

        assert not result["changed"]
        assert len(result["stats"]) == 8

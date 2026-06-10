# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_stick_table


@pytest.fixture
def module_args_show():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "table": "web_back",
        "action": "show",
        "key": None,
        "data_type": None,
    }


@pytest.fixture
def mock_module(module_args_show):
    mock = MagicMock()
    mock.params = module_args_show
    mock.check_mode = False
    return mock


class TestHAProxyStickTable:
    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_show_table(self, mock_socket_class, mock_module):
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = """# table: web_back, type: ip, size:204800, used:2
0x1234: key=10.0.0.1 use=0 exp=30000 gpc0=5 conn_rate(30000)=2
0x5678: key=10.0.0.2 use=1 exp=25000 gpc0=0 conn_rate(30000)=10
"""

        result = haproxy_stick_table.manage_stick_table(mock_module)

        mock_client.execute.assert_called_with("show table web_back")
        assert result["changed"] is False
        assert result["table"] == "web_back"
        assert result["entry_count"] == 2
        assert len(result["entries"]) == 2
        assert result["entries"][0]["key"] == "10.0.0.1"
        assert result["entries"][0]["use"] == "0"
        assert result["entries"][0]["exp"] == "30000"
        assert result["entries"][0]["gpc0"] == "5"
        assert result["entries"][1]["key"] == "10.0.0.2"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_lookup_key(self, mock_socket_class, mock_module):
        mock_module.params["action"] = "lookup"
        mock_module.params["key"] = "10.0.0.1"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = """# table: web_back, type: ip, size:204800, used:1
0x1234: key=10.0.0.1 use=0 exp=30000 gpc0=5 conn_rate(30000)=2
"""

        result = haproxy_stick_table.manage_stick_table(mock_module)

        mock_client.execute.assert_called_with("show table web_back key 10.0.0.1")
        assert result["changed"] is False
        assert result["entry_count"] == 1
        assert result["entries"][0]["key"] == "10.0.0.1"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_clear_table(self, mock_socket_class, mock_module):
        mock_module.params["action"] = "clear"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = "\n"

        result = haproxy_stick_table.manage_stick_table(mock_module)

        mock_client.execute.assert_called_with("clear table web_back")
        assert result["changed"] is True
        assert result["table"] == "web_back"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_clear_check_mode(self, mock_socket_class, mock_module):
        mock_module.params["action"] = "clear"
        mock_module.check_mode = True
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        result = haproxy_stick_table.manage_stick_table(mock_module)

        mock_client.execute.assert_not_called()
        assert result["changed"] is True
        assert result["table"] == "web_back"

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_show_empty_table(self, mock_socket_class, mock_module):
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = """# table: web_back, type: ip, size:204800, used:0
"""

        result = haproxy_stick_table.manage_stick_table(mock_module)

        assert result["changed"] is False
        assert result["entry_count"] == 0
        assert result["entries"] == []

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_stick_table.HAProxySocket")
    def test_show_with_data_type_filter(self, mock_socket_class, mock_module):
        mock_module.params["data_type"] = "gpc0"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client
        mock_client.execute.return_value = """# table: web_back, type: ip, size:204800, used:1
0x1234: key=10.0.0.1 use=0 exp=30000 gpc0=5
"""

        result = haproxy_stick_table.manage_stick_table(mock_module)

        mock_client.execute.assert_called_with("show table web_back data.gpc0")
        assert result["entry_count"] == 1

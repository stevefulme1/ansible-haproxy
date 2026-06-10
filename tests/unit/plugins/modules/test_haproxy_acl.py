# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.sfulmer.haproxy.plugins.modules import haproxy_acl


@pytest.fixture
def module_args_present():
    return {
        "socket": "/var/run/haproxy/admin.sock",
        "timeout": 10,
        "acl_name": "blocked_ips",
        "state": "present",
        "value": "10.0.0.1",
    }


@pytest.fixture
def mock_module(module_args_present):
    mock = MagicMock()
    mock.params = module_args_present
    mock.check_mode = False
    return mock


class TestHAProxyAcl:
    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_add_acl_entry(self, mock_socket_class, mock_module):
        """Test adding a new ACL entry that doesn't exist yet."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show acl returns entries without the new value
        mock_client.execute.side_effect = [
            "0x1234 10.0.0.2\n0x5678 10.0.0.3\n",  # show acl (initial check)
            "",  # add acl response
            "0x1234 10.0.0.1\n0x5678 10.0.0.2\n0x9abc 10.0.0.3\n",  # show acl (final)
        ]

        result = haproxy_acl.manage_acl(mock_module)

        assert mock_client.execute.call_count == 3
        assert any("add acl blocked_ips 10.0.0.1" in str(call) for call in mock_client.execute.call_args_list)
        assert result["changed"] is True
        assert "10.0.0.1" in result["entries"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_add_existing_entry_no_change(self, mock_socket_class, mock_module):
        """Test adding an ACL entry that already exists."""
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show acl returns entries including the value we're trying to add
        mock_client.execute.return_value = "0x1234 10.0.0.1\n0x5678 10.0.0.2\n"

        result = haproxy_acl.manage_acl(mock_module)

        # Should only call show acl, not add acl
        assert mock_client.execute.call_count == 1
        assert "show acl" in str(mock_client.execute.call_args_list[0])
        assert result["changed"] is False
        assert "10.0.0.1" in result["entries"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_remove_acl_entry(self, mock_socket_class, mock_module):
        """Test removing an ACL entry that exists."""
        mock_module.params["state"] = "absent"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        mock_client.execute.side_effect = [
            "0x1234 10.0.0.1\n0x5678 10.0.0.2\n",  # show acl (initial check)
            "",  # del acl response
            "0x5678 10.0.0.2\n",  # show acl (final)
        ]

        result = haproxy_acl.manage_acl(mock_module)

        assert mock_client.execute.call_count == 3
        assert any("del acl blocked_ips 10.0.0.1" in str(call) for call in mock_client.execute.call_args_list)
        assert result["changed"] is True
        assert "10.0.0.1" not in result["entries"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_remove_missing_entry_no_change(self, mock_socket_class, mock_module):
        """Test removing an ACL entry that doesn't exist."""
        mock_module.params["state"] = "absent"
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show acl returns entries without the value we're trying to remove
        mock_client.execute.return_value = "0x5678 10.0.0.2\n0x9abc 10.0.0.3\n"

        result = haproxy_acl.manage_acl(mock_module)

        # Should only call show acl, not del acl
        assert mock_client.execute.call_count == 1
        assert "show acl" in str(mock_client.execute.call_args_list[0])
        assert result["changed"] is False
        assert "10.0.0.1" not in result["entries"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_list_acl(self, mock_socket_class, mock_module):
        """Test listing ACL entries."""
        mock_module.params["state"] = "list"
        mock_module.params["value"] = None
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        mock_client.execute.return_value = "0x1234 10.0.0.1\n0x5678 10.0.0.2\n0x9abc 10.0.0.3\n"

        result = haproxy_acl.manage_acl(mock_module)

        assert mock_client.execute.call_count == 1
        assert "show acl blocked_ips" in str(mock_client.execute.call_args_list[0])
        assert result["changed"] is False
        assert len(result["entries"]) == 3
        assert "10.0.0.1" in result["entries"]
        assert "10.0.0.2" in result["entries"]
        assert "10.0.0.3" in result["entries"]

    @patch("ansible_collections.sfulmer.haproxy.plugins.modules.haproxy_acl.HAProxySocket")
    def test_check_mode(self, mock_socket_class, mock_module):
        """Test check mode doesn't execute add/del commands."""
        mock_module.check_mode = True
        mock_client = MagicMock()
        mock_socket_class.return_value = mock_client

        # show acl returns entries without the new value
        mock_client.execute.return_value = "0x5678 10.0.0.2\n"

        result = haproxy_acl.manage_acl(mock_module)

        # Should call show acl but not add acl in check mode
        assert mock_client.execute.call_count == 1
        assert "show acl" in str(mock_client.execute.call_args_list[0])
        assert result["changed"] is True
        # In check mode, entries should reflect current state, not proposed change
        assert "10.0.0.1" not in result["entries"]

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Pytest configuration for stevefulme1.haproxy collection tests."""

from __future__ import absolute_import, division, print_function

import sys

# Add /tmp to sys.path to enable ansible_collections.stevefulme1.haproxy namespace import
# The collection is symlinked at /tmp/ansible_collections/sfulmer/haproxy
if "/tmp" not in sys.path:
    sys.path.insert(0, "/tmp")

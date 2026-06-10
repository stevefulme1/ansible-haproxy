# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

import sys
from pathlib import Path


# Add extensions path so we can import the EDA plugin directly
sys.path.insert(0, str(Path(__file__).parents[4] / "extensions" / "eda" / "plugins" / "event_source"))

from haproxy_events import _detect_changes


class TestDetectChanges:
    def test_server_state_change_detected(self):
        previous = [
            {"pxname": "web", "svname": "srv1", "status": "UP", "scur": "5"},
        ]
        current = [
            {"pxname": "web", "svname": "srv1", "status": "DOWN", "scur": "0"},
        ]

        events = _detect_changes(previous, current)

        assert len(events) == 1
        assert events[0]["type"] == "server_state_change"
        assert events[0]["data"]["backend"] == "web"
        assert events[0]["data"]["server"] == "srv1"
        assert events[0]["data"]["previous_status"] == "UP"
        assert events[0]["data"]["current_status"] == "DOWN"

    def test_no_change_no_event(self):
        stats = [
            {"pxname": "web", "svname": "srv1", "status": "UP", "scur": "5"},
        ]

        events = _detect_changes(stats, stats)

        assert len(events) == 0

    def test_connection_threshold_breach(self):
        previous = [
            {"pxname": "web", "svname": "FRONTEND", "status": "OPEN", "scur": "50", "slim": "200"},
        ]
        current = [
            {"pxname": "web", "svname": "FRONTEND", "status": "OPEN", "scur": "180", "slim": "200"},
        ]

        events = _detect_changes(previous, current, connection_threshold=0.8)

        threshold_events = [e for e in events if e["type"] == "connection_threshold"]
        assert len(threshold_events) == 1
        assert threshold_events[0]["data"]["frontend"] == "web"
        assert threshold_events[0]["data"]["utilization_pct"] == 90.0

    def test_new_server_detected(self):
        previous = []
        current = [
            {"pxname": "web", "svname": "srv1", "status": "UP", "scur": "0"},
        ]

        events = _detect_changes(previous, current)

        assert len(events) == 1
        assert events[0]["type"] == "server_added"

    def test_server_removed_detected(self):
        previous = [
            {"pxname": "web", "svname": "srv1", "status": "UP", "scur": "0"},
        ]
        current = []

        events = _detect_changes(previous, current)

        assert len(events) == 1
        assert events[0]["type"] == "server_removed"
